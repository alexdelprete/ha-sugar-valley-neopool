"""Tests for NeoPool switch platform."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sugar_valley_neopool.const import (
    CMD_FILTRATION,
    MASK_HIDRO_COVER_ENABLE,
    MASK_HIDRO_TEMP_SHUTDOWN_ENABLE,
    REG_HIDRO_COVER_ENABLE,
)
from custom_components.sugar_valley_neopool.switch import (
    REGISTER_BIT_SWITCH_DESCRIPTIONS,
    REGISTER_SWITCH_DESCRIPTIONS,
    SWITCH_DESCRIPTIONS,
    NeoPoolAutoTimeSyncSwitch,
    NeoPoolRegisterBitSwitch,
    NeoPoolRegisterSwitch,
    NeoPoolSwitch,
    NeoPoolSwitchEntityDescription,
    async_setup_entry,
)


class TestSwitchDescriptions:
    """Tests for switch entity descriptions."""

    def test_switch_descriptions_exist(self) -> None:
        """Test that switch descriptions are defined."""
        assert len(SWITCH_DESCRIPTIONS) > 0

    def test_filtration_switch_description(self) -> None:
        """Test filtration switch description."""
        desc = next(d for d in SWITCH_DESCRIPTIONS if d.key == "filtration")

        assert desc.json_path == "NeoPool.Filtration.State"
        assert desc.command == CMD_FILTRATION
        assert desc.payload_on == "1"
        assert desc.payload_off == "0"

    def test_light_no_longer_a_switch(self) -> None:
        """The pool light moved to the light platform; not a switch anymore."""
        assert all(d.key != "light" for d in SWITCH_DESCRIPTIONS)

    def test_aux_no_longer_switches(self) -> None:
        """AUX1-4 moved to mode selects + binary sensors; not switches anymore."""
        assert all(not d.key.startswith("aux") for d in SWITCH_DESCRIPTIONS)

    def test_all_descriptions_have_command(self) -> None:
        """Test all descriptions have command field."""
        for desc in SWITCH_DESCRIPTIONS:
            assert desc.command is not None
            assert desc.json_path is not None


class TestNeoPoolSwitch:
    """Tests for NeoPoolSwitch entity."""

    def test_switch_initialization(self, mock_config_entry: MagicMock) -> None:
        """Test switch initialization."""
        desc = NeoPoolSwitchEntityDescription(
            key="test_switch",
            name="Test Switch",
            json_path="NeoPool.Test.State",
            command="NPTest",
        )

        switch = NeoPoolSwitch(mock_config_entry, desc)

        assert switch.entity_description == desc
        assert switch._attr_is_on is None
        assert switch._attr_unique_id == "neopool_mqtt_ABC123_test_switch"

    @pytest.mark.asyncio
    async def test_switch_turn_on(self, mock_config_entry: MagicMock, mock_hass: MagicMock) -> None:
        """Test switch turn on command."""
        desc = NeoPoolSwitchEntityDescription(
            key="filtration",
            name="Filtration",
            json_path="NeoPool.Filtration.State",
            command=CMD_FILTRATION,
            payload_on="1",
        )

        switch = NeoPoolSwitch(mock_config_entry, desc)
        switch.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await switch.async_turn_on()

            mock_publish.assert_called_once_with(
                mock_hass,
                f"cmnd/SmartPool/{CMD_FILTRATION}",
                "1",
                qos=0,
                retain=False,
            )

    @pytest.mark.asyncio
    async def test_switch_turn_off(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test switch turn off command."""
        desc = NeoPoolSwitchEntityDescription(
            key="filtration",
            name="Filtration",
            json_path="NeoPool.Filtration.State",
            command=CMD_FILTRATION,
            payload_off="0",
        )

        switch = NeoPoolSwitch(mock_config_entry, desc)
        switch.hass = mock_hass

        with patch(
            "homeassistant.components.mqtt.async_publish",
            new_callable=AsyncMock,
        ) as mock_publish:
            await switch.async_turn_off()

            mock_publish.assert_called_once_with(
                mock_hass,
                f"cmnd/SmartPool/{CMD_FILTRATION}",
                "0",
                qos=0,
                retain=False,
            )

    @pytest.mark.asyncio
    async def test_switch_state_from_mqtt(
        self,
        mock_config_entry: MagicMock,
        mock_hass: MagicMock,
        sample_payload: dict[str, Any],
    ) -> None:
        """Test switch state updates from MQTT message."""
        desc = NeoPoolSwitchEntityDescription(
            key="filtration",
            name="Filtration",
            json_path="NeoPool.Filtration.State",
            command=CMD_FILTRATION,
        )

        switch = NeoPoolSwitch(mock_config_entry, desc)
        switch.hass = mock_hass
        switch.entity_id = "switch.filtration"
        switch.async_write_ha_state = MagicMock()

        sensor_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal sensor_callback
            if "SENSOR" in topic:
                sensor_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await switch.async_added_to_hass()

        mock_msg = MagicMock()
        mock_msg.payload = json.dumps(sample_payload)
        sensor_callback(mock_msg)

        # Filtration.State = 1 in sample payload
        assert switch._attr_is_on is True
        assert switch._attr_available is True

    @pytest.mark.asyncio
    async def test_switch_handles_missing_path(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test switch handles missing JSON path gracefully."""
        desc = NeoPoolSwitchEntityDescription(
            key="test_switch",
            name="Test Switch",
            json_path="NeoPool.NonExistent.State",
            command="NPTest",
        )

        switch = NeoPoolSwitch(mock_config_entry, desc)
        switch.hass = mock_hass
        switch.entity_id = "switch.test"
        switch.async_write_ha_state = MagicMock()

        sensor_callback = None

        async def capture_callback(hass, topic, callback, **kwargs):
            nonlocal sensor_callback
            if "SENSOR" in topic:
                sensor_callback = callback
            return MagicMock()

        with patch(
            "homeassistant.components.mqtt.async_subscribe",
            side_effect=capture_callback,
        ):
            await switch.async_added_to_hass()

        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"NeoPool": {"Other": "data"}})
        sensor_callback(mock_msg)

        assert switch._attr_is_on is None
        assert switch._attr_available is False
        switch.async_write_ha_state.assert_called()


class TestAsyncSetupEntry:
    """Tests for async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_entry_creates_switches(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Test that setup entry creates all switch entities."""
        added_entities = []

        def async_add_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_config_entry, async_add_entities)

        # Command switches + auto-time-sync + register switches + bit switches.
        assert len(added_entities) == (
            len(SWITCH_DESCRIPTIONS)
            + 1
            + len(REGISTER_SWITCH_DESCRIPTIONS)
            + len(REGISTER_BIT_SWITCH_DESCRIPTIONS)
        )
        assert sum(isinstance(e, NeoPoolSwitch) for e in added_entities) == len(SWITCH_DESCRIPTIONS)
        assert any(isinstance(e, NeoPoolAutoTimeSyncSwitch) for e in added_entities)
        assert sum(isinstance(e, NeoPoolRegisterBitSwitch) for e in added_entities) == len(
            REGISTER_BIT_SWITCH_DESCRIPTIONS
        )


class TestNeoPoolAutoTimeSyncSwitch:
    """Tests for the HA-side auto time-sync switch."""

    def test_initialization(self, mock_config_entry: MagicMock) -> None:
        """Switch initializes from the runtime_data flag and is always available."""
        mock_config_entry.runtime_data.auto_time_sync = False
        switch = NeoPoolAutoTimeSyncSwitch(mock_config_entry)

        assert switch._attr_unique_id == "neopool_mqtt_ABC123_auto_time_sync"
        assert switch._attr_available is True
        assert switch.is_on is False

    @pytest.mark.asyncio
    async def test_turn_on_off_updates_runtime_flag(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Toggling sets both the entity state and the shared runtime flag."""
        mock_config_entry.runtime_data.auto_time_sync = False
        switch = NeoPoolAutoTimeSyncSwitch(mock_config_entry)
        switch.hass = mock_hass
        switch.async_write_ha_state = MagicMock()

        await switch.async_turn_on()
        assert switch.is_on is True
        assert mock_config_entry.runtime_data.auto_time_sync is True

        await switch.async_turn_off()
        assert switch.is_on is False
        assert mock_config_entry.runtime_data.auto_time_sync is False

    @pytest.mark.asyncio
    async def test_restores_last_state(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """On add, the switch restores its last on/off state across restarts."""
        mock_config_entry.runtime_data.auto_time_sync = False
        switch = NeoPoolAutoTimeSyncSwitch(mock_config_entry)
        switch.hass = mock_hass
        switch.async_write_ha_state = MagicMock()

        last_state = MagicMock()
        last_state.state = "on"

        with (
            patch(
                "homeassistant.helpers.restore_state.RestoreEntity.async_added_to_hass",
                new_callable=AsyncMock,
            ),
            patch.object(
                NeoPoolAutoTimeSyncSwitch,
                "async_get_last_state",
                new=AsyncMock(return_value=last_state),
            ),
        ):
            await switch.async_added_to_hass()

        assert switch.is_on is True
        assert mock_config_entry.runtime_data.auto_time_sync is True


class TestNeoPoolRegisterSwitch:
    """Tests for register-backed config switches (UV/climate/antifreeze)."""

    def _make(self, entry: MagicMock) -> tuple[NeoPoolRegisterSwitch, Any]:
        desc = REGISTER_SWITCH_DESCRIPTIONS[0]  # uv_mode
        return NeoPoolRegisterSwitch(entry, desc), desc

    def test_is_on_from_register_state(self, mock_config_entry: MagicMock) -> None:
        """is_on reflects the cached register value (None when unknown)."""
        sw, desc = self._make(mock_config_entry)
        mock_config_entry.runtime_data.register_state.clear()
        assert sw.is_on is None
        mock_config_entry.runtime_data.register_state[desc.register] = 1
        assert sw.is_on is True
        mock_config_entry.runtime_data.register_state[desc.register] = 0
        assert sw.is_on is False

    def test_available_requires_gating_and_value(self, mock_config_entry: MagicMock) -> None:
        """Availability needs online + gating keys present + a cached value."""
        sw, desc = self._make(mock_config_entry)
        mock_config_entry.runtime_data.register_state.clear()
        sw._attr_available = True  # LWT online
        sw._gating_ok = False
        assert sw.available is False
        sw._gating_ok = True
        assert sw.available is False  # value not cached yet
        mock_config_entry.runtime_data.register_state[desc.register] = 1
        assert sw.available is True

    @pytest.mark.asyncio
    async def test_turn_on_off_writes_register(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Toggling writes the register and optimistically updates the cache."""
        sw, desc = self._make(mock_config_entry)
        sw.hass = mock_hass
        sw.async_write_ha_state = MagicMock()
        mock_config_entry.runtime_data.register_state.clear()

        with patch.object(sw, "_write_register", new_callable=AsyncMock) as mock_w:
            await sw.async_turn_on()
            mock_w.assert_awaited_once_with(desc.register, 1)
            assert mock_config_entry.runtime_data.register_state[desc.register] == 1

            await sw.async_turn_off()
            assert mock_config_entry.runtime_data.register_state[desc.register] == 0

    @pytest.mark.asyncio
    async def test_gating_tracked_from_sensor(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """The SENSOR watch flips _gating_ok on gating-key presence."""
        sw, _desc = self._make(mock_config_entry)  # uv_mode gates on Relay.UV
        sw.hass = mock_hass
        sw.async_write_ha_state = MagicMock()

        sensor_cb = None

        async def capture(hass, topic, cb, **kwargs):
            nonlocal sensor_cb
            if "SENSOR" in topic:
                sensor_cb = cb
            return MagicMock()

        with (
            patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture),
            patch(
                "custom_components.sugar_valley_neopool.switch.async_dispatcher_connect",
                return_value=MagicMock(),
            ),
        ):
            await sw.async_added_to_hass()

        msg = MagicMock()
        msg.payload = json.dumps({"NeoPool": {"Relay": {"UV": 0}}})
        sensor_cb(msg)
        assert sw._gating_ok is True

        msg.payload = json.dumps({"NeoPool": {"Other": 1}})
        sensor_cb(msg)
        assert sw._gating_ok is False


class TestNeoPoolRegisterBitSwitch:
    """Tests for bit-packed config switches (cover-reduction / temp-shutdown)."""

    def _make(self, entry: MagicMock, key: str) -> NeoPoolRegisterBitSwitch:
        desc = next(d for d in REGISTER_BIT_SWITCH_DESCRIPTIONS if d.key == key)
        return NeoPoolRegisterBitSwitch(entry, desc)

    def test_is_on_reads_bit(self, mock_config_entry: MagicMock) -> None:
        """is_on reflects only the entity's own bit of the shared register."""
        sw = self._make(mock_config_entry, "hydro_cover_reduction")
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        assert sw.is_on is None
        rs[REG_HIDRO_COVER_ENABLE] = MASK_HIDRO_TEMP_SHUTDOWN_ENABLE  # other bit only
        assert sw.is_on is False
        rs[REG_HIDRO_COVER_ENABLE] = MASK_HIDRO_COVER_ENABLE
        assert sw.is_on is True

    @pytest.mark.asyncio
    async def test_turn_on_preserves_sibling_bit(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Toggling one bit must not clobber the sibling bit in the register."""
        sw = self._make(mock_config_entry, "hydro_cover_reduction")
        sw.hass = mock_hass
        sw.async_write_ha_state = MagicMock()
        rs = mock_config_entry.runtime_data.register_state
        rs.clear()
        # Temp-shutdown already enabled; cover-reduction off.
        rs[REG_HIDRO_COVER_ENABLE] = MASK_HIDRO_TEMP_SHUTDOWN_ENABLE

        with patch.object(sw, "_write_register", new_callable=AsyncMock) as mock_w:
            await sw.async_turn_on()
            expected = MASK_HIDRO_TEMP_SHUTDOWN_ENABLE | MASK_HIDRO_COVER_ENABLE
            mock_w.assert_awaited_once_with(REG_HIDRO_COVER_ENABLE, expected)
            assert rs[REG_HIDRO_COVER_ENABLE] == expected

            await sw.async_turn_off()
            # Cover bit cleared, temp-shutdown bit preserved.
            assert rs[REG_HIDRO_COVER_ENABLE] == MASK_HIDRO_TEMP_SHUTDOWN_ENABLE

    @pytest.mark.asyncio
    async def test_no_write_when_value_uncached(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Without a cached register value, a blind RMW write is skipped."""
        sw = self._make(mock_config_entry, "hydro_temp_shutdown")
        sw.hass = mock_hass
        sw.async_write_ha_state = MagicMock()
        mock_config_entry.runtime_data.register_state.clear()

        with patch.object(sw, "_write_register", new_callable=AsyncMock) as mock_w:
            await sw.async_turn_on()
            mock_w.assert_not_awaited()


class TestNeoPoolRegisterSwitchEdges:
    """Edge coverage: invalid payload guard + dispatcher-driven refresh."""

    @pytest.mark.asyncio
    async def test_invalid_payload_and_handle_update(
        self, mock_config_entry: MagicMock, mock_hass: MagicMock
    ) -> None:
        """Invalid SENSOR payload is ignored; _handle_register_update writes state."""
        desc = REGISTER_SWITCH_DESCRIPTIONS[0]  # uv_mode
        sw = NeoPoolRegisterSwitch(mock_config_entry, desc)
        sw.hass = mock_hass
        sw.async_write_ha_state = MagicMock()

        sensor_cb = None

        async def capture(hass, topic, cb, **kwargs):
            nonlocal sensor_cb
            if "SENSOR" in topic:
                sensor_cb = cb
            return MagicMock()

        with (
            patch("homeassistant.components.mqtt.async_subscribe", side_effect=capture),
            patch(
                "custom_components.sugar_valley_neopool.switch.async_dispatcher_connect",
                return_value=MagicMock(),
            ),
        ):
            await sw.async_added_to_hass()

        msg = MagicMock()
        msg.payload = "not json {{{"
        sensor_cb(msg)  # must not raise
        assert sw._gating_ok is False

        sw.async_write_ha_state.reset_mock()
        sw._handle_register_update()
        sw.async_write_ha_state.assert_called_once()

"""Platform-specific tests to boost coverage.

Tests for sensor, binary_sensor, switch, select, number, and button platforms.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sugar_valley_neopool import NeoPoolData
from custom_components.sugar_valley_neopool.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    NeoPoolBinarySensor,
    async_setup_entry as binary_sensor_setup,
)
from custom_components.sugar_valley_neopool.button import (
    BUTTON_DESCRIPTIONS,
    NeoPoolButton,
    async_setup_entry as button_setup,
)
from custom_components.sugar_valley_neopool.const import (
    CONF_DEVICE_NAME,
    CONF_DISCOVERY_PREFIX,
    CONF_NODEID,
    DOMAIN,
)
from custom_components.sugar_valley_neopool.entity import NeoPoolEntity, NeoPoolMQTTEntity
from custom_components.sugar_valley_neopool.number import (
    NUMBER_DESCRIPTIONS,
    REGISTER_BYTE_NUMBER_DESCRIPTIONS,
    REGISTER_NUMBER_DESCRIPTIONS,
    NeoPoolNumber,
    async_setup_entry as number_setup,
)
from custom_components.sugar_valley_neopool.select import (
    SELECT_DESCRIPTIONS,
    NeoPoolSelect,
    async_setup_entry as select_setup,
)
from custom_components.sugar_valley_neopool.sensor import (
    SENSOR_DESCRIPTIONS,
    NeoPoolSensor,
    async_setup_entry as sensor_setup,
)
from custom_components.sugar_valley_neopool.switch import (
    REGISTER_BIT_SWITCH_DESCRIPTIONS,
    REGISTER_SWITCH_DESCRIPTIONS,
    SWITCH_DESCRIPTIONS,
    NeoPoolSwitch,
    async_setup_entry as switch_setup,
)
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_NAME: "Test Pool",
            CONF_DISCOVERY_PREFIX: "SmartPool",
            CONF_NODEID: "ABC123",
        },
    )
    entry.add_to_hass(hass)
    entry.runtime_data = NeoPoolData(
        device_name="Test Pool",
        mqtt_topic="SmartPool",
        nodeid="ABC123",
    )
    return entry


class TestNeoPoolEntityBase:
    """Tests for NeoPoolEntity base class."""

    def test_entity_unique_id_format(self, mock_config_entry: MockConfigEntry) -> None:
        """Test entity unique_id follows correct format."""
        entity = NeoPoolEntity(mock_config_entry, "water_temperature")

        assert entity._attr_unique_id == "neopool_mqtt_ABC123_water_temperature"

    def test_entity_has_entity_name(self, mock_config_entry: MockConfigEntry) -> None:
        """Test entity has entity name attribute."""
        entity = NeoPoolEntity(mock_config_entry, "test_key")

        assert entity._attr_has_entity_name is True

    def test_entity_initially_unavailable(self, mock_config_entry: MockConfigEntry) -> None:
        """Test entity is initially unavailable."""
        entity = NeoPoolEntity(mock_config_entry, "test_key")

        assert entity._attr_available is False

    def test_mqtt_topic_property(self, mock_config_entry: MockConfigEntry) -> None:
        """Test mqtt_topic property returns correct value."""
        entity = NeoPoolEntity(mock_config_entry, "test_key")

        assert entity.mqtt_topic == "SmartPool"


class TestNeoPoolMQTTEntityBase:
    """Tests for NeoPoolMQTTEntity base class."""

    def test_unsubscribe_callbacks_initialized(self, mock_config_entry: MockConfigEntry) -> None:
        """Test unsubscribe callbacks list is initialized."""
        entity = NeoPoolMQTTEntity(mock_config_entry, "test_key")

        assert entity._unsubscribe_callbacks == []

    @pytest.mark.asyncio
    async def test_async_will_remove_clears_callbacks(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test async_will_remove_from_hass clears callbacks."""
        entity = NeoPoolMQTTEntity(mock_config_entry, "test_key")
        entity.hass = hass

        mock_unsub1 = MagicMock()
        mock_unsub2 = MagicMock()
        entity._unsubscribe_callbacks = [mock_unsub1, mock_unsub2]

        await entity.async_will_remove_from_hass()

        mock_unsub1.assert_called_once()
        mock_unsub2.assert_called_once()
        assert entity._unsubscribe_callbacks == []


class TestSensorPlatform:
    """Tests for sensor platform."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_sensors(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test async_setup_entry creates all sensors."""
        entities = []

        def capture_entities(new_entities):
            entities.extend(new_entities)

        await sensor_setup(hass, mock_config_entry, capture_entities)

        # +1 for the standalone NeoPoolConnectionRateSensor (no entity description —
        # reads from the shared ConnectionRateTracker in runtime_data)
        assert len(entities) == len(SENSOR_DESCRIPTIONS) + 1

    def test_all_sensor_descriptions_have_json_path(self) -> None:
        """Test all sensor descriptions have json_path."""
        for desc in SENSOR_DESCRIPTIONS:
            assert hasattr(desc, "json_path")
            assert desc.json_path is not None
            assert desc.json_path.startswith("NeoPool.")

    def test_sensor_initial_value_none(self, mock_config_entry: MockConfigEntry) -> None:
        """Test sensor starts with None value."""
        desc = SENSOR_DESCRIPTIONS[0]
        sensor = NeoPoolSensor(mock_config_entry, desc)

        assert sensor._attr_native_value is None


class TestBinarySensorPlatform:
    """Tests for binary_sensor platform."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_binary_sensors(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test async_setup_entry creates all binary sensors."""
        entities = []

        def capture_entities(new_entities):
            entities.extend(new_entities)

        await binary_sensor_setup(hass, mock_config_entry, capture_entities)

        # +1 for the standalone NeoPoolConnectionProblemBinarySensor
        assert len(entities) == len(BINARY_SENSOR_DESCRIPTIONS) + 1

    def test_binary_sensor_invert_logic(self) -> None:
        """Test some binary sensors use invert logic."""
        inverted = [d for d in BINARY_SENSOR_DESCRIPTIONS if d.invert]

        # Should have sensors with invert=True (water flow, tank levels)
        assert len(inverted) >= 2

    def test_binary_sensor_initial_state(self, mock_config_entry: MockConfigEntry) -> None:
        """Test binary sensor starts with None state."""
        desc = BINARY_SENSOR_DESCRIPTIONS[0]
        sensor = NeoPoolBinarySensor(mock_config_entry, desc)

        assert sensor._attr_is_on is None


class TestSwitchPlatform:
    """Tests for switch platform."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_switches(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test async_setup_entry creates all switches."""
        entities = []

        def capture_entities(new_entities):
            entities.extend(new_entities)

        await switch_setup(hass, mock_config_entry, capture_entities)

        # +1 auto-time-sync switch, + register switches, + bit-packed switches.
        assert len(entities) == (
            len(SWITCH_DESCRIPTIONS)
            + 1
            + len(REGISTER_SWITCH_DESCRIPTIONS)
            + len(REGISTER_BIT_SWITCH_DESCRIPTIONS)
        )

    def test_all_switches_have_commands(self) -> None:
        """Test all switch descriptions have command."""
        for desc in SWITCH_DESCRIPTIONS:
            assert hasattr(desc, "command")
            assert desc.command.startswith("NP")

    def test_switch_payloads(self) -> None:
        """Test switch payloads are correct."""
        for desc in SWITCH_DESCRIPTIONS:
            assert desc.payload_on == "1"
            assert desc.payload_off == "0"

    @pytest.mark.asyncio
    async def test_switch_turn_on(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test switch turn_on publishes command."""
        desc = SWITCH_DESCRIPTIONS[0]  # Filtration
        switch = NeoPoolSwitch(mock_config_entry, desc)
        switch.hass = hass

        with patch.object(switch, "_publish_command") as mock_publish:
            await switch.async_turn_on()

        mock_publish.assert_called_once_with(desc.command, desc.payload_on)

    @pytest.mark.asyncio
    async def test_switch_turn_off(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test switch turn_off publishes command."""
        desc = SWITCH_DESCRIPTIONS[0]  # Filtration
        switch = NeoPoolSwitch(mock_config_entry, desc)
        switch.hass = hass

        with patch.object(switch, "_publish_command") as mock_publish:
            await switch.async_turn_off()

        mock_publish.assert_called_once_with(desc.command, desc.payload_off)


class TestSelectPlatform:
    """Tests for select platform."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_selects(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test async_setup_entry creates all selects."""
        entities = []

        def capture_entities(new_entities):
            entities.extend(new_entities)

        await select_setup(hass, mock_config_entry, capture_entities)

        assert len(entities) == len(SELECT_DESCRIPTIONS)

    def test_all_selects_have_options_map(self) -> None:
        """Test all select descriptions have options_map."""
        for desc in SELECT_DESCRIPTIONS:
            assert hasattr(desc, "options_map")
            assert len(desc.options_map) > 0
            # Options should match options_map values
            assert list(desc.options) == list(desc.options_map.values())

    def test_select_initial_option(self, mock_config_entry: MockConfigEntry) -> None:
        """Test select starts with None option."""
        desc = SELECT_DESCRIPTIONS[0]
        select = NeoPoolSelect(mock_config_entry, desc)

        assert select._attr_current_option is None
        assert select._attr_options == list(desc.options_map.values())

    @pytest.mark.asyncio
    async def test_select_option_publishes_int(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test selecting option publishes integer value."""
        desc = SELECT_DESCRIPTIONS[0]  # Filtration Mode
        select = NeoPoolSelect(mock_config_entry, desc)
        select.hass = hass

        # Get first option name and its integer key
        first_key = list(desc.options_map.keys())[0]
        first_option = desc.options_map[first_key]

        with patch.object(select, "_publish_command") as mock_publish:
            await select.async_select_option(first_option)

        mock_publish.assert_called_once_with(desc.command, str(first_key))

    @pytest.mark.asyncio
    async def test_select_invalid_option_logs_warning(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test selecting invalid option logs warning."""
        desc = SELECT_DESCRIPTIONS[0]
        select = NeoPoolSelect(mock_config_entry, desc)
        select.hass = hass

        with patch.object(select, "_publish_command") as mock_publish:
            await select.async_select_option("Invalid Option")

        # Should not publish for invalid option
        mock_publish.assert_not_called()


class TestNumberPlatform:
    """Tests for number platform."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_numbers(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test async_setup_entry creates all numbers."""
        entities = []

        def capture_entities(new_entities):
            entities.extend(new_entities)

        await number_setup(hass, mock_config_entry, capture_entities)

        # Command numbers + register numbers + byte-packed register numbers.
        assert len(entities) == (
            len(NUMBER_DESCRIPTIONS)
            + len(REGISTER_NUMBER_DESCRIPTIONS)
            + len(REGISTER_BYTE_NUMBER_DESCRIPTIONS)
        )

    def test_all_numbers_have_limits(self) -> None:
        """Test all number descriptions have min/max values."""
        for desc in NUMBER_DESCRIPTIONS:
            assert desc.native_min_value is not None
            if desc.max_json_path:
                # Dynamic max: native_max_value is None until device reports it
                pass
            else:
                assert desc.native_max_value is not None
                assert desc.native_min_value < desc.native_max_value

    def test_number_initial_value(self, mock_config_entry: MockConfigEntry) -> None:
        """Test number starts with None value."""
        desc = NUMBER_DESCRIPTIONS[0]
        number = NeoPoolNumber(mock_config_entry, desc)

        assert number._attr_native_value is None

    @pytest.mark.asyncio
    async def test_number_set_value_with_template(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test setting value with command_template."""
        # Find hydrolysis_setpoint which has command_template
        desc = next(d for d in NUMBER_DESCRIPTIONS if d.command_template)
        number = NeoPoolNumber(mock_config_entry, desc)
        number.hass = hass

        with patch.object(number, "_publish_command") as mock_publish:
            await number.async_set_native_value(50.0)

        # Should format as "50 %" for hydrolysis
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args[0]
        assert "50 %" in call_args[1]

    @pytest.mark.asyncio
    async def test_number_set_value_integer(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test setting value as integer when step >= 1."""
        # Find redox_setpoint which has step=1
        desc = next(
            d
            for d in NUMBER_DESCRIPTIONS
            if d.native_step and d.native_step >= 1 and not d.command_template
        )
        number = NeoPoolNumber(mock_config_entry, desc)
        number.hass = hass

        with patch.object(number, "_publish_command") as mock_publish:
            await number.async_set_native_value(750.0)

        mock_publish.assert_called_once_with(desc.command, "750")

    @pytest.mark.asyncio
    async def test_number_set_value_float(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test setting value as float when step < 1."""
        # Find ph_min which has step=0.1
        desc = next(
            d
            for d in NUMBER_DESCRIPTIONS
            if d.native_step and d.native_step < 1 and not d.command_template
        )
        number = NeoPoolNumber(mock_config_entry, desc)
        number.hass = hass

        with patch.object(number, "_publish_command") as mock_publish:
            await number.async_set_native_value(7.2)

        mock_publish.assert_called_once_with(desc.command, "7.2")


class TestButtonPlatform:
    """Tests for button platform."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_creates_buttons(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test async_setup_entry creates all buttons."""
        entities = []

        def capture_entities(new_entities):
            entities.extend(new_entities)

        await button_setup(hass, mock_config_entry, capture_entities)

        # +1 for the dedicated reset-cell-runtime button (not description-driven).
        assert len(entities) == len(BUTTON_DESCRIPTIONS) + 1

    def test_button_always_available(self, mock_config_entry: MockConfigEntry) -> None:
        """Test button is always available."""
        desc = BUTTON_DESCRIPTIONS[0]
        button = NeoPoolButton(mock_config_entry, desc)

        assert button._attr_available is True

    @pytest.mark.asyncio
    async def test_button_press_publishes_command(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test button press publishes command."""
        desc = BUTTON_DESCRIPTIONS[0]  # Clear Error
        button = NeoPoolButton(mock_config_entry, desc)
        button.hass = hass

        with patch.object(button, "_publish_command") as mock_publish:
            await button.async_press()

        mock_publish.assert_called_once_with(desc.command, desc.payload)


class TestEntityDescriptionCoverage:
    """Tests to ensure all entity descriptions are valid."""

    def test_sensor_descriptions_count(self) -> None:
        """Test sensor descriptions count."""
        assert len(SENSOR_DESCRIPTIONS) >= 20

    def test_binary_sensor_descriptions_count(self) -> None:
        """Test binary sensor descriptions count."""
        assert len(BINARY_SENSOR_DESCRIPTIONS) >= 10

    def test_switch_descriptions_count(self) -> None:
        """Test switch descriptions count."""
        assert len(SWITCH_DESCRIPTIONS) >= 5

    def test_select_descriptions_count(self) -> None:
        """Test select descriptions count."""
        assert len(SELECT_DESCRIPTIONS) >= 3

    def test_number_descriptions_count(self) -> None:
        """Test number descriptions count."""
        assert len(NUMBER_DESCRIPTIONS) >= 4

    def test_button_descriptions_count(self) -> None:
        """Test button descriptions count."""
        assert len(BUTTON_DESCRIPTIONS) >= 1

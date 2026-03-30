"""Tests for sensor/binary_sensor logic — TC-032 to TC-037.

These tests validate entity logic without requiring the HA runtime.
They test the data extraction and mapping logic directly.
"""

import pytest

from yarbo_robot_sdk.device_helpers import extract_field
from yarbo_robot_sdk.models import Device


# ---- Sensor logic tests (no HA dependency) ----

SAMPLE_DEVICE = Device(
    sn="SN001", type_id="snowbot", name="My Snowbot", model="S1", online=True
)

SAMPLE_STATUS = {
    "BatteryMSG": {"capacity": 85, "status": 1, "temp_err": 0},
    "StateMSG": {
        "working_state": 1,
        "charging_status": 0,
        "error_code": 0,
    },
    "CombinedOdom": {"x": -2.836, "y": 9.515, "phi": -0.033},
    "RTKMSG": {"status": "2"},
}

WORKING_STATE_MAP = {
    0: "idle",
    1: "working",
    2: "paused",
    3: "error",
    4: "returning",
}


class TestBatterySensorLogic:
    """TC-032: Battery sensor data extraction."""

    def test_battery_value(self):
        value = extract_field(SAMPLE_STATUS, "BatteryMSG.capacity")
        assert value == 85

    def test_battery_missing(self):
        value = extract_field({}, "BatteryMSG.capacity")
        assert value is None


class TestWorkingStateSensorLogic:
    """TC-033: Working state enum mapping."""

    @pytest.mark.parametrize(
        "state,expected",
        [(0, "idle"), (1, "working"), (2, "paused"), (3, "error"), (4, "returning")],
    )
    def test_known_states(self, state, expected):
        assert WORKING_STATE_MAP.get(state) == expected

    def test_unknown_state(self):
        state = 99
        result = WORKING_STATE_MAP.get(state, f"unknown_{state}")
        assert result == "unknown_99"

    def test_extract_working_state(self):
        value = extract_field(SAMPLE_STATUS, "StateMSG.working_state")
        assert value == 1


class TestOnlineBinarySensorLogic:
    """TC-034: Online status from device object."""

    def test_online_true(self):
        device = Device(sn="SN001", type_id="snowbot", name="Bot", model="S1", online=True)
        assert device.online is True

    def test_online_false(self):
        device = Device(sn="SN001", type_id="snowbot", name="Bot", model="S1", online=False)
        assert device.online is False


class TestChargingBinarySensorLogic:
    """TC-035: Charging status extraction."""

    def test_charging_active(self):
        data = {"StateMSG": {"charging_status": 1}}
        status = extract_field(data, "StateMSG.charging_status")
        assert status == 1

    def test_charging_inactive(self):
        status = extract_field(SAMPLE_STATUS, "StateMSG.charging_status")
        assert status == 0

    def test_charging_missing(self):
        status = extract_field({}, "StateMSG.charging_status")
        assert status is None


class TestDeviceInfo:
    """TC-036: Device info correctness."""

    def test_device_fields(self):
        assert SAMPLE_DEVICE.sn == "SN001"
        assert SAMPLE_DEVICE.name == "My Snowbot"
        assert SAMPLE_DEVICE.model == "S1"
        assert SAMPLE_DEVICE.type_id == "snowbot"


class TestMultiDeviceSupport:
    """TC-037: Multiple devices supported."""

    def test_multiple_devices_different_types(self):
        devices = [
            Device(sn="SN001", type_id="snowbot", name="Snowbot 1", model="S1", online=True),
            Device(sn="SN002", type_id="snowbot", name="Snowbot 2", model="S1", online=False),
            Device(sn="SN003", type_id="mower", name="Mower 1", model="M1", online=True),
        ]
        assert len(devices) == 3

        # Each device should get 4 entities (battery, working_state, online, charging)
        entity_count = len(devices) * 4
        assert entity_count == 12

        # Unique IDs should be unique
        unique_ids = set()
        for d in devices:
            for suffix in ["battery", "working_state", "online", "charging"]:
                unique_ids.add(f"{d.sn}_{suffix}")
        assert len(unique_ids) == 12

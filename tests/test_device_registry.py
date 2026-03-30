"""Tests for device registry — TC-016, TC-017."""

from yarbo_robot_sdk.device_registry import (
    DeviceType,
    get_device_type,
    list_device_types,
)


class TestGetDeviceType:
    """TC-016."""

    def test_existing_type(self):
        dt = get_device_type("mower")
        assert dt is not None
        assert dt.type_id == "mower"
        assert dt.name == "割草机器人"

    def test_snowbot_type(self):
        dt = get_device_type("snowbot")
        assert dt is not None
        assert dt.type_id == "snowbot"

    def test_nonexistent_type(self):
        assert get_device_type("nonexistent") is None


class TestListDeviceTypes:
    """TC-017."""

    def test_returns_all_types(self):
        types = list_device_types()
        assert len(types) >= 2
        assert all(isinstance(t, DeviceType) for t in types)
        type_ids = {t.type_id for t in types}
        assert "mower" in type_ids
        assert "snowbot" in type_ids

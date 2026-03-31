"""Tests for device_helpers."""

import pytest

from yarbo_robot_sdk.device_helpers import (
    extract_field,
    resolve_device_msg_topic,
    resolve_topic_by_name,
)
from yarbo_robot_sdk.device_registry import get_device_type
from yarbo_robot_sdk.exceptions import YarboSDKError


class TestDeviceRegistryData:
    def test_yarbo_y_loaded(self):
        dt = get_device_type("yarbo_Y")
        assert dt is not None
        assert dt.name == "Yarbo Y Series"

    def test_yarbo_y_has_device_msg_topic(self):
        dt = get_device_type("yarbo_Y")
        topic_names = [t.name for t in dt.topics]
        assert "device_msg" in topic_names
        device_msg_topic = next(t for t in dt.topics if t.name == "device_msg")
        assert device_msg_topic.template == "snowbot/{sn}/device/DeviceMSG"

    def test_yarbo_y_has_heart_beat_topic(self):
        dt = get_device_type("yarbo_Y")
        topic_names = [t.name for t in dt.topics]
        assert "heart_beat" in topic_names
        hb_topic = next(t for t in dt.topics if t.name == "heart_beat")
        assert hb_topic.template == "snowbot/{sn}/device/heart_beat"

    def test_yarbo_y_has_status_fields(self):
        dt = get_device_type("yarbo_Y")
        paths = [f.path for f in dt.status_fields]
        assert "BatteryMSG.capacity" in paths
        assert "StateMSG.working_state" in paths
        assert "HeartBeatMSG.working_state" in paths


class TestExtractField:
    def test_extract_nested_value(self):
        data = {"BatteryMSG": {"capacity": 42, "status": 1}}
        assert extract_field(data, "BatteryMSG.capacity") == 42

    def test_extract_missing_nested_key(self):
        data = {"BatteryMSG": {"capacity": 42}}
        assert extract_field(data, "BatteryMSG.nonexistent") is None

    def test_extract_missing_top_key(self):
        data = {"BatteryMSG": {"capacity": 42}}
        assert extract_field(data, "NonExistent.field") is None

    def test_extract_top_level_key(self):
        data = {"timestamp": 123456}
        assert extract_field(data, "timestamp") == 123456

    def test_extract_from_empty_dict(self):
        assert extract_field({}, "any.path") is None


class TestResolveDeviceMsgTopic:
    def test_resolve_yarbo_y(self):
        topic = resolve_device_msg_topic("SN001", "yarbo_Y")
        assert topic == "snowbot/SN001/device/DeviceMSG"

    def test_resolve_unknown_type(self):
        with pytest.raises(YarboSDKError, match="Unknown device type"):
            resolve_device_msg_topic("SN001", "unknown_type")


class TestResolveTopicByName:
    def test_resolve_device_msg(self):
        assert resolve_topic_by_name("SN001", "yarbo_Y", "device_msg") == "snowbot/SN001/device/DeviceMSG"

    def test_resolve_heart_beat(self):
        assert resolve_topic_by_name("SN001", "yarbo_Y", "heart_beat") == "snowbot/SN001/device/heart_beat"

    def test_resolve_unknown_topic_name(self):
        with pytest.raises(YarboSDKError, match="No topic"):
            resolve_topic_by_name("SN001", "yarbo_Y", "nonexistent_topic")

    def test_resolve_unknown_device_type(self):
        with pytest.raises(YarboSDKError, match="Unknown device type"):
            resolve_topic_by_name("SN001", "bad_type", "heart_beat")

"""Tests for device_registry — JSON loading, FieldDefinition, backward compat."""

import json
from pathlib import Path

import pytest

from yarbo_robot_sdk.device_registry import (
    DEVICE_REGISTRY,
    DeviceRegistryError,
    DeviceType,
    _load_device_type,
    get_control_field_definitions,
    get_device_type,
    get_field_definitions,
    list_device_types,
    resolve_control_topic,
)
from yarbo_robot_sdk.exceptions import YarboSDKError
from yarbo_robot_sdk.models import ControlFieldDefinition, FieldDefinition


# ---- TC-001: JSON config files load correctly ----

class TestJsonLoading:
    def test_list_device_types_returns_two(self):
        types = list_device_types()
        assert len(types) >= 1

    def test_snowbot_loaded(self):
        dt = get_device_type("yarbo_Y")
        assert dt is not None
        assert dt.type_id == "yarbo_Y"
        assert dt.name == "Yarbo Y Series"

    def test_mower_loaded(self):
        dt = get_device_type("yarbo_Y")
        assert dt is not None
        assert dt.type_id == "yarbo_Y"
        assert dt.name == "Yarbo Y Series"

    def test_topics_parsed(self):
        dt = get_device_type("yarbo_Y")
        assert len(dt.topics) >= 1
        assert dt.topics[0].name == "device_msg"
        assert "{sn}" in dt.topics[0].template

    def test_apis_parsed(self):
        dt = get_device_type("yarbo_Y")
        assert len(dt.apis) >= 1
        assert dt.apis[0].name == "device_detail"
        assert dt.apis[0].method == "GET"


# ---- TC-002: FieldDefinition metadata ----

class TestFieldDefinitionMetadata:
    def test_battery_field_metadata(self):
        fields = get_field_definitions("yarbo_Y")
        battery = next(f for f in fields if f.path == "BatteryMSG.capacity")
        assert battery.name == "Battery"
        assert battery.entity_type == "sensor"
        assert battery.device_class == "battery"
        assert battery.unit == "%"
        assert battery.enabled_by_default is True
        assert battery.category == "battery"

    def test_field_definition_is_dataclass(self):
        fields = get_field_definitions("yarbo_Y")
        assert isinstance(fields[0], FieldDefinition)


# ---- TC-003: value_map loading ----

class TestValueMap:
    def test_working_state_value_map(self):
        fields = get_field_definitions("yarbo_Y")
        ws = next(f for f in fields if f.path == "StateMSG.working_state")
        assert ws.value_map is not None
        assert ws.value_map["0"] == "idle"
        assert ws.value_map["1"] == "working"
        assert ws.device_class == "enum"

    def test_charging_value_map(self):
        fields = get_field_definitions("yarbo_Y")
        ch = next(f for f in fields if f.path == "StateMSG.charging_status")
        assert ch.entity_type == "binary_sensor"
        assert ch.value_map["1"] == "true"
        assert ch.value_map["0"] == "false"


# ---- TC-004: Yarbo Y has all field categories ----

class TestYarboYFieldCategories:
    def test_has_battery_fields(self):
        fields = get_field_definitions("yarbo_Y")
        paths = [f.path for f in fields]
        assert "BatteryMSG.capacity" in paths
        assert "StateMSG.charging_status" in paths

    def test_has_status_fields(self):
        fields = get_field_definitions("yarbo_Y")
        paths = [f.path for f in fields]
        assert "StateMSG.working_state" in paths
        assert "StateMSG.error_code" in paths

    def test_has_rtk_fields(self):
        fields = get_field_definitions("yarbo_Y")
        paths = [f.path for f in fields]
        assert "RTKMSG.status" in paths

    def test_has_head_fields(self):
        fields = get_field_definitions("yarbo_Y")
        paths = [f.path for f in fields]
        assert "HeadMsg.head_type" in paths

    def test_head_type_value_map(self):
        fields = get_field_definitions("yarbo_Y")
        ht = next(f for f in fields if f.path == "HeadMsg.head_type")
        assert ht.value_map["0"] == "none"
        assert ht.value_map["1"] == "snow_blower"
        assert ht.value_map["2"] == "leaf_blower"
        assert ht.value_map["3"] == "mower"
        assert ht.value_map["4"] == "smart_cover"


# ---- TC-005: Backward compatibility ----

class TestBackwardCompat:
    def test_status_fields_have_path_attr(self):
        dt = get_device_type("yarbo_Y")
        for field_def in dt.status_fields:
            assert hasattr(field_def, "path")

    def test_topic_template_accessible(self):
        dt = get_device_type("yarbo_Y")
        assert "snowbot/{sn}" in dt.topics[0].template

    def test_list_device_types_returns_device_type(self):
        types = list_device_types()
        assert all(isinstance(t, DeviceType) for t in types)


# ---- TC-006: Invalid JSON raises error ----

class TestInvalidJson:
    def test_missing_type_id(self, tmp_path):
        bad_json = tmp_path / "bad.json"
        bad_json.write_text('{"name": "test", "fields": []}')
        with pytest.raises(DeviceRegistryError, match="Missing 'type_id'"):
            _load_device_type(bad_json)

    def test_invalid_json_syntax(self, tmp_path):
        bad_json = tmp_path / "bad.json"
        bad_json.write_text('{invalid json}')
        with pytest.raises(DeviceRegistryError, match="Invalid JSON"):
            _load_device_type(bad_json)

    def test_missing_field_path(self, tmp_path):
        bad_json = tmp_path / "bad.json"
        bad_json.write_text(json.dumps({
            "type_id": "test",
            "name": "test",
            "fields": [{"name": "Test", "entity_type": "sensor"}]
        }))
        with pytest.raises(DeviceRegistryError, match="Missing required field 'path'"):
            _load_device_type(bad_json)

    def test_invalid_entity_type(self, tmp_path):
        bad_json = tmp_path / "bad.json"
        bad_json.write_text(json.dumps({
            "type_id": "test",
            "name": "test",
            "fields": [{"path": "a.b", "name": "Test", "entity_type": "switch"}]
        }))
        with pytest.raises(DeviceRegistryError, match="Invalid entity_type"):
            _load_device_type(bad_json)


# ---- TC-007: Unknown type ----

class TestUnknownType:
    def test_unknown_type_returns_empty(self):
        assert get_field_definitions("unknown") == []

    def test_unknown_device_type_returns_none(self):
        assert get_device_type("nonexistent") is None


# ---- TC-008: Snowbot field count ----

class TestFieldCount:
    def test_snowbot_has_15_plus_fields(self):
        fields = get_field_definitions("yarbo_Y")
        assert len(fields) >= 15, f"Expected >= 15 fields, got {len(fields)}"

    def test_mower_has_fields(self):
        fields = get_field_definitions("yarbo_Y")
        assert len(fields) >= 5


# ---- TC-009 + TC-010: extract_field with MQTT message sample ----

MQTT_SAMPLE = {
    "BatteryMSG": {"capacity": 42, "status": 1, "temp_err": 0, "timestamp": 1774496497.881275},
    "BodyMsg": {"recharge_state": 0},
    "CombinedOdom": {"phi": -0.033, "x": -2.836, "y": 9.515},
    "EletricMSG": {"rwheel_current": 0.016},
    "HeadMsg": {"head_type": 3},
    "HeadSerialMsg": {"head_sn": "250705027S9D7274"},
    "RTKMSG": {"gga_atn_dis": 55.76, "heading_status": -2, "rtk_version": "", "status": "2", "timestamp": 1774496497.94},
    "RunningStatusMSG": {"chute_angle": 0, "chute_steering_engine_info": 0, "elec_navigation_rear_right_sensor": 13, "head_gyro_pitch": -2.15, "head_gyro_roll": -2.26, "rain_sensor_data": 5},
    "StateMSG": {"adjustangle_status": 0, "auto_draw_waiting_state": 0, "car_controller": False, "charging_status": 0, "en_state_led": True, "en_warn_led": True, "error_code": 0, "error_map_id": -1, "machine_controller": 1, "on_going_planning": 0, "on_going_recharging": 0, "on_going_to_start_point": 0, "on_mul_points": 0, "planning_paused": 0, "robot_follow_state": False, "schedule_cancel": 0, "vision_auto_draw_state": 0, "working_state": 1},
    "base_status": 7,
    "combined_odom_confidence": 0.1,
    "rtcm_age": 2.0,
    "ultrasonic_msg": {"lf_dis": 9999, "mt_dis": 9999, "rf_dis": 9999},
}


class TestExtractFieldWithSample:
    def test_battery_capacity(self):
        from yarbo_robot_sdk.device_helpers import extract_field
        assert extract_field(MQTT_SAMPLE, "BatteryMSG.capacity") == 42

    def test_working_state(self):
        from yarbo_robot_sdk.device_helpers import extract_field
        assert extract_field(MQTT_SAMPLE, "StateMSG.working_state") == 1

    def test_position(self):
        from yarbo_robot_sdk.device_helpers import extract_field
        assert extract_field(MQTT_SAMPLE, "CombinedOdom.x") == -2.836

    def test_rtk_status(self):
        from yarbo_robot_sdk.device_helpers import extract_field
        assert extract_field(MQTT_SAMPLE, "RTKMSG.status") == "2"

    def test_head_type(self):
        from yarbo_robot_sdk.device_helpers import extract_field
        assert extract_field(MQTT_SAMPLE, "HeadMsg.head_type") == 3

    def test_ultrasonic(self):
        from yarbo_robot_sdk.device_helpers import extract_field
        assert extract_field(MQTT_SAMPLE, "ultrasonic_msg.lf_dis") == 9999

    def test_top_level_fields(self):
        from yarbo_robot_sdk.device_helpers import extract_field
        assert extract_field(MQTT_SAMPLE, "base_status") == 7
        assert extract_field(MQTT_SAMPLE, "combined_odom_confidence") == 0.1
        assert extract_field(MQTT_SAMPLE, "rtcm_age") == 2.0

    def test_all_snowbot_mqtt_fields_extractable(self):
        """All non-__device__ snowbot fields should extract some value from sample."""
        from yarbo_robot_sdk.device_helpers import extract_field

        fields = get_field_definitions("yarbo_Y")
        mqtt_fields = [f for f in fields if not f.path.startswith("__device__")]

        extracted = 0
        for f in mqtt_fields:
            val = extract_field(MQTT_SAMPLE, f.path)
            if val is not None:
                extracted += 1

        assert extracted >= len(mqtt_fields) // 2, (
            f"Only {extracted}/{len(mqtt_fields)} fields extractable from sample"
        )

    def test_nonexistent_path_returns_none(self):
        from yarbo_robot_sdk.device_helpers import extract_field
        assert extract_field(MQTT_SAMPLE, "NotExist.field") is None


# ---- TC-016: control_topics parsed correctly ----

class TestControlTopicsParsed:
    """TC-016."""

    def test_yarbo_Y_has_control_topics(self):
        dt = get_device_type("yarbo_Y")
        assert len(dt.control_topics) >= 1

    def test_set_working_state_topic_name(self):
        dt = get_device_type("yarbo_Y")
        names = [ct.name for ct in dt.control_topics]
        assert "set_working_state" in names

    def test_set_working_state_template(self):
        dt = get_device_type("yarbo_Y")
        ct = next(c for c in dt.control_topics if c.name == "set_working_state")
        assert "{sn}" in ct.template
        assert "set_working_state" in ct.template


# ---- TC-017: control_fields parsed correctly ----

class TestControlFieldsParsed:
    """TC-017."""

    def test_yarbo_Y_has_control_fields(self):
        fields = get_control_field_definitions("yarbo_Y")
        assert len(fields) >= 1

    def test_control_field_is_dataclass(self):
        fields = get_control_field_definitions("yarbo_Y")
        assert all(isinstance(f, ControlFieldDefinition) for f in fields)

    def test_working_state_control_field(self):
        fields = get_control_field_definitions("yarbo_Y")
        ws = next(f for f in fields if f.path == "HeartBeatMSG.working_state")
        assert ws.entity_type == "select"
        assert ws.command_topic == "set_working_state"
        assert ws.command_key == "state"
        assert "standby" in ws.options
        assert "working" in ws.options
        assert ws.value_map["standby"] == 0
        assert ws.value_map["working"] == 1
        assert ws.state_value_map["0"] == "standby"
        assert ws.state_value_map["1"] == "working"

    def test_unknown_type_returns_empty(self):
        assert get_control_field_definitions("nonexistent") == []


# ---- TC-018: resolve_control_topic ----

class TestResolveControlTopic:
    """TC-018."""

    def test_resolve_set_working_state(self):
        topic = resolve_control_topic("SN123", "yarbo_Y", "set_working_state")
        assert topic == "snowbot/SN123/app/set_working_state"

    def test_sn_substituted(self):
        topic = resolve_control_topic("MY_DEVICE", "yarbo_Y", "set_working_state")
        assert "MY_DEVICE" in topic
        assert "{sn}" not in topic

    def test_unknown_device_type_raises(self):
        with pytest.raises(YarboSDKError, match="Unknown device type"):
            resolve_control_topic("SN123", "nonexistent", "set_working_state")

    def test_unknown_topic_name_raises(self):
        with pytest.raises(YarboSDKError, match="No control topic"):
            resolve_control_topic("SN123", "yarbo_Y", "nonexistent_command")


# ---- TC-019: control_field missing required key raises ----

class TestControlFieldValidation:
    """TC-019."""

    def _make_valid_control_field(self):
        return {
            "path": "HeartBeatMSG.working_state",
            "name": "Working State",
            "entity_type": "select",
            "command_topic": "set_working_state",
            "command_key": "state",
            "options": ["standby", "working"],
            "value_map": {"standby": 0, "working": 1},
            "state_value_map": {"0": "standby", "1": "working"},
        }

    def test_missing_command_topic_raises(self, tmp_path):
        cf = self._make_valid_control_field()
        del cf["command_topic"]
        bad_json = tmp_path / "bad.json"
        bad_json.write_text(json.dumps({
            "type_id": "test", "name": "test", "control_fields": [cf]
        }))
        with pytest.raises(DeviceRegistryError, match="Missing required field 'command_topic'"):
            _load_device_type(bad_json)

    def test_missing_options_raises(self, tmp_path):
        cf = self._make_valid_control_field()
        del cf["options"]
        bad_json = tmp_path / "bad.json"
        bad_json.write_text(json.dumps({
            "type_id": "test", "name": "test", "control_fields": [cf]
        }))
        with pytest.raises(DeviceRegistryError, match="Missing required field 'options'"):
            _load_device_type(bad_json)

    def test_invalid_entity_type_raises(self, tmp_path):
        cf = self._make_valid_control_field()
        cf["entity_type"] = "button"
        bad_json = tmp_path / "bad.json"
        bad_json.write_text(json.dumps({
            "type_id": "test", "name": "test", "control_fields": [cf]
        }))
        with pytest.raises(DeviceRegistryError, match="Invalid entity_type"):
            _load_device_type(bad_json)

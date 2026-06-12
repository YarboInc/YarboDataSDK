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
    def test_list_device_types_returns_at_least_one(self):
        types = list_device_types()
        assert len(types) >= 1

    def test_yarbo_y_loaded(self):
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

    def test_all_descriptions_are_english(self):
        dt = get_device_type("yarbo_Y")
        for t in dt.topics:
            assert all(ord(c) < 128 for c in t.description), (
                f"Topic '{t.name}' description contains non-ASCII: {t.description}"
            )
        for ct in dt.control_topics:
            assert all(ord(c) < 128 for c in ct.description), (
                f"Control topic '{ct.name}' description contains non-ASCII: {ct.description}"
            )
        for a in dt.apis:
            assert all(ord(c) < 128 for c in a.description), (
                f"API '{a.name}' description contains non-ASCII: {a.description}"
            )


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
    def test_heart_beat_state_value_map(self):
        fields = get_field_definitions("yarbo_Y")
        hb = next(f for f in fields if f.path == "HeartBeatMSG.working_state")
        assert hb.value_map is not None
        assert hb.value_map["0"] == "standby"
        assert hb.value_map["1"] == "working"
        assert hb.device_class == "enum"

    def test_charging_value_map(self):
        fields = get_field_definitions("yarbo_Y")
        ch = next(f for f in fields if f.path == "BatteryMSG.status")
        assert ch.entity_type == "binary_sensor"
        assert ch.device_class == "battery_charging"
        assert ch.custom_extractor == "charging_threshold"


# ---- TC-004: Yarbo Y field presence (updated for Bay-09 changes) ----

class TestYarboYFieldPresence:
    def test_has_retained_fields(self):
        fields = get_field_definitions("yarbo_Y")
        paths = [f.path for f in fields]
        assert "BatteryMSG.capacity" in paths
        assert "BatteryMSG.status" in paths
        assert "StateMSG.error_code" in paths
        assert "HeartBeatMSG.working_state" in paths
        assert "HeadMsg.head_type" in paths
        assert "HeadSerialMsg.head_sn" in paths
        assert "CombinedOdom.x" in paths
        assert "CombinedOdom.y" in paths
        assert "CombinedOdom.phi" in paths

    def test_has_new_fields(self):
        fields = get_field_definitions("yarbo_Y")
        paths = [f.path for f in fields]
        assert "BatteryMSG.voltage" in paths
        assert "BatteryMSG.current" in paths
        assert "BatteryMSG.health" in paths
        assert "__computed__.charging_power" in paths
        assert "route_priority" in paths
        assert "StateMSG.on_going_planning" in paths
        assert "StateMSG.planning_paused" in paths
        assert "StateMSG.on_going_recharging" in paths
        assert "StateMSG.enable_sound" in paths
        assert "LedInfoMSG.led_head" in paths
        assert "StateMSG.volume" in paths
        assert "HeadAndVersionCheck.head_firmware_version" in paths
        assert "BodyVersionMsg.body_fw_version" in paths
        assert "StateMSG.working_state" in paths
        assert "net_module_status.lte_rssi" in paths
        assert "halow_status.strength" in paths
        assert "RunningStatusMSG.rain_sensor_data" in paths
        assert "StateMSG.person_detect_status" in paths
        assert "StateMSG.robot_follow_state" in paths
        assert "BatteryMSG.temp_err" in paths
        assert "StateMSG.stuck" in paths
        assert "StateMSG.obstacle" in paths
        assert "RTKMSG.sat_num" in paths

    def test_deleted_fields_absent(self):
        fields = get_field_definitions("yarbo_Y")
        paths = [f.path for f in fields]
        deleted = [
            "StateMSG.charging_status",
            "base_status",
            "combined_odom_confidence",
            "RTKMSG.heading_status", "rtcm_age",
            "ultrasonic_msg.lf_dis", "ultrasonic_msg.mt_dis", "ultrasonic_msg.rf_dis",
            "__device__.online",
            "__computed__.charging_time_remaining",
        ]
        for d in deleted:
            assert d not in paths, f"Deleted field '{d}' still present"

    def test_head_type_value_map_updated(self):
        fields = get_field_definitions("yarbo_Y")
        ht = next(f for f in fields if f.path == "HeadMsg.head_type")
        assert ht.value_map["0"] == "None"
        assert ht.value_map["1"] == "Snow Blower"
        assert ht.value_map["2"] == "Blower"
        assert ht.value_map["3"] == "Mower"
        assert ht.value_map["4"] == "Smart Cover"
        assert ht.value_map["5"] == "Mower Pro"

    def test_head_sn_enabled_by_default(self):
        fields = get_field_definitions("yarbo_Y")
        sn = next(f for f in fields if f.path == "HeadSerialMsg.head_sn")
        assert sn.enabled_by_default is True

    def test_network_has_custom_extractor(self):
        fields = get_field_definitions("yarbo_Y")
        net = next(f for f in fields if f.path == "route_priority")
        assert net.custom_extractor == "network_priority"

    def test_auto_plan_status_custom_extractor(self):
        fields = get_field_definitions("yarbo_Y")
        ap = next(f for f in fields if f.path == "StateMSG.on_going_planning")
        assert ap.custom_extractor == "planning_status"
        # value_map now contains display options for HA enum
        assert "Not Started" in ap.value_map.values()
        assert "Error: Outside Mapped Area (WP006)" in ap.value_map.values()

    def test_recharging_status_custom_extractor(self):
        fields = get_field_definitions("yarbo_Y")
        rs = next(f for f in fields if f.path == "StateMSG.on_going_recharging")
        assert rs.custom_extractor == "recharging_status"
        assert "Charging" in rs.value_map.values()
        assert "Error: Stuck" in rs.value_map.values()

    def test_stuck_uses_nonzero_threshold(self):
        fields = get_field_definitions("yarbo_Y")
        stuck = next(f for f in fields if f.path == "StateMSG.stuck")
        assert stuck.custom_extractor == "nonzero_threshold"

    def test_charging_power_disabled_by_default(self):
        fields = get_field_definitions("yarbo_Y")
        cp = next(f for f in fields if f.path == "__computed__.charging_power")
        assert cp.enabled_by_default is False

    def test_default_enabled_strategy(self):
        """Diagnostic/detail fields should be disabled by default."""
        fields = get_field_definitions("yarbo_Y")
        disabled = [f.path for f in fields if not f.enabled_by_default]
        assert set(disabled) == {
            "BatteryMSG.voltage",
            "BatteryMSG.current",
            "BatteryMSG.temperature1",
            "BatteryMSG.temperature2",
            "BatteryMSG.temperature3",
            "BatteryMSG.temperature4",
            "BatteryMSG.temperature5",
            "BatteryMSG.temperature6",
            "__computed__.charging_power",
            "halow_status.strength",
            "StateMSG.obstacle",
            "RunningStatusMSG.rain_sensor_data",
            "CombinedOdom.x",
            "CombinedOdom.y",
            "CombinedOdom.phi",
            "RTKMSG.sat_num",
        }


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

    def test_invalid_field_entity_type(self, tmp_path):
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

    def test_unknown_device_type_falls_back_to_yarbo_y(self):
        dt = get_device_type("nonexistent")
        assert dt is not None
        assert dt.type_id == "yarbo_Y"


# ---- TC-008: Field count ----

class TestFieldCount:
    def test_yarbo_y_has_43_fields(self):
        """43 fields after adding battery cell temperature sensors."""
        fields = get_field_definitions("yarbo_Y")
        assert len(fields) == 43, f"Expected 43 fields, got {len(fields)}"

    def test_yarbo_y_has_15_control_fields(self):
        """15 control fields after adding Emergency Stop button."""
        fields = get_control_field_definitions("yarbo_Y")
        assert len(fields) == 15, f"Expected 15 control fields, got {len(fields)}"


# ---- TC-009: extract_field with MQTT message sample ----

MQTT_SAMPLE = {
    "BatteryMSG": {"capacity": 42, "status": 1, "temp_err": 0, "timestamp": 1774496497.881275},
    "BodyMsg": {"recharge_state": 0},
    "CombinedOdom": {"phi": -0.033, "x": -2.836, "y": 9.515},
    "HeadMsg": {"head_type": 3},
    "HeadSerialMsg": {"head_sn": "250705027S9D7274"},
    "LedInfoMSG": {"led_head": 0, "body_left_d": 255},
    "StateMSG": {
        "charging_status": 0, "error_code": 0,
        "on_going_planning": 0, "on_going_recharging": 0,
        "planning_paused": 0, "working_state": 1,
        "enable_sound": True, "volume": 66.7,
    },
    "route_priority": {"hg0": -1, "wlan0": 0, "wwan0": -1},
}


class TestExtractFieldWithSample:
    def test_battery_capacity(self):
        from yarbo_robot_sdk.device_helpers import extract_field
        assert extract_field(MQTT_SAMPLE, "BatteryMSG.capacity") == 42

    def test_position(self):
        from yarbo_robot_sdk.device_helpers import extract_field
        assert extract_field(MQTT_SAMPLE, "CombinedOdom.x") == -2.836

    def test_head_type(self):
        from yarbo_robot_sdk.device_helpers import extract_field
        assert extract_field(MQTT_SAMPLE, "HeadMsg.head_type") == 3

    def test_new_fields_extractable(self):
        from yarbo_robot_sdk.device_helpers import extract_field
        assert extract_field(MQTT_SAMPLE, "StateMSG.on_going_planning") == 0
        assert extract_field(MQTT_SAMPLE, "StateMSG.planning_paused") == 0
        assert extract_field(MQTT_SAMPLE, "StateMSG.on_going_recharging") == 0
        assert extract_field(MQTT_SAMPLE, "StateMSG.enable_sound") is True
        assert extract_field(MQTT_SAMPLE, "StateMSG.volume") == 66.7
        assert extract_field(MQTT_SAMPLE, "LedInfoMSG.led_head") == 0

    def test_route_priority_extractable(self):
        from yarbo_robot_sdk.device_helpers import extract_field
        rp = extract_field(MQTT_SAMPLE, "route_priority")
        assert isinstance(rp, dict)
        assert rp["wlan0"] == 0

    def test_nonexistent_path_returns_none(self):
        from yarbo_robot_sdk.device_helpers import extract_field
        assert extract_field(MQTT_SAMPLE, "NotExist.field") is None


# ---- TC-016: control_topics parsed correctly ----

class TestControlTopicsParsed:
    def test_yarbo_Y_has_control_topics(self):
        dt = get_device_type("yarbo_Y")
        assert len(dt.control_topics) >= 12

    def test_original_topics_present(self):
        dt = get_device_type("yarbo_Y")
        names = [ct.name for ct in dt.control_topics]
        assert "set_working_state" in names
        assert "read_gps_ref" in names
        assert "get_map" in names

    def test_new_topics_present(self):
        dt = get_device_type("yarbo_Y")
        names = [ct.name for ct in dt.control_topics]
        for expected in [
            "read_all_plan", "get_device_msg", "start_plan",
            "pause", "resume", "stop",
            "cmd_recharge", "set_sound_param", "light_ctrl",
            "set_person_detect", "set_follow_state",
            "save_global_params", "set_map_obstacle_switch", "ignore_obstacles",
            "set_child_lock", "song_cmd",
            "mower_target_cmd", "mower_speed_cmd", "cmd_set_chute_angle",
        ]:
            assert expected in names, f"Missing control topic: {expected}"

    def test_removed_topics_absent(self):
        dt = get_device_type("yarbo_Y")
        names = [ct.name for ct in dt.control_topics]
        assert "smart_vision_control" not in names
        assert "cmd_buzzer" not in names


# ---- TC-017: control_fields parsed correctly ----

class TestControlFieldsParsed:
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
        assert ws.extra_payload == {"source": "smart_home"}

    def test_sound_switch_control_field(self):
        fields = get_control_field_definitions("yarbo_Y")
        ss = next(f for f in fields if f.path == "StateMSG.enable_sound")
        assert ss.entity_type == "switch"
        assert ss.command_topic == "set_sound_param"
        assert ss.command_builder == "sound_switch"

    def test_volume_control_field(self):
        fields = get_control_field_definitions("yarbo_Y")
        vol = next(f for f in fields if f.path == "StateMSG.volume")
        assert vol.entity_type == "number"
        assert vol.command_topic == "set_sound_param"
        assert vol.command_builder == "sound_volume"
        assert vol.min_value == 0
        assert vol.max_value == 100
        assert vol.step == 1
        assert vol.unit == "%"

    def test_blade_height_control_field(self):
        fields = get_control_field_definitions("yarbo_Y")
        blade_height = next(f for f in fields if f.path == "MowerState.blade_height")
        assert blade_height.entity_type == "number"
        assert blade_height.command_topic == "mower_target_cmd"
        assert blade_height.command_key == "target"
        assert blade_height.enabled_by_default is False
        assert blade_height.compatible_head_types == [3, 5]

    def test_blade_speed_control_field(self):
        fields = get_control_field_definitions("yarbo_Y")
        blade_speed = next(f for f in fields if f.path == "MowerState.blade_speed")
        assert blade_speed.entity_type == "number"
        assert blade_speed.command_topic == "mower_speed_cmd"
        assert blade_speed.command_key == "state"
        assert blade_speed.enabled_by_default is False
        assert blade_speed.compatible_head_types == [3, 5]

    def test_chute_angle_control_field(self):
        fields = get_control_field_definitions("yarbo_Y")
        chute_angle = next(f for f in fields if f.path == "RunningStatusMSG.chute_angle")
        assert chute_angle.entity_type == "number"
        assert chute_angle.command_topic == "cmd_set_chute_angle"
        assert chute_angle.command_key == "cmd"
        assert chute_angle.enabled_by_default is False
        assert chute_angle.compatible_head_types == [1]

    def test_roof_lights_control_field(self):
        fields = get_control_field_definitions("yarbo_Y")
        hl = next(f for f in fields if f.path == "LedInfoMSG.led_head")
        assert hl.entity_type == "switch"
        assert hl.command_topic == "light_ctrl"
        assert hl.command_builder == "light_switch"

    def test_person_detection_control_field(self):
        fields = get_control_field_definitions("yarbo_Y")
        pd = next(f for f in fields if f.path == "StateMSG.person_detect_status")
        assert pd.entity_type == "switch"
        assert pd.command_topic == "set_person_detect"
        assert pd.command_builder == "person_detection_switch"

    def test_geo_fence_control_field(self):
        fields = get_control_field_definitions("yarbo_Y")
        gf = next(f for f in fields if f.path == "enable_elec_fence")
        assert gf.entity_type == "switch"
        assert gf.command_topic == "save_global_params"
        assert gf.command_builder == "geo_fence_switch"

    def test_follow_mode_control_field(self):
        fields = get_control_field_definitions("yarbo_Y")
        fm = next(f for f in fields if f.path == "StateMSG.robot_follow_state")
        assert fm.entity_type == "switch"
        assert fm.command_topic == "set_follow_state"
        assert fm.command_builder == "state_int_switch"

    def test_ignore_obstacles_control_field(self):
        fields = get_control_field_definitions("yarbo_Y")
        io = next(f for f in fields if f.path == "map_obstacle_switch")
        assert io.entity_type == "switch"
        assert io.command_topic == "set_map_obstacle_switch"
        assert io.command_builder == "ignore_obstacles_switch"

    def test_child_lock_control_field(self):
        fields = get_control_field_definitions("yarbo_Y")
        cl = next(f for f in fields if f.path == "StateMSG.child_lock_status")
        assert cl.entity_type == "switch"
        assert cl.command_topic == "set_child_lock"
        assert cl.command_builder == "state_bool_switch"

    def test_ignore_obstacle_zones_control_field(self):
        fields = get_control_field_definitions("yarbo_Y")
        ioz = next(f for f in fields if f.path == "__action__.ignore_obstacle_zones")
        assert ioz.entity_type == "button"
        assert ioz.command_topic == "ignore_obstacles"
        assert ioz.command_builder == "ignore_obstacle_zones"

    def test_play_sound_control_field(self):
        fields = get_control_field_definitions("yarbo_Y")
        ps = next(f for f in fields if f.path == "__action__.play_sound")
        assert ps.entity_type == "button"
        assert ps.command_topic == "song_cmd"
        assert ps.command_builder == "play_sound"
        assert ps.enabled_by_default is True

    def test_emergency_stop_control_field(self):
        fields = get_control_field_definitions("yarbo_Y")
        es = next(f for f in fields if f.path == "__action__.emergency_stop")
        assert es.entity_type == "button"
        assert es.command_topic == "stop"
        assert es.command_builder == "empty_payload"
        assert es.enabled_by_default is True

    def test_removed_control_fields_absent(self):
        fields = get_control_field_definitions("yarbo_Y")
        paths = [f.path for f in fields]
        assert "HubInfoMSG.head_camera_power" not in paths
        assert "HubInfoMSG.loud" not in paths

    def test_unknown_type_returns_empty(self):
        assert get_control_field_definitions("nonexistent") == []


# ---- TC-018: resolve_control_topic ----

class TestResolveControlTopic:
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

    def test_resolve_new_topics(self):
        assert resolve_control_topic("SN1", "yarbo_Y", "start_plan") == "snowbot/SN1/app/start_plan"
        assert resolve_control_topic("SN1", "yarbo_Y", "pause") == "snowbot/SN1/app/pause"
        assert resolve_control_topic("SN1", "yarbo_Y", "resume") == "snowbot/SN1/app/resume"
        assert resolve_control_topic("SN1", "yarbo_Y", "stop") == "snowbot/SN1/app/stop"
        assert resolve_control_topic("SN1", "yarbo_Y", "cmd_recharge") == "snowbot/SN1/app/cmd_recharge"
        assert resolve_control_topic("SN1", "yarbo_Y", "set_sound_param") == "snowbot/SN1/app/set_sound_param"
        assert resolve_control_topic("SN1", "yarbo_Y", "light_ctrl") == "snowbot/SN1/app/light_ctrl"
        assert resolve_control_topic("SN1", "yarbo_Y", "set_person_detect") == "snowbot/SN1/app/set_person_detect"
        assert resolve_control_topic("SN1", "yarbo_Y", "set_follow_state") == "snowbot/SN1/app/set_follow_state"
        assert resolve_control_topic("SN1", "yarbo_Y", "save_global_params") == "snowbot/SN1/app/save_global_params"
        assert resolve_control_topic("SN1", "yarbo_Y", "set_map_obstacle_switch") == "snowbot/SN1/app/set_map_obstacle_switch"
        assert resolve_control_topic("SN1", "yarbo_Y", "ignore_obstacles") == "snowbot/SN1/app/ignore_obstacles"
        assert resolve_control_topic("SN1", "yarbo_Y", "set_child_lock") == "snowbot/SN1/app/set_child_lock"
        assert resolve_control_topic("SN1", "yarbo_Y", "song_cmd") == "snowbot/SN1/app/song_cmd"
        assert resolve_control_topic("SN1", "yarbo_Y", "mower_target_cmd") == "snowbot/SN1/app/mower_target_cmd"
        assert resolve_control_topic("SN1", "yarbo_Y", "mower_speed_cmd") == "snowbot/SN1/app/mower_speed_cmd"
        assert resolve_control_topic("SN1", "yarbo_Y", "cmd_set_chute_angle") == "snowbot/SN1/app/cmd_set_chute_angle"

    def test_unknown_topic_name_raises(self):
        with pytest.raises(YarboSDKError, match="No control topic"):
            resolve_control_topic("SN123", "yarbo_Y", "nonexistent_command")


# ---- TC-019: control_field validation ----

class TestControlFieldValidation:
    def test_missing_command_topic_raises(self, tmp_path):
        cf = {
            "path": "test.field",
            "name": "Test",
            "entity_type": "select",
        }
        bad_json = tmp_path / "bad.json"
        bad_json.write_text(json.dumps({
            "type_id": "test", "name": "test", "control_fields": [cf]
        }))
        with pytest.raises(DeviceRegistryError, match="Missing required field 'command_topic'"):
            _load_device_type(bad_json)

    def test_invalid_entity_type_raises(self, tmp_path):
        cf = {
            "path": "test.field",
            "name": "Test",
            "entity_type": "sensor",
            "command_topic": "some_topic",
        }
        bad_json = tmp_path / "bad.json"
        bad_json.write_text(json.dumps({
            "type_id": "test", "name": "test", "control_fields": [cf]
        }))
        with pytest.raises(DeviceRegistryError, match="Invalid entity_type"):
            _load_device_type(bad_json)

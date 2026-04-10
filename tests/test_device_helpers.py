"""Tests for device_helpers."""

import pytest

from yarbo_robot_sdk.device_helpers import (
    convert_map_to_geojson,
    extract_active_network,
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
        assert "HeartBeatMSG.working_state" in paths


class TestExtractActiveNetwork:
    """TC-001 from TEST-CASE-Bay-09."""

    def test_wifi_active(self):
        assert extract_active_network({"hg0": -1, "wlan0": 600, "wwan0": -1}) == "Wifi"

    def test_halow_active(self):
        assert extract_active_network({"hg0": 10, "wlan0": -1, "wwan0": -1}) == "Halow"

    def test_4g_active(self):
        assert extract_active_network({"hg0": -1, "wlan0": -1, "wwan0": 100}) == "4G"

    def test_all_inactive(self):
        assert extract_active_network({"hg0": -1, "wlan0": -1, "wwan0": -1}) is None

    def test_empty_dict(self):
        assert extract_active_network({}) is None

    def test_none_input(self):
        assert extract_active_network(None) is None

    def test_non_dict_input(self):
        assert extract_active_network("not a dict") is None

    def test_lowest_priority_wins(self):
        """Lowest non-negative value is the active network."""
        assert extract_active_network({"hg0": 10, "wlan0": 600, "wwan0": -1}) == "Halow"

    def test_zero_priority(self):
        """Priority 0 is valid and lowest possible."""
        assert extract_active_network({"hg0": -1, "wlan0": 0, "wwan0": 100}) == "Wifi"


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


# ---- get_map GeoJSON conversion tests ----

# Sample get_map response data (truncated from real device response)
GET_MAP_SAMPLE = {
    "areas": [
        {
            "id": 3,
            "name": "Area 2",
            "range": [
                {"phi": 1.478, "x": -36.909, "y": -30.227},
                {"phi": 1.477, "x": -36.875, "y": -25.459},
                {"phi": -0.295, "x": -32.335, "y": -26.141},
            ],
            "ref": {"latitude": 22.613023680368677, "longitude": 114.04911050736438},
        },
    ],
    "pathways": [
        {
            "id": 1,
            "name": "Pathway 1",
            "range": [
                {"phi": 0.152, "x": 0.236, "y": 17.218},
                {"phi": 0.153, "x": 0.677, "y": 17.303},
            ],
            "ref": {"latitude": 22.613023680368677, "longitude": 114.04911050736438},
        },
    ],
    "sidewalks": [],
    "deadends": [],
    "nogozones": [],
    "novisionzones": [],
    "elec_fence": [],
    "chargingData": {
        "chargingPoint": {"phi": 0.0, "x": 0.0, "y": 0.0},
        "startPoint": {"phi": 0.0, "x": 1.0, "y": 0.0},
        "enable": True,
        "hasChargingStation": 0,
        "id": 1,
    },
    "allchargingData": [],
}


class TestConvertMapToGeoJson:
    def test_returns_feature_collection(self):
        result = convert_map_to_geojson(GET_MAP_SAMPLE)
        assert result["type"] == "FeatureCollection"
        assert "features" in result

    def test_area_becomes_polygon(self):
        result = convert_map_to_geojson(GET_MAP_SAMPLE)
        area_features = [
            f for f in result["features"]
            if f["properties"]["zone_type"] == "areas"
        ]
        assert len(area_features) == 1
        f = area_features[0]
        assert f["geometry"]["type"] == "Polygon"
        assert f["properties"]["id"] == 3
        assert f["properties"]["name"] == "Area 2"

    def test_polygon_ring_is_closed(self):
        result = convert_map_to_geojson(GET_MAP_SAMPLE)
        area_features = [
            f for f in result["features"]
            if f["properties"]["zone_type"] == "areas"
        ]
        coords = area_features[0]["geometry"]["coordinates"][0]
        assert coords[0] == coords[-1], "Polygon ring must be closed"

    def test_coordinates_are_lon_lat_order(self):
        """GeoJSON spec requires [longitude, latitude] order."""
        result = convert_map_to_geojson(GET_MAP_SAMPLE)
        area_features = [
            f for f in result["features"]
            if f["properties"]["zone_type"] == "areas"
        ]
        first_coord = area_features[0]["geometry"]["coordinates"][0][0]
        # longitude (~114) should come before latitude (~22)
        assert first_coord[0] > 100, f"Expected longitude first, got {first_coord}"
        assert first_coord[1] < 30, f"Expected latitude second, got {first_coord}"

    def test_pathway_becomes_linestring(self):
        result = convert_map_to_geojson(GET_MAP_SAMPLE)
        pathway_features = [
            f for f in result["features"]
            if f["properties"]["zone_type"] == "pathways"
        ]
        assert len(pathway_features) == 1
        f = pathway_features[0]
        assert f["geometry"]["type"] == "LineString"
        assert len(f["geometry"]["coordinates"]) == 2
        assert f["properties"]["name"] == "Pathway 1"

    def test_charging_becomes_point_with_fallback_ref(self):
        # chargingData has no ref, so needs fallback
        fallback = {"ref": {"latitude": 22.613, "longitude": 114.049}}
        result = convert_map_to_geojson(GET_MAP_SAMPLE, fallback_ref=fallback)
        charging_features = [
            f for f in result["features"]
            if f["properties"]["zone_type"] == "charging"
        ]
        assert len(charging_features) == 1
        f = charging_features[0]
        assert f["geometry"]["type"] == "Point"
        assert f["properties"]["enable"] is True

    def test_charging_skipped_without_ref(self):
        # chargingData has no ref and no fallback → skipped
        result = convert_map_to_geojson(GET_MAP_SAMPLE)
        charging_features = [
            f for f in result["features"]
            if f["properties"]["zone_type"] == "charging"
        ]
        assert len(charging_features) == 0

    def test_empty_data(self):
        result = convert_map_to_geojson({})
        assert result["type"] == "FeatureCollection"
        assert result["features"] == []

    def test_area_with_too_few_points_skipped(self):
        data = {
            "areas": [
                {
                    "id": 99,
                    "name": "Tiny",
                    "range": [{"x": 0, "y": 0}],
                    "ref": {"latitude": 22.0, "longitude": 114.0},
                }
            ]
        }
        result = convert_map_to_geojson(data)
        assert len(result["features"]) == 0

    def test_coordinates_rounded_to_7_decimals(self):
        result = convert_map_to_geojson(GET_MAP_SAMPLE)
        area_features = [
            f for f in result["features"]
            if f["properties"]["zone_type"] == "areas"
        ]
        for coord in area_features[0]["geometry"]["coordinates"][0]:
            lon_str = str(coord[0])
            lat_str = str(coord[1])
            if "." in lon_str:
                assert len(lon_str.split(".")[1]) <= 7
            if "." in lat_str:
                assert len(lat_str.split(".")[1]) <= 7

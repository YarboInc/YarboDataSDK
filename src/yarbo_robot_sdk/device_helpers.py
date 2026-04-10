"""High-level device helpers — resolve topics, extract fields, coordinate conversion."""

import math
from typing import Any, Optional

from yarbo_robot_sdk.device_registry import get_device_type
from yarbo_robot_sdk.exceptions import YarboSDKError


def resolve_device_msg_topic(sn: str, type_id: str) -> str:
    """Look up the DeviceMSG topic template for a device type and substitute the SN.

    Args:
        sn: Device serial number.
        type_id: Device type ID (e.g. "mower", "snowbot").

    Returns:
        Resolved topic string (e.g. "snowbot/SN001/device/DeviceMSG").

    Raises:
        YarboSDKError: If device type is unknown or has no device_msg topic.
    """
    device_type = get_device_type(type_id)
    if device_type is None:
        raise YarboSDKError(f"Unknown device type: {type_id}")
    for topic in device_type.topics:
        if topic.name == "device_msg":
            return topic.template.replace("{sn}", sn)
    raise YarboSDKError(f"No device_msg topic defined for device type: {type_id}")


def resolve_topic_by_name(sn: str, type_id: str, topic_name: str) -> str:
    """Look up a topic template by name for a device type and substitute the SN.

    Args:
        sn: Device serial number.
        type_id: Device type ID.
        topic_name: The topic name to look up (e.g. "heart_beat", "device_msg").

    Returns:
        Resolved topic string with {sn} substituted.

    Raises:
        YarboSDKError: If device type is unknown or topic name is not found.
    """
    device_type = get_device_type(type_id)
    if device_type is None:
        raise YarboSDKError(f"Unknown device type: {type_id}")
    for topic in device_type.topics:
        if topic.name == topic_name:
            return topic.template.replace("{sn}", sn)
    raise YarboSDKError(
        f"No topic '{topic_name}' defined for device type: {type_id}"
    )


NETWORK_INTERFACE_MAP = {"hg0": "Halow", "wlan0": "Wifi", "wwan0": "4G"}


def extract_active_network(route_priority: Any) -> str | None:
    """Extract the active network type from a route_priority object.

    The route_priority object contains interface names (hg0, wlan0, wwan0)
    mapped to priority values. A value of -1 means the interface is not
    available. Among available interfaces (priority >= 0), the one with
    the lowest value is the active network.

    Args:
        route_priority: Dict with keys hg0/wlan0/wwan0 and int priority values.

    Returns:
        "Halow", "Wifi", "4G", or None if no active interface found.
    """
    if not isinstance(route_priority, dict):
        return None
    best_iface = None
    best_priority = None
    for iface, display_name in NETWORK_INTERFACE_MAP.items():
        val = route_priority.get(iface)
        if not isinstance(val, (int, float)) or val < 0:
            continue
        if best_priority is None or val < best_priority:
            best_iface = display_name
            best_priority = val
    return best_iface


def extract_field(data: dict, field_path: str) -> Any:
    """Extract a value from a nested dict using dot-separated path.

    Args:
        data: Nested dictionary (e.g. MQTT message payload).
        field_path: Dot-separated key path (e.g. "BatteryMSG.capacity").

    Returns:
        The value at the path, or None if any key is missing.
    """
    current = data
    for key in field_path.split("."):
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


# Meters per degree of latitude (constant approximation for small distances)
_METERS_PER_DEGREE_LAT = 111320.0


def convert_local_to_gps(
    ref_lat: float,
    ref_lon: float,
    local_x: float,
    local_y: float,
) -> tuple[float, float]:
    """Convert local odometry coordinates to absolute GPS coordinates.

    The device uses a local coordinate system where:
    - X positive direction is West
    - Y positive direction is North

    Args:
        ref_lat: GPS reference origin latitude (degrees).
        ref_lon: GPS reference origin longitude (degrees).
        local_x: Local X coordinate in meters (positive = West).
        local_y: Local Y coordinate in meters (positive = North).

    Returns:
        Tuple of (latitude, longitude) in degrees.
    """
    ref_lat_rad = math.radians(ref_lat)
    meters_per_degree_lon = _METERS_PER_DEGREE_LAT * math.cos(ref_lat_rad)

    lat = ref_lat + (local_y / _METERS_PER_DEGREE_LAT)
    lon = ref_lon - (local_x / meters_per_degree_lon)
    return (lat, lon)


def convert_map_to_geojson(
    map_data: dict,
    fallback_ref: Optional[dict] = None,
) -> dict:
    """Convert raw get_map response data to a GeoJSON FeatureCollection.

    Each zone type is converted to the appropriate GeoJSON geometry:
    - areas, nogozones, novisionzones, elec_fence → Polygon
    - pathways, sidewalks, deadends → LineString
    - chargingData / allchargingData → Point

    Coordinates are converted from local (x, y) to GPS (lon, lat) using each
    zone's own ``ref`` GPS reference point.

    Args:
        map_data: The ``data`` dict from a get_map data_feedback response.
        fallback_ref: Optional GPS reference ``{"ref": {"latitude": ...,
            "longitude": ...}}`` used when a zone lacks its own ref (e.g.
            chargingData). If *None*, zones without a ref are skipped.

    Returns:
        A GeoJSON FeatureCollection dict.
    """
    features: list[dict] = []

    # Polygon zone types
    polygon_types = ["areas", "nogozones", "novisionzones", "elec_fence"]
    for zone_type in polygon_types:
        for zone in map_data.get(zone_type, []):
            feature = _zone_to_polygon_feature(zone, zone_type, fallback_ref)
            if feature is not None:
                features.append(feature)

    # LineString zone types
    line_types = ["pathways", "sidewalks", "deadends"]
    for zone_type in line_types:
        for zone in map_data.get(zone_type, []):
            feature = _zone_to_linestring_feature(zone, zone_type, fallback_ref)
            if feature is not None:
                features.append(feature)

    # Charging data (single + all)
    charging = map_data.get("chargingData")
    if charging is not None:
        feature = _charging_to_point_feature(charging, fallback_ref)
        if feature is not None:
            features.append(feature)

    for charging in map_data.get("allchargingData", []):
        feature = _charging_to_point_feature(charging, fallback_ref)
        if feature is not None:
            features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def _get_ref(zone: dict, fallback_ref: Optional[dict]) -> Optional[tuple[float, float]]:
    """Extract (ref_lat, ref_lon) from a zone's ref or fallback."""
    ref = zone.get("ref", {})
    lat = ref.get("latitude")
    lon = ref.get("longitude")
    if lat is not None and lon is not None and lat != 0.0 and lon != 0.0:
        return (lat, lon)
    if fallback_ref is not None:
        fb = fallback_ref.get("ref", fallback_ref)
        lat = fb.get("latitude")
        lon = fb.get("longitude")
        if lat is not None and lon is not None:
            return (lat, lon)
    return None


def _local_point_to_lonlat(
    ref_lat: float, ref_lon: float, point: dict
) -> list[float]:
    """Convert a local {x, y} point to [longitude, latitude] (GeoJSON order)."""
    lat, lon = convert_local_to_gps(
        ref_lat, ref_lon, float(point.get("x", 0)), float(point.get("y", 0))
    )
    return [round(lon, 7), round(lat, 7)]


def _zone_to_polygon_feature(
    zone: dict, zone_type: str, fallback_ref: Optional[dict]
) -> Optional[dict]:
    """Convert a zone with a 'range' list of points to a GeoJSON Polygon feature."""
    points = zone.get("range", [])
    if len(points) < 3:
        return None
    ref = _get_ref(zone, fallback_ref)
    if ref is None:
        return None
    ref_lat, ref_lon = ref

    coords = [_local_point_to_lonlat(ref_lat, ref_lon, p) for p in points]
    # Close the polygon ring
    if coords[0] != coords[-1]:
        coords.append(coords[0])

    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [coords],
        },
        "properties": {
            "id": zone.get("id"),
            "name": zone.get("name", ""),
            "zone_type": zone_type,
        },
    }


def _zone_to_linestring_feature(
    zone: dict, zone_type: str, fallback_ref: Optional[dict]
) -> Optional[dict]:
    """Convert a zone with a 'range' list of points to a GeoJSON LineString feature."""
    points = zone.get("range", [])
    if len(points) < 2:
        return None
    ref = _get_ref(zone, fallback_ref)
    if ref is None:
        return None
    ref_lat, ref_lon = ref

    coords = [_local_point_to_lonlat(ref_lat, ref_lon, p) for p in points]

    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coords,
        },
        "properties": {
            "id": zone.get("id"),
            "name": zone.get("name", ""),
            "zone_type": zone_type,
        },
    }


def _charging_to_point_feature(
    charging: dict, fallback_ref: Optional[dict]
) -> Optional[dict]:
    """Convert chargingData to a GeoJSON Point feature."""
    cp = charging.get("chargingPoint")
    if cp is None:
        return None
    ref = _get_ref(charging, fallback_ref)
    if ref is None:
        return None
    ref_lat, ref_lon = ref

    coords = _local_point_to_lonlat(ref_lat, ref_lon, cp)

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": coords,
        },
        "properties": {
            "id": charging.get("id"),
            "name": charging.get("name", "Charging Station"),
            "zone_type": "charging",
            "enable": charging.get("enable"),
            "has_charging_station": charging.get("hasChargingStation"),
        },
    }

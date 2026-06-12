"""Typed module facades for the Yarbo modular platform."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from yarbo_robot_sdk.device_helpers import extract_field

_LOGGER = logging.getLogger(__name__)
from yarbo_robot_sdk.exceptions import YarboSDKError
from yarbo_robot_sdk.models import Device
from yarbo_robot_sdk.public_types import (
    CommandPayload,
    DataFeedbackCallback,
    DeviceData,
    StatusCallback,
)

DEFAULT_TYPE_ID = "yarbo_Y"


class _ClientProtocol(Protocol):
    """Subset of YarboClient used by module facades."""

    def subscribe_device_message(
        self, sn: str, type_id: str, callback: StatusCallback
    ) -> None: ...

    def subscribe_heart_beat(
        self, sn: str, type_id: str, callback: StatusCallback
    ) -> None: ...

    def subscribe_data_feedback(
        self,
        sn: str,
        type_id: str,
        callback: DataFeedbackCallback | None = None,
    ) -> None: ...

    def mqtt_publish_command(
        self, sn: str, type_id: str, command_topic_name: str, payload: CommandPayload
    ) -> None: ...

    def get_device_msg(
        self, sn: str, type_id: str, timeout: float = 10.0
    ) -> DeviceData: ...

    def read_gps_ref(
        self, sn: str, type_id: str, timeout: float = 10.0
    ) -> DeviceData: ...

    def get_map(
        self, sn: str, type_id: str, timeout: float = 30.0
    ) -> DeviceData: ...

    def read_all_plan(
        self, sn: str, type_id: str, timeout: float = 10.0
    ) -> DeviceData: ...

    def get_connect_wifi_name(
        self, sn: str, type_id: str, timeout: float = 10.0
    ) -> DeviceData: ...


class YarboModule:
    """Base facade for commands that belong to a named Yarbo module."""

    module_name = "module"
    compatible_head_types: tuple[int, ...] = ()

    def __init__(self, client: _ClientProtocol):
        self._client = client

    def matches_head_type(self, head_type: int | str | None) -> bool:
        """Return whether this module is compatible with a head type.

        Modules without a compatibility list are shared Core-style namespaces
        and are considered compatible with all head types.
        """
        if not self.compatible_head_types:
            return True
        try:
            return int(head_type) in self.compatible_head_types
        except (TypeError, ValueError):
            return False

    def validate_head_type(self, head_type: int | str | None) -> None:
        """Raise if this module is not compatible with the current head type."""
        if self.matches_head_type(head_type):
            return
        expected = ", ".join(str(v) for v in self.compatible_head_types)
        raise YarboSDKError(
            f"{self.module_name} module is unavailable for current Yarbo "
            f"head_type={head_type!r}; expected one of: {expected}"
        )

    def validate_device_data(self, device_data: DeviceData | None) -> None:
        """Validate compatibility from a DeviceMSG-like payload if provided."""
        if not self.compatible_head_types or device_data is None:
            return
        head_type = _extract_head_type(device_data)
        if head_type is None:
            return
        self.validate_head_type(head_type)

    def subscribe_device_message(
        self,
        sn: str,
        callback: StatusCallback,
        type_id: str = DEFAULT_TYPE_ID,
    ) -> None:
        """Subscribe to real-time status for this module's device."""
        self._client.subscribe_device_message(sn, type_id, callback)

    def subscribe_heart_beat(
        self,
        sn: str,
        callback: StatusCallback,
        type_id: str = DEFAULT_TYPE_ID,
    ) -> None:
        """Subscribe to heartbeat messages for this module's device."""
        self._client.subscribe_heart_beat(sn, type_id, callback)

    def subscribe_data_feedback(
        self,
        sn: str,
        callback: DataFeedbackCallback | None = None,
        type_id: str = DEFAULT_TYPE_ID,
    ) -> None:
        """Subscribe to command feedback responses for this module's device."""
        self._client.subscribe_data_feedback(sn, type_id, callback)

    def get_device_msg(
        self, sn: str, type_id: str = DEFAULT_TYPE_ID, timeout: float = 10.0
    ) -> DeviceData:
        """Request a full DeviceMSG snapshot."""
        return self._client.get_device_msg(sn, type_id, timeout)

    def read_gps_ref(
        self, sn: str, type_id: str = DEFAULT_TYPE_ID, timeout: float = 10.0
    ) -> DeviceData:
        """Request the GPS reference origin."""
        return self._client.read_gps_ref(sn, type_id, timeout)

    def get_map(
        self, sn: str, type_id: str = DEFAULT_TYPE_ID, timeout: float = 30.0
    ) -> DeviceData:
        """Request map and zone data."""
        return self._client.get_map(sn, type_id, timeout)

    def read_all_plan(
        self, sn: str, type_id: str = DEFAULT_TYPE_ID, timeout: float = 10.0
    ) -> DeviceData:
        """Request all auto plans."""
        return self._client.read_all_plan(sn, type_id, timeout)

    def get_connect_wifi_name(
        self, sn: str, type_id: str = DEFAULT_TYPE_ID, timeout: float = 10.0
    ) -> DeviceData:
        """Request connected Wi-Fi information."""
        return self._client.get_connect_wifi_name(sn, type_id, timeout)

    def set_working_state(
        self,
        sn: str,
        state: int,
        type_id: str = DEFAULT_TYPE_ID,
        source: str = "smart_home",
    ) -> None:
        """Set standby/working state. ``0`` is standby and ``1`` is working."""
        self._client.mqtt_publish_command(
            sn, type_id, "set_working_state", {"state": state, "source": source}
        )

    def publish_command(
        self,
        sn: str,
        command_topic_name: str,
        payload: CommandPayload,
        type_id: str = DEFAULT_TYPE_ID,
    ) -> None:
        """Publish a raw command under this module namespace."""
        self._client.mqtt_publish_command(sn, type_id, command_topic_name, payload)


class CoreModule(YarboModule):
    """Core Yarbo platform commands shared by all attachments."""

    module_name = "core"

    def start_plan(
        self,
        sn: str,
        plan_id: int,
        type_id: str = DEFAULT_TYPE_ID,
        start_percent: int = 0,
    ) -> None:
        """Start an auto plan."""
        payload = {"id": plan_id}
        if start_percent > 0:
            payload["percent"] = int(start_percent)
        self._client.mqtt_publish_command(
            sn,
            type_id,
            "start_plan",
            payload,
        )

    def pause(self, sn: str, type_id: str = DEFAULT_TYPE_ID) -> None:
        """Pause the current plan."""
        self._client.mqtt_publish_command(sn, type_id, "pause", {})

    def resume(self, sn: str, type_id: str = DEFAULT_TYPE_ID) -> None:
        """Resume the current plan."""
        self._client.mqtt_publish_command(sn, type_id, "resume", {})

    def stop(self, sn: str, type_id: str = DEFAULT_TYPE_ID) -> None:
        """Stop the current plan."""
        self._client.mqtt_publish_command(sn, type_id, "stop", {})

    def return_to_charge(self, sn: str, type_id: str = DEFAULT_TYPE_ID) -> None:
        """Return to the charging station (cmd=2 required by device firmware)."""
        self._client.mqtt_publish_command(sn, type_id, "cmd_recharge", {"cmd": 2})

    def song_cmd(
        self,
        sn: str,
        song_name: str = "find yarbo",
        type_id: str = DEFAULT_TYPE_ID,
    ) -> None:
        """Play a named sound on the device (default: find-Yarbo locator)."""
        self._client.mqtt_publish_command(
            sn, type_id, "song_cmd", {"song_name": song_name}
        )

    def set_sound_param(
        self,
        sn: str,
        enable: bool,
        vol: float,
        mode: int = 0,
        type_id: str = DEFAULT_TYPE_ID,
    ) -> None:
        """Enable or disable sound and set volume (0.0–1.0)."""
        self._client.mqtt_publish_command(
            sn, type_id, "set_sound_param", {"enable": enable, "vol": vol, "mode": mode}
        )

    def set_headlight(
        self,
        sn: str,
        on: bool,
        type_id: str = DEFAULT_TYPE_ID,
    ) -> None:
        """Turn the head light on or off."""
        self._client.mqtt_publish_command(
            sn, type_id, "light_ctrl", {"led_head": 1 if on else 0}
        )

    def set_child_lock(
        self,
        sn: str,
        enabled: bool,
        type_id: str = DEFAULT_TYPE_ID,
    ) -> None:
        """Enable or disable child lock."""
        self._client.mqtt_publish_command(
            sn, type_id, "set_child_lock", {"state": enabled}
        )

    def set_person_detect(
        self,
        sn: str,
        enabled: bool,
        type_id: str = DEFAULT_TYPE_ID,
    ) -> None:
        """Enable or disable person detection."""
        self._client.mqtt_publish_command(
            sn, type_id, "set_person_detect", {"state": 1 if enabled else 0}
        )

    def set_follow_state(
        self,
        sn: str,
        enabled: bool,
        type_id: str = DEFAULT_TYPE_ID,
    ) -> None:
        """Enable or disable follow mode."""
        self._client.mqtt_publish_command(
            sn, type_id, "set_follow_state", {"state": 1 if enabled else 0}
        )

    def save_global_params(
        self,
        sn: str,
        enable_elec_fence: bool,
        id: int = 1,
        type_id: str = DEFAULT_TYPE_ID,
    ) -> None:
        """Enable or disable the geo-fence."""
        self._client.mqtt_publish_command(
            sn,
            type_id,
            "save_global_params",
            {"id": id, "enable_elec_fence": enable_elec_fence},
        )

    def set_map_obstacle_switch(
        self,
        sn: str,
        enabled: bool,
        type_id: str = DEFAULT_TYPE_ID,
    ) -> None:
        """Enable or disable map obstacle avoidance."""
        self._client.mqtt_publish_command(
            sn, type_id, "set_map_obstacle_switch", {"switch": 1 if enabled else 0}
        )

    def clear_obstacle_zones(
        self,
        sn: str,
        type_id: str = DEFAULT_TYPE_ID,
    ) -> None:
        """Clear all obstacle zones from the map."""
        self._client.mqtt_publish_command(
            sn, type_id, "ignore_obstacles", {"zone": []}
        )

    def wireless_charging_cmd(
        self,
        sn: str,
        cmd: int = 0,
        type_id: str = DEFAULT_TYPE_ID,
    ) -> None:
        """Control wireless charging dock.

        ``cmd=0`` stop charging, ``cmd=1`` start charging.
        """
        self._client.mqtt_publish_command(
            sn, type_id, "wireless_charging_cmd", {"cmd": cmd}
        )


class MowerModule(YarboModule):
    """Typed facade for Mower and Mower Pro attachments."""

    module_name = "mower"
    compatible_head_types = (3, 5)

    def set_blade_height(
        self,
        sn: str,
        height_mm: int,
        type_id: str = DEFAULT_TYPE_ID,
        *,
        head_type: int | str | None = None,
        device_data: DeviceData | None = None,
    ) -> None:
        """Set mower blade target height in millimeters."""
        self._validate_optional_context(head_type, device_data)
        self._client.mqtt_publish_command(
            sn, type_id, "mower_target_cmd", {"target": height_mm}
        )

    def set_blade_speed(
        self,
        sn: str,
        speed_percent: int,
        type_id: str = DEFAULT_TYPE_ID,
        *,
        head_type: int | str | None = None,
        device_data: DeviceData | None = None,
    ) -> None:
        """Set mower blade speed as a percentage."""
        self._validate_optional_context(head_type, device_data)
        self._client.mqtt_publish_command(
            sn, type_id, "mower_speed_cmd", {"state": speed_percent}
        )

    def _validate_optional_context(
        self, head_type: int | str | None, device_data: DeviceData | None
    ) -> None:
        if head_type is not None:
            self.validate_head_type(head_type)
            return
        self.validate_device_data(device_data)


class SnowBlowerModule(YarboModule):
    """Typed facade for the Snow Blower attachment."""

    module_name = "snow_blower"
    compatible_head_types = (1,)

    def set_chute_angle(
        self,
        sn: str,
        angle: int,
        type_id: str = DEFAULT_TYPE_ID,
        *,
        head_type: int | str | None = None,
        device_data: DeviceData | None = None,
    ) -> None:
        """Set snow blower chute angle."""
        if head_type is not None:
            self.validate_head_type(head_type)
        else:
            self.validate_device_data(device_data)
        self._client.mqtt_publish_command(
            sn, type_id, "cmd_set_chute_angle", {"cmd": angle}
        )


class BlowerModule(YarboModule):
    """Typed facade for the Blower attachment."""

    module_name = "blower"
    compatible_head_types = (2,)


class TrimmerModule(YarboModule):
    """Typed facade for the Trimmer attachment."""

    module_name = "trimmer"


class PlowModule(YarboModule):
    """Typed facade for the Plow attachment."""

    module_name = "plow"


class SmartAssistModule(YarboModule):
    """Typed facade for the Smart Assist Module attachment."""

    module_name = "sam"


def _extract_head_type(device_data: DeviceData) -> int | str | None:
    """Extract HeadMsg.head_type from raw or data_feedback-wrapped payloads."""
    head_type = extract_field(device_data, "HeadMsg.head_type")
    if head_type is not None:
        return head_type
    nested = device_data.get("data")
    if isinstance(nested, dict):
        return extract_field(nested, "HeadMsg.head_type")
    return None


@dataclass(frozen=True)
class BoundYarboModule:
    """Module facade bound to one device, so callers do not repeat SN/type_id."""

    module: YarboModule
    device: Device
    device_data: DeviceData | None = None

    @property
    def sn(self) -> str:
        return self.device.sn

    @property
    def type_id(self) -> str:
        return self.device.type_id or DEFAULT_TYPE_ID

    def subscribe_device_message(
        self, callback: StatusCallback
    ) -> None:
        self.module.subscribe_device_message(self.sn, callback, self.type_id)

    def subscribe_heart_beat(self, callback: StatusCallback) -> None:
        self.module.subscribe_heart_beat(self.sn, callback, self.type_id)

    def subscribe_data_feedback(
        self, callback: DataFeedbackCallback | None = None
    ) -> None:
        self.module.subscribe_data_feedback(self.sn, callback, self.type_id)

    def get_device_msg(self, timeout: float = 10.0) -> DeviceData:
        _LOGGER.debug("[BoundYarboModule] get_device_msg sn=%s timeout=%s", self.sn, timeout)
        return self.module.get_device_msg(self.sn, self.type_id, timeout)

    def read_gps_ref(self, timeout: float = 10.0) -> DeviceData:
        _LOGGER.debug("[BoundYarboModule] read_gps_ref sn=%s timeout=%s", self.sn, timeout)
        return self.module.read_gps_ref(self.sn, self.type_id, timeout)

    def get_map(self, timeout: float = 30.0) -> DeviceData:
        _LOGGER.debug("[BoundYarboModule] get_map sn=%s timeout=%s", self.sn, timeout)
        return self.module.get_map(self.sn, self.type_id, timeout)

    def read_all_plan(self, timeout: float = 10.0) -> DeviceData:
        _LOGGER.debug("[BoundYarboModule] read_all_plan sn=%s timeout=%s", self.sn, timeout)
        return self.module.read_all_plan(self.sn, self.type_id, timeout)

    def get_connect_wifi_name(self, timeout: float = 10.0) -> DeviceData:
        _LOGGER.debug("[BoundYarboModule] get_connect_wifi_name sn=%s timeout=%s", self.sn, timeout)
        return self.module.get_connect_wifi_name(self.sn, self.type_id, timeout)

    def set_working_state(self, state: int, source: str = "smart_home") -> None:
        _LOGGER.debug("[BoundYarboModule] set_working_state sn=%s state=%s", self.sn, state)
        self.module.set_working_state(self.sn, state, self.type_id, source)

    def publish_command(
        self, command_topic_name: str, payload: CommandPayload
    ) -> None:
        _LOGGER.debug("[BoundYarboModule] publish_command sn=%s topic=%s payload=%s", self.sn, command_topic_name, payload)
        self.module.publish_command(
            self.sn, command_topic_name, payload, self.type_id
        )

    def _validate_module(self) -> None:
        self.module.validate_device_data(self.device_data)


@dataclass(frozen=True)
class BoundCoreModule(BoundYarboModule):
    """Core module bound to one device."""

    module: CoreModule

    def start_plan(self, plan_id: int, start_percent: int = 0) -> None:
        _LOGGER.debug("[BoundCoreModule] start_plan sn=%s plan_id=%s start_percent=%s", self.sn, plan_id, start_percent)
        self.module.start_plan(self.sn, plan_id, self.type_id, start_percent)

    def pause(self) -> None:
        _LOGGER.debug("[BoundCoreModule] pause sn=%s", self.sn)
        self.module.pause(self.sn, self.type_id)

    def resume(self) -> None:
        _LOGGER.debug("[BoundCoreModule] resume sn=%s", self.sn)
        self.module.resume(self.sn, self.type_id)

    def stop(self) -> None:
        _LOGGER.debug("[BoundCoreModule] stop sn=%s", self.sn)
        self.module.stop(self.sn, self.type_id)

    def return_to_charge(self) -> None:
        _LOGGER.debug("[BoundCoreModule] return_to_charge sn=%s", self.sn)
        self.module.return_to_charge(self.sn, self.type_id)

    def song_cmd(self, song_name: str = "find yarbo") -> None:
        _LOGGER.debug("[BoundCoreModule] song_cmd sn=%s song_name=%s", self.sn, song_name)
        self.module.song_cmd(self.sn, song_name, self.type_id)

    def set_sound_param(self, enable: bool, vol: float, mode: int = 0) -> None:
        _LOGGER.debug("[BoundCoreModule] set_sound_param sn=%s enable=%s vol=%s mode=%s", self.sn, enable, vol, mode)
        self.module.set_sound_param(self.sn, enable, vol, mode, self.type_id)

    def set_headlight(self, on: bool) -> None:
        _LOGGER.debug("[BoundCoreModule] set_headlight sn=%s on=%s", self.sn, on)
        self.module.set_headlight(self.sn, on, self.type_id)

    def set_child_lock(self, enabled: bool) -> None:
        _LOGGER.debug("[BoundCoreModule] set_child_lock sn=%s enabled=%s", self.sn, enabled)
        self.module.set_child_lock(self.sn, enabled, self.type_id)

    def set_person_detect(self, enabled: bool) -> None:
        _LOGGER.debug("[BoundCoreModule] set_person_detect sn=%s enabled=%s", self.sn, enabled)
        self.module.set_person_detect(self.sn, enabled, self.type_id)

    def set_follow_state(self, enabled: bool) -> None:
        _LOGGER.debug("[BoundCoreModule] set_follow_state sn=%s enabled=%s", self.sn, enabled)
        self.module.set_follow_state(self.sn, enabled, self.type_id)

    def save_global_params(self, enable_elec_fence: bool, id: int = 1) -> None:
        _LOGGER.debug("[BoundCoreModule] save_global_params sn=%s enable_elec_fence=%s", self.sn, enable_elec_fence)
        self.module.save_global_params(self.sn, enable_elec_fence, id, self.type_id)

    def set_map_obstacle_switch(self, enabled: bool) -> None:
        _LOGGER.debug("[BoundCoreModule] set_map_obstacle_switch sn=%s enabled=%s", self.sn, enabled)
        self.module.set_map_obstacle_switch(self.sn, enabled, self.type_id)

    def clear_obstacle_zones(self) -> None:
        _LOGGER.debug("[BoundCoreModule] clear_obstacle_zones sn=%s", self.sn)
        self.module.clear_obstacle_zones(self.sn, self.type_id)

    def wireless_charging_cmd(self, cmd: int = 0) -> None:
        _LOGGER.debug("[BoundCoreModule] wireless_charging_cmd sn=%s cmd=%s", self.sn, cmd)
        self.module.wireless_charging_cmd(self.sn, cmd, self.type_id)


@dataclass(frozen=True)
class BoundMowerModule(BoundYarboModule):
    """Mower module bound to one device."""

    module: MowerModule

    def set_blade_height(self, height_mm: int) -> None:
        _LOGGER.debug("[BoundMowerModule] set_blade_height sn=%s height_mm=%s", self.sn, height_mm)
        self._validate_module()
        self.module.set_blade_height(self.sn, height_mm, self.type_id)

    def set_blade_speed(self, speed_percent: int) -> None:
        _LOGGER.debug("[BoundMowerModule] set_blade_speed sn=%s speed_percent=%s", self.sn, speed_percent)
        self._validate_module()
        self.module.set_blade_speed(self.sn, speed_percent, self.type_id)


@dataclass(frozen=True)
class BoundSnowBlowerModule(BoundYarboModule):
    """Snow Blower module bound to one device."""

    module: SnowBlowerModule

    def set_chute_angle(self, angle: int) -> None:
        _LOGGER.debug("[BoundSnowBlowerModule] set_chute_angle sn=%s angle=%s", self.sn, angle)
        self._validate_module()
        self.module.set_chute_angle(self.sn, angle, self.type_id)


@dataclass(frozen=True)
class BoundYarboDevice:
    """Typed module hierarchy for one Yarbo device."""

    client: _ClientProtocol
    device: Device
    device_data: DeviceData | None = None

    @property
    def core(self) -> BoundCoreModule:
        return BoundCoreModule(CoreModule(self.client), self.device, self.device_data)

    @property
    def snow_bot(self) -> BoundCoreModule:
        """Backward-compatible name for the shared Yarbo base platform."""
        return self.core

    @property
    def mower(self) -> BoundMowerModule:
        return BoundMowerModule(MowerModule(self.client), self.device, self.device_data)

    @property
    def snow_blower(self) -> BoundSnowBlowerModule:
        return BoundSnowBlowerModule(
            SnowBlowerModule(self.client), self.device, self.device_data
        )

    @property
    def blower(self) -> BoundYarboModule:
        return BoundYarboModule(BlowerModule(self.client), self.device, self.device_data)

    @property
    def trimmer(self) -> BoundYarboModule:
        return BoundYarboModule(
            TrimmerModule(self.client), self.device, self.device_data
        )

    @property
    def plow(self) -> BoundYarboModule:
        return BoundYarboModule(PlowModule(self.client), self.device, self.device_data)

    @property
    def sam(self) -> BoundYarboModule:
        return BoundYarboModule(
            SmartAssistModule(self.client), self.device, self.device_data
        )

"""Tests for typed Yarbo module facades."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from yarbo_robot_sdk import (
    CommandPayload,
    CoreModule,
    DeviceData,
    MowerModule,
    SnowBlowerModule,
    YarboClient,
)
from yarbo_robot_sdk.exceptions import YarboSDKError
from yarbo_robot_sdk.models import Device


def test_pep_561_marker_exists():
    marker = Path(__file__).resolve().parents[1] / "src/yarbo_robot_sdk/py.typed"
    assert marker.exists()


def test_public_type_aliases_are_runtime_usable():
    payload: CommandPayload = {"state": 1}
    data: DeviceData = {"HeadMsg": {"head_type": 3}}

    assert payload["state"] == 1
    assert data["HeadMsg"]["head_type"] == 3


def test_client_exposes_typed_module_names(api_base_url, rsa_key_pair):
    client = YarboClient(
        api_base_url=api_base_url,
        mqtt_host="test-mqtt.yarbo.com",
        mqtt_port=8883,
        mqtt_use_tls=True,
        rsa_public_key=rsa_key_pair["public_key"],
    )

    assert isinstance(client.core, CoreModule)
    assert client.snow_bot is client.core
    assert isinstance(client.mower, MowerModule)
    assert isinstance(client.snow_blower, SnowBlowerModule)


def test_snow_bot_get_device_msg_delegates_to_client(api_base_url, rsa_key_pair):
    client = YarboClient(
        api_base_url=api_base_url,
        mqtt_host="test-mqtt.yarbo.com",
        mqtt_port=8883,
        mqtt_use_tls=True,
        rsa_public_key=rsa_key_pair["public_key"],
    )
    client.get_device_msg = MagicMock(return_value={"data": {"ok": True}})

    result = client.snow_bot.get_device_msg("SN001")

    assert result == {"data": {"ok": True}}
    client.get_device_msg.assert_called_once_with("SN001", "yarbo_Y", 10.0)


def test_mower_module_publishes_blade_commands(api_base_url, rsa_key_pair):
    client = YarboClient(
        api_base_url=api_base_url,
        mqtt_host="test-mqtt.yarbo.com",
        mqtt_port=8883,
        mqtt_use_tls=True,
        rsa_public_key=rsa_key_pair["public_key"],
    )
    client.mqtt_publish_command = MagicMock()

    client.mower.set_blade_height("SN001", 60)
    client.mower.set_blade_speed("SN001", 85)

    client.mqtt_publish_command.assert_any_call(
        "SN001", "yarbo_Y", "mower_target_cmd", {"target": 60}
    )
    client.mqtt_publish_command.assert_any_call(
        "SN001", "yarbo_Y", "mower_speed_cmd", {"state": 85}
    )


def test_snow_blower_module_publishes_chute_angle(api_base_url, rsa_key_pair):
    client = YarboClient(
        api_base_url=api_base_url,
        mqtt_host="test-mqtt.yarbo.com",
        mqtt_port=8883,
        mqtt_use_tls=True,
        rsa_public_key=rsa_key_pair["public_key"],
    )
    client.mqtt_publish_command = MagicMock()

    client.snow_blower.set_chute_angle("SN001", 120)

    client.mqtt_publish_command.assert_called_once_with(
        "SN001", "yarbo_Y", "cmd_set_chute_angle", {"cmd": 120}
    )


def test_core_start_plan_matches_existing_payload(api_base_url, rsa_key_pair):
    client = YarboClient(
        api_base_url=api_base_url,
        mqtt_host="test-mqtt.yarbo.com",
        mqtt_port=8883,
        mqtt_use_tls=True,
        rsa_public_key=rsa_key_pair["public_key"],
    )
    client.mqtt_publish_command = MagicMock()

    client.core.start_plan("SN001", 123, start_percent=25)

    client.mqtt_publish_command.assert_called_once_with(
        "SN001", "yarbo_Y", "start_plan", {"id": 123, "percent": 25}
    )


def test_bound_device_uses_device_identity(api_base_url, rsa_key_pair):
    client = YarboClient(
        api_base_url=api_base_url,
        mqtt_host="test-mqtt.yarbo.com",
        mqtt_port=8883,
        mqtt_use_tls=True,
        rsa_public_key=rsa_key_pair["public_key"],
    )
    client.mqtt_publish_command = MagicMock()
    device = Device(
        sn="SN002", type_id="snowbot", name="Snowbot", model="S1", online=True
    )

    bound = client.device(device)
    bound.core.return_to_charge()
    bound.mower.set_blade_height(55)
    bound.snow_blower.set_chute_angle(45)

    client.mqtt_publish_command.assert_any_call(
        "SN002", "snowbot", "cmd_recharge", {"cmd": 2}
    )
    client.mqtt_publish_command.assert_any_call(
        "SN002", "snowbot", "mower_target_cmd", {"target": 55}
    )
    client.mqtt_publish_command.assert_any_call(
        "SN002", "snowbot", "cmd_set_chute_angle", {"cmd": 45}
    )


def test_bound_device_validates_head_specific_module(api_base_url, rsa_key_pair):
    client = YarboClient(
        api_base_url=api_base_url,
        mqtt_host="test-mqtt.yarbo.com",
        mqtt_port=8883,
        mqtt_use_tls=True,
        rsa_public_key=rsa_key_pair["public_key"],
    )
    client.mqtt_publish_command = MagicMock()
    device = Device(
        sn="SN003", type_id="yarbo_Y", name="Snow Yarbo", model="Y1", online=True
    )
    snow_data = {"HeadMsg": {"head_type": 1}}

    bound = client.device(device, data=snow_data)
    bound.core.return_to_charge()
    bound.snow_blower.set_chute_angle(90)

    with pytest.raises(YarboSDKError, match="mower module is unavailable"):
        bound.mower.set_blade_height(55)

    client.mqtt_publish_command.assert_any_call(
        "SN003", "yarbo_Y", "cmd_recharge", {"cmd": 2}
    )
    client.mqtt_publish_command.assert_any_call(
        "SN003", "yarbo_Y", "cmd_set_chute_angle", {"cmd": 90}
    )


def test_direct_module_validates_optional_head_context(api_base_url, rsa_key_pair):
    client = YarboClient(
        api_base_url=api_base_url,
        mqtt_host="test-mqtt.yarbo.com",
        mqtt_port=8883,
        mqtt_use_tls=True,
        rsa_public_key=rsa_key_pair["public_key"],
    )
    client.mqtt_publish_command = MagicMock()

    with pytest.raises(YarboSDKError, match="snow_blower module is unavailable"):
        client.snow_blower.set_chute_angle("SN004", 100, head_type=3)

    client.mower.set_blade_height("SN004", 60, head_type=3)
    client.mqtt_publish_command.assert_called_once_with(
        "SN004", "yarbo_Y", "mower_target_cmd", {"target": 60}
    )

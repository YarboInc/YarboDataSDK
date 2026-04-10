# Real-time Data

## Overview

The SDK provides real-time device data via MQTT subscriptions. All connection, authentication, and data encoding are handled internally.

## Subscribing to Data

### Device Status

Receives continuous status updates while the device is active — battery, position, sensors, plan execution state, etc.

```python
def on_status(topic, data):
    from yarbo_robot_sdk import extract_field
    battery = extract_field(data, "BatteryMSG.capacity")
    volume = extract_field(data, "StateMSG.volume")
    print(f"Battery: {battery}%, Volume: {volume}")

client.subscribe_device_message(device.sn, device.type_id, on_status)
```

### Heartbeat

Periodic signal indicating the device is online. Use this to detect connectivity.

```python
client.subscribe_heart_beat(device.sn, device.type_id, on_heartbeat)
```

### Command Responses

Responses to data requests (`get_device_msg`, `read_all_plan`, etc.) are delivered here. The SDK handles this internally when you use the request methods — you typically don't need to subscribe manually.

```python
client.subscribe_data_feedback(device.sn, device.type_id, on_feedback)
```

## Data Compression

Devices with newer firmware use compressed data. The SDK handles compression and decompression transparently — no action required.

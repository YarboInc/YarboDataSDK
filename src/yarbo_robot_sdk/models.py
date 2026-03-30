"""Data models for Yarbo Robot SDK."""

from dataclasses import dataclass


@dataclass
class Device:
    """Device basic information."""

    sn: str
    type_id: str
    name: str
    model: str
    online: bool
    user_type: str = ""

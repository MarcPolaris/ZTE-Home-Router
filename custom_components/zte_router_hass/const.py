"""Constants for the ZTE Router integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "zte_router_hass"
MANUFACTURER = "ZTE"

CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_NAME = "name"

DEFAULT_HOST = "192.168.2.1"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"

CONF_SCAN_INTERVAL = "scan_interval"
CONF_FULL_INTERVAL = "full_interval"
# Fast endpoints (WiFi/WAN/system status) are polled at this interval so state
# changes made elsewhere (router web UI, ZTE app) show up within seconds.
DEFAULT_SCAN_INTERVAL = 5
MIN_SCAN_INTERVAL = 3
MAX_SCAN_INTERVAL = 600

# The slow endpoints (device info, LED/auto-restart, LAN device list, mesh
# topology) are refreshed on their own interval (seconds), configurable.
DEFAULT_FULL_INTERVAL = 30

UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

# coordinator data keys
KEY_DEVICE = "device"
KEY_WAN = "wan"
KEY_WIFI = "wifi"
KEY_GUEST = "guest_wifi"
KEY_SYSTEM = "system"
KEY_LAN_DEVICES = "lan_devices"
KEY_TOPOLOGY = "topology"
KEY_MUMIMO = "mumimo"

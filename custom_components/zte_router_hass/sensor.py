"""Sensor platform for ZTE Router."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfDataRate, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZTEDataUpdateCoordinator
from .entity import ZTEEntity, dig, uptime_to_datetime


@dataclass(frozen=True, kw_only=True)
class ZTESensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any] = lambda data: None


SENSORS: tuple[ZTESensorDescription, ...] = (
    # ---------------- 状态监控类 ----------------
    ZTESensorDescription(
        key="uptime",
        translation_key="uptime",
        name="运行时间",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: uptime_to_datetime(dig(d, "device", "uptime_seconds")),
    ),
    ZTESensorDescription(
        key="wan_status",
        translation_key="wan_status",
        name="WAN 连接状态",
        value_fn=lambda d: dig(d, "wan", "wan1", "connection_status") or "unknown",
    ),
    ZTESensorDescription(
        key="wan_connection_type",
        translation_key="wan_connection_type",
        name="WAN 连接类型",
        value_fn=lambda d: dig(d, "wan", "wan1", "connection_type") or "unknown",
    ),
    ZTESensorDescription(
        key="wan_ip",
        translation_key="wan_ip",
        name="WAN IP 地址",
        icon="mdi:ip-network",
        value_fn=lambda d: dig(d, "wan", "wan1", "ip_address") or "unknown",
    ),
    ZTESensorDescription(
        key="wan_gateway",
        translation_key="wan_gateway",
        name="WAN 网关",
        value_fn=lambda d: dig(d, "wan", "wan1", "gateway") or "unknown",
    ),
    ZTESensorDescription(
        key="wan_uptime",
        translation_key="wan_uptime",
        name="WAN 连接时长",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: uptime_to_datetime(dig(d, "wan", "wan1", "wan_uptime_seconds")),
    ),
    ZTESensorDescription(
        key="wan_rx_bytes",
        translation_key="wan_rx_bytes",
        name="WAN 接收流量",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        value_fn=lambda d: round(
            (dig(d, "wan", "wan1", "rx_bytes") or 0) / 1024**3, 3
        ),
    ),
    ZTESensorDescription(
        key="wan_tx_bytes",
        translation_key="wan_tx_bytes",
        name="WAN 发送流量",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        value_fn=lambda d: round(
            (dig(d, "wan", "wan1", "tx_bytes") or 0) / 1024**3, 3
        ),
    ),
    ZTESensorDescription(
        key="ipv6_status",
        translation_key="ipv6_status",
        name="IPv6 状态",
        value_fn=lambda d: dig(d, "wan", "ipv6", "connection_status") or "unknown",
    ),
    ZTESensorDescription(
        key="ipv6_address",
        translation_key="ipv6_address",
        name="IPv6 地址",
        value_fn=lambda d: dig(d, "wan", "ipv6", "global_address") or "unknown",
    ),
    ZTESensorDescription(
        key="dual_wan",
        translation_key="dual_wan",
        name="双 WAN 功能",
        value_fn=lambda d: "on" if dig(d, "wan", "dual_wan", "enabled") else "off",
    ),
    ZTESensorDescription(
        key="ssid_2g",
        translation_key="ssid_2g",
        name="2.4GHz SSID",
        value_fn=lambda d: dig(d, "wifi", "main", "2.4ghz", "ssid") or "unknown",
    ),
    ZTESensorDescription(
        key="wifi_2g_status",
        translation_key="wifi_2g_status",
        name="2.4GHz Wi-Fi 状态",
        value_fn=lambda d: (
            "on" if dig(d, "wifi", "main", "2.4ghz", "enabled") else "off"
        ),
    ),
    ZTESensorDescription(
        key="ssid_5g",
        translation_key="ssid_5g",
        name="5GHz SSID",
        value_fn=lambda d: dig(d, "wifi", "main", "5ghz", "ssid") or "unknown",
    ),
    ZTESensorDescription(
        key="wifi_5g_status",
        translation_key="wifi_5g_status",
        name="5GHz Wi-Fi 状态",
        value_fn=lambda d: (
            "on" if dig(d, "wifi", "main", "5ghz", "enabled") else "off"
        ),
    ),
    ZTESensorDescription(
        key="guest_ssid_2g",
        translation_key="guest_ssid_2g",
        name="访客 2.4GHz SSID",
        value_fn=lambda d: dig(d, "guest_wifi", "2.4ghz", "ssid") or "unknown",
    ),
    ZTESensorDescription(
        key="guest_wifi_2g_status",
        translation_key="guest_wifi_2g_status",
        name="访客 2.4GHz Wi-Fi 状态",
        value_fn=lambda d: (
            "on" if dig(d, "guest_wifi", "2.4ghz", "enabled") else "off"
        ),
    ),
    ZTESensorDescription(
        key="guest_ssid_5g",
        translation_key="guest_ssid_5g",
        name="访客 5GHz SSID",
        value_fn=lambda d: dig(d, "guest_wifi", "5ghz", "ssid") or "unknown",
    ),
    ZTESensorDescription(
        key="guest_wifi_5g_status",
        translation_key="guest_wifi_5g_status",
        name="访客 5GHz Wi-Fi 状态",
        value_fn=lambda d: (
            "on" if dig(d, "guest_wifi", "5ghz", "enabled") else "off"
        ),
    ),
    ZTESensorDescription(
        key="led",
        translation_key="led",
        name="指示灯定时",
        value_fn=lambda d: (
            "on" if dig(d, "system", "led", "schedule_enabled") else "off"
        ),
    ),
    ZTESensorDescription(
        key="auto_restart",
        translation_key="auto_restart",
        name="自动重启",
        value_fn=lambda d: (
            "on" if dig(d, "system", "auto_restart", "enabled") else "off"
        ),
    ),
    ZTESensorDescription(
        key="connected_devices",
        translation_key="connected_devices",
        name="连接设备数",
        icon="mdi:devices",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(
            [x for x in (d.get("lan_devices") or []) if x.get("active")]
        ),
    ),
    ZTESensorDescription(
        key="total_rx",
        translation_key="total_rx",
        name="总接收流量",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        value_fn=lambda d: round(
            (dig(d, "wan", "wan1", "rx_bytes") or 0) / 1024**3, 3
        ),
    ),
    ZTESensorDescription(
        key="total_tx",
        translation_key="total_tx",
        name="总发送流量",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        value_fn=lambda d: round(
            (dig(d, "wan", "wan1", "tx_bytes") or 0) / 1024**3, 3
        ),
    ),
    # ---------------- WAN 实时速率（vue_home_device_data） ----------------
    ZTESensorDescription(
        key="wan_down_rate",
        translation_key="wan_down_rate",
        name="WAN 实时下行速率",
        icon="mdi:arrow-down-bold",
        value_fn=lambda d: dig(d, "summary", "wan_down_rate") or "unknown",
    ),
    ZTESensorDescription(
        key="wan_up_rate",
        translation_key="wan_up_rate",
        name="WAN 实时上行速率",
        icon="mdi:arrow-up-bold",
        value_fn=lambda d: dig(d, "summary", "wan_up_rate") or "unknown",
    ),
    ZTESensorDescription(
        key="wan_negotiated_speed",
        translation_key="wan_negotiated_speed",
        name="WAN 协商速率",
        icon="mdi:speedometer",
        native_unit_of_measurement="Mbps",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (
            float(dig(d, "summary", "wan_speed"))
            if str(dig(d, "summary", "wan_speed") or "").replace(".", "").isdigit()
            else None
        ),
    ),
    ZTESensorDescription(
        key="access_device_num",
        translation_key="access_device_num",
        name="接入设备总数",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: dig(d, "summary", "access_dev_num"),
    ),
    # ---------------- Mesh 漫游阈值（mesh_threshold_data） ----------------
    ZTESensorDescription(
        key="roam_rssi_24g",
        translation_key="roam_rssi_24g",
        name="Mesh 漫游阈值 2.4GHz",
        icon="mdi:rss",
        native_unit_of_measurement="dBm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: dig(d, "roam", "rssi_24g"),
    ),
    ZTESensorDescription(
        key="roam_rssi_5g",
        translation_key="roam_rssi_5g",
        name="Mesh 漫游阈值 5GHz",
        icon="mdi:rss",
        native_unit_of_measurement="dBm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: dig(d, "roam", "rssi_5g"),
    ),
    ZTESensorDescription(
        key="roam_legacy_sta",
        translation_key="roam_legacy_sta",
        name="老旧设备漫游",
        icon="mdi:swap-horizontal-circle-outline",
        value_fn=lambda d: "on" if dig(d, "roam", "legacy_roam") else "off",
    ),
    # ---------------- 网络/安全服务状态 ----------------
    ZTESensorDescription(
        key="dmz_status",
        translation_key="dmz_status",
        name="DMZ 主机",
        icon="mdi:shield-half-full",
        value_fn=lambda d: "on" if dig(d, "dmz", "enable") else "off",
    ),
    ZTESensorDescription(
        key="ddns_status",
        translation_key="ddns_status",
        name="DDNS 状态",
        icon="mdi:dns",
        value_fn=lambda d: (
            dig(d, "ddns", "status") or "off"
            if dig(d, "ddns", "enable")
            else "off"
        ),
    ),
    ZTESensorDescription(
        key="qos_status",
        translation_key="qos_status",
        name="智能 QoS",
        icon="mdi:network-strength-4",
        value_fn=lambda d: "on" if dig(d, "qos", "enable") else "off",
    ),
    ZTESensorDescription(
        key="port_forward_rules",
        translation_key="port_forward_rules",
        name="端口转发规则数",
        icon="mdi:swap-horizontal",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: dig(d, "portfw") or 0,
    ),
    ZTESensorDescription(
        key="parental_devices",
        translation_key="parental_devices",
        name="家长控制设备数",
        icon="mdi:shield-account",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: dig(d, "pctrl") or 0,
    ),
    ZTESensorDescription(
        key="band_choice",
        translation_key="band_choice",
        name="Wi-Fi 频段优选",
        icon="mdi:wifi-strength-4",
        value_fn=lambda d: dig(d, "band", "band_choose") or "unknown",
    ),
    # ---------------- 系统时间与固件 ----------------
    ZTESensorDescription(
        key="ntp_sync",
        translation_key="ntp_sync",
        name="NTP 同步状态码",
        icon="mdi:clock-check-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: dig(d, "ntp", "sync_status_code") or "unknown",
    ),
    ZTESensorDescription(
        key="router_local_time",
        translation_key="router_local_time",
        name="路由器本地时间",
        icon="mdi:clock-outline",
        value_fn=lambda d: dig(d, "ntp", "local_time") or "unknown",
    ),
    ZTESensorDescription(
        key="firmware_date",
        translation_key="firmware_date",
        name="固件发布日期",
        icon="mdi:calendar-clock",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: dig(d, "fwver", "ver_date") or "unknown",
    ),
    ZTESensorDescription(
        key="wifi_2g_channel",
        translation_key="wifi_2g_channel",
        name="2.4GHz Wi-Fi 信道",
        icon="mdi:radio-tower",
        value_fn=lambda d: dig(d, "wifi_radio", "2.4ghz", "channel") or "unknown",
    ),
    ZTESensorDescription(
        key="wifi_5g_channel",
        translation_key="wifi_5g_channel",
        name="5GHz Wi-Fi 信道",
        icon="mdi:radio-tower",
        value_fn=lambda d: dig(d, "wifi_radio", "5ghz", "channel") or "unknown",
    ),
    ZTESensorDescription(
        key="wifi_2g_rate",
        translation_key="wifi_2g_rate",
        name="2.4GHz 理论速率",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        value_fn=lambda d: dig(d, "wifi_radio", "2.4ghz", "max_rate_mbps"),
    ),
    ZTESensorDescription(
        key="wifi_5g_rate",
        translation_key="wifi_5g_rate",
        name="5GHz 理论速率",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        value_fn=lambda d: dig(d, "wifi_radio", "5ghz", "max_rate_mbps"),
    ),
    ZTESensorDescription(
        key="compat_ssid_2g",
        translation_key="compat_ssid_2g",
        name="Wi-Fi 5 兼容网络 2.4GHz 名称",
        icon="mdi:wifi-cog",
        value_fn=lambda d: dig(d, "wifi_compat", "2.4ghz", "ssid") or "unknown",
    ),
    ZTESensorDescription(
        key="compat_ssid_5g",
        translation_key="compat_ssid_5g",
        name="Wi-Fi 5 兼容网络 5GHz 名称",
        icon="mdi:wifi-cog",
        value_fn=lambda d: dig(d, "wifi_compat", "5ghz", "ssid") or "unknown",
    ),
    ZTESensorDescription(
        key="wifi_timer",
        translation_key="wifi_timer",
        name="Wi-Fi 定时关闭",
        icon="mdi:timer-off-outline",
        value_fn=lambda d: "on" if dig(d, "wifi_timer", "enabled") else "off",
    ),
    ZTESensorDescription(
        key="wifi_timer_window",
        translation_key="wifi_timer_window",
        name="Wi-Fi 定时关闭时段",
        icon="mdi:clock-outline",
        value_fn=lambda d: (
            f"{dig(d, 'wifi_timer', 'start')} - {dig(d, 'wifi_timer', 'end')}"
            if dig(d, "wifi_timer", "start")
            else "unknown"
        ),
    ),
    ZTESensorDescription(
        key="ipv6_lla",
        translation_key="ipv6_lla",
        name="IPv6 LLA",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: dig(d, "wan", "ipv6", "lla") or "unknown",
    ),
    ZTESensorDescription(
        key="ipv6_gateway",
        translation_key="ipv6_gateway",
        name="IPv6 网关",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: dig(d, "wan", "ipv6", "gateway") or "unknown",
    ),
    # ---------------- 诊断类 ----------------
    ZTESensorDescription(
        key="model",
        translation_key="model",
        name="设备型号",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: dig(d, "device", "model") or "unknown",
    ),
    ZTESensorDescription(
        key="software_version",
        translation_key="software_version",
        name="软件版本",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: dig(d, "device", "software_version") or "unknown",
    ),
    ZTESensorDescription(
        key="hardware_version",
        translation_key="hardware_version",
        name="硬件版本",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: dig(d, "device", "hardware_version") or "unknown",
    ),
    ZTESensorDescription(
        key="manufacturer",
        translation_key="manufacturer",
        name="制造商",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: dig(d, "device", "manufacturer") or "ZTE",
    ),
    ZTESensorDescription(
        key="serial_number",
        translation_key="serial_number",
        name="序列号",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: dig(d, "device", "serial_number") or "unknown",
    ),
    ZTESensorDescription(
        key="work_mode",
        translation_key="work_mode",
        name="工作模式",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: dig(d, "device", "mode") or "unknown",
    ),
    ZTESensorDescription(
        key="mesh",
        translation_key="mesh",
        name="Mesh 组网",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: "on" if dig(d, "device", "mesh_enabled") else "off",
    ),
    ZTESensorDescription(
        key="wan_mac",
        translation_key="wan_mac",
        name="WAN MAC 地址",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: dig(d, "wan", "wan1", "mac_address") or "unknown",
    ),
    ZTESensorDescription(
        key="dns",
        translation_key="dns",
        name="DNS 服务器",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: ", ".join(
            x
            for x in (
                dig(d, "wan", "wan1", "dns1"),
                dig(d, "wan", "wan1", "dns2"),
                dig(d, "wan", "wan1", "dns3"),
            )
            if x and x != "0.0.0.0"
        )
        or "unknown",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ZTEDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ZTESensor(coordinator, description) for description in SENSORS
    )


class ZTESensor(ZTEEntity, SensorEntity):
    """Representation of a ZTE router sensor."""

    entity_description: ZTESensorDescription

    def __init__(
        self,
        coordinator: ZTEDataUpdateCoordinator,
        description: ZTESensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._attr_unique_id_base}_{description.key}"
        # keep the unit in sync with the description (HA no longer copies it)
        self._attr_native_unit_of_measurement = getattr(
            description, "native_unit_of_measurement", None
        )

    @property
    def suggested_object_id(self) -> str | None:
        """Stable, language independent entity_id (e.g. sensor.wan_ip)."""
        return self.entity_description.key

    @property
    def native_value(self) -> datetime | str | float | int | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.entity_description.key == "connected_devices":
            devices = [
                {
                    "hostname": dev.get("hostname"),
                    "ip": dev.get("ip"),
                    "mac": dev.get("mac"),
                    "connection_type": dev.get("connection_type"),
                    "band": dev.get("band"),
                }
                for dev in self.coordinator.lan_devices
            ]
            return {"lan_devices": devices}
        if self.entity_description.key == "mesh":
            topo = self.coordinator.data.get("topology") or {}
            agents = [
                {"name": a.get("name"), "ip": a.get("ip"), "mac": a.get("mac")}
                for a in topo.get("agents", [])
            ]
            return {"mesh_agents": agents} if agents else {}
        return {}

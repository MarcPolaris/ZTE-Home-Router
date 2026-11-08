<div align="center">

# ZTE Home Router

**A Home Assistant integration for ZTE home Wi-Fi routers**
中兴家用路由器 Home Assistant 集成

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2025.10%2B-41BDF5.svg)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/badge/version-1.0.2-brightgreen.svg)](https://github.com/MarcPolaris/ZTE-Home-Router/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MarcPolaris&repository=ZTE-Home-Router&category=integration)

[English](#english) · [简体中文](#简体中文)

</div>

---

## English

Turn a ZTE consumer router into a first-class Home Assistant device: every connected client becomes a tracker, every radio and SSID becomes a switch, and WAN/Wi-Fi health is exposed as sensors — all over the local network, no cloud, no MQTT bridge, no router firmware modification.

The protocol was reverse-engineered from the ZTE Vue web console (`?_type=...&_tag=...` endpoints). Verified on **ZTE 巡天 BE5100 Pro+ (ZXSLC SR7110 / SR7115)**, firmware **V1.0.0.4B8.8000**, in a Mesh setup with a master and a slave node.

### Highlights

- **Presence that actually works** — one `device_tracker` per LAN/Wi-Fi client, with IP, hostname, link type, band, RSSI, guest flag, parent mesh node and per-device traffic.
- **Full Wi-Fi control** — dual-band sync, MLO, per-band on/off, SSID hiding, guest networks, and the Wi-Fi 5 compatibility network (master + per-band).
- **Two-speed polling** — Wi-Fi/WAN state every 5 s, device list and topology every 30 s; both configurable.
- **Zero router traffic on demand** — a local-only *Pause tracker* switch stops polling completely so the integration never fights your browser session.

### Supported models

> **Scope**: this integration targets ZTE **home Wi-Fi routers** — dual-band, Wi-Fi 6 / Wi-Fi 7 consumer routers. ZTE **5G CPE** models (MC801A / MC888 / MC889 / G5 Ultra) are covered by a different project, [Kajkac/ZTE-MC-Home-assistant-repo](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo).

| Status | Models |
| :-- | :-- |
| ✅ **Verified** | 巡天 BE5100 Pro+ (ZXSLC SR7110 / SR7115), firmware V1.0.0.4B8.8000, Mesh master + slave |
| 🧪 **Expected to work** (community testing needed) | 问天 BE7200 MAX · 问天 BE7200 Pro+ · 问天 BE6800 Pro+ · 晴天 BE5100 Pro+ · 晴天 BE5100 · 巡天 BE5100 · 巡天 BE3600 Pro · 巡天 BE3600 Pro 青云版 · AX5400 Pro+ · 巡天 AX3000 Pro+ · 巡天 AX3000 · 晴天 AX3000 |

Any ZTE router whose web console speaks the same `?_type=vueData|hiddenData|vuejsonData&_tag=...` API (Vue-based admin page) should work — that covers most Wi-Fi 6/7 models from 2022 onwards. Some features degrade gracefully: the MU-MIMO switch only appears when the router exposes the Wi-Fi 7 special-features endpoint. If your model works, please [open an issue](https://github.com/MarcPolaris/ZTE-Home-Router/issues) and report it — the table grows from user reports.

### Entities

#### Switches (13)

| Switch | Underlying field | Notes |
| :-- | :-- | :-- |
| Wi-Fi dual band sync | `DualBandSync` | Merges 2.4 / 5 GHz into one SSID |
| Wi-Fi MLO aggregation | `MLOEnable` | Wi-Fi 7 multi-link operation; **mutually exclusive** with dual-band sync |
| 2.4GHz Wi-Fi / 5GHz Wi-Fi | `AP1` / `AP5` `Enable` | Main radios on/off |
| Hide 2.4GHz / 5GHz SSID | `ESSIDHideEnable` | |
| Guest 2.4GHz / 5GHz Wi-Fi | guest `Enable` | |
| Wi-Fi 5 compatibility network | `ForceWiFi` | Master switch of the compatibility network |
| Wi-Fi 5 compatibility network 2.4GHz / 5GHz | `AP3` / `AP7` `Enable` | Per-band switches, independent of the master switch |
| MU-MIMO | Wi-Fi 7 special features | Created only when the endpoint exists |
| Pause tracker | *local only* | Stops all polling; entities freeze at their last state |

> **How the compatibility network behaves.** On the router page there is one master switch and two band switches, all independent. A firmware quirk: after the master switch is turned off, both band switches stay "on" internally (the SSIDs are simply not broadcast), and turning the master back on restores them. To avoid a misleading "master off, bands still on" state, the two band switches in Home Assistant show the **effective** state (`master on AND band on`): with the master off they read *off*, and turning either band on automatically turns the master on. Turning the master on while both bands are off turns both bands on.

#### Sensors (59)

| Group | Entities |
| :-- | :-- |
| **System** | Uptime · Working mode · Mesh status · LED indicator · Auto restart · Connected devices · Access devices total |
| **WAN** | Connection status · Connection type · IP address · Gateway · MAC · DNS servers · Uptime · Dual WAN · Received / Sent traffic · IPv6 status / address / LLA / gateway · **Live up / down rate** · **Negotiated speed** |
| **Wi-Fi main** | 2.4GHz SSID + status + channel + max rate · 5GHz SSID + status + channel + max rate · Band preference |
| **Guest Wi-Fi** | Guest 2.4GHz SSID + status · Guest 5GHz SSID + status |
| **Compatibility network** | Wi-Fi 5 compat 2.4GHz / 5GHz SSID |
| **Schedule** | Wi-Fi schedule · Wi-Fi schedule window (read-only) |
| **Traffic totals** | Total received · Total sent |
| **Mesh roaming** | Roaming threshold 2.4GHz / 5GHz (dBm) · Legacy device roaming |
| **Network services** | DMZ host · DDNS status · Smart QoS · Port forwarding rules · Parental control devices |
| **Diagnostic** | Model · Firmware version · Hardware version · Manufacturer · Serial number · Firmware release date · NTP sync · Router local time |

#### Button (1)

| Button | Action |
| :-- | :-- |
| Reboot | Reboots the router |

#### Device tracker (one per client)

`home` / `not_home`, with attributes: `mac`, `ip`, `hostname`, `connection_type` (LAN / 2.4GHz / 5GHz), `interface`, `band`, `rssi`, `is_guest`, `parent_device` (upstream mesh node), `device_type`, `rx_bytes`, `tx_bytes`, plus from the app-side client table: `alias` (name set in the ZTE app), `ipv6` / `ipv6_gua`, `iface_type`, `last_connection`, `up_rate` / `down_rate` (live).

### Installation

**HACS (recommended)**

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MarcPolaris&repository=ZTE-Home-Router&category=integration)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/MarcPolaris/ZTE-Home-Router`, category **Integration**.
2. Search for **ZTE Home Router** and install it.
3. Restart Home Assistant.

**Manual**

Copy `custom_components/zte_router_hass` into your HA `config/custom_components/` directory and restart.

### Configuration

**Settings → Devices & Services → Add Integration → ZTE Home Router**

| Option | Default | Description |
| :-- | :-- | :-- |
| Host | `192.168.2.1` | Router IP address |
| Username | `admin` | Web console username |
| Password | `admin` | Web console password |
| Name | *model + IP* | Device name, leave empty to auto-generate |

After setup, open **Configure** on the integration to tune polling:

| Option | Default | Range | What it refreshes |
| :-- | :-- | :-- | :-- |
| Status interval | 5 s | 3–600 s | Wi-Fi, WAN, MU-MIMO, client detail (rates/IPv6) — state changed in the router UI or the ZTE app shows up here within seconds |
| Full interval | 30 s | — | Device list, mesh topology, LED / auto-restart, mesh roaming thresholds, DMZ / DDNS / QoS / NTP status |

All entities hang off one device registered during the config flow (unique id = router serial number). The integration ships its own brand icon, so the device is rendered with the ZTE logo.

### Automation examples

Turn guest Wi-Fi off at night and back on in the morning:

```yaml
automation:
  - alias: "Router: guest Wi-Fi off at night"
    triggers:
      - trigger: time
        at: "23:30:00"
    actions:
      - action: switch.turn_off
        target:
          entity_id: switch.guest_wifi_2g
```

Notify when the number of connected clients jumps (new device joined):

```yaml
automation:
  - alias: "Router: many new clients"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.connected_devices
        above: 20
    actions:
      - action: notify.persistent_notification
        data:
          message: >-
            {{ states('sensor.connected_devices') }}
            clients are connected to the router.
```

Script to free the admin session before you open the router web UI:

```yaml
script:
  router_maintenance:
    alias: "Router: pause polling for 10 minutes"
    sequence:
      - action: switch.turn_on
        target:
          entity_id: switch.pause_tracker
      - delay: "00:10:00"
      - action: switch.turn_off
        target:
          entity_id: switch.pause_tracker
```

> Entity IDs depend on your device name — check **Developer Tools → States** for the exact values.

### How it works

| Topic | Behaviour |
| :-- | :-- |
| **Admin session preemption** | ZTE routers allow very few concurrent admin sessions. When all are taken, the integration *kicks the oldest* session to log in — this can sign out a browser tab that is logged into the router. Use *Pause tracker* if that is a problem. |
| **Switches submit the whole form** | Toggling any main Wi-Fi switch re-submits the complete Wi-Fi configuration (SSIDs, security, power). Do not edit Wi-Fi settings in the web console and in HA at the same time. |
| **`-1452` "page expired" is expected** | For radio-restarting changes this firmware writes the new configuration *first* and only then answers `-1452`, because restarting the radio invalidates the page session. The integration re-reads the real state and treats the change as successful when it took effect. |
| **Dual-band state source** | Dual-band sync and MLO are read from `dualband_lua` — the same endpoint the web console uses. `wifi_advancedssid_data` keeps a stale copy of those two flags, so it is ignored. |
| **MLO vs dual-band sync** | Mutually exclusive in firmware: enabling MLO turns dual-band sync off automatically (the web UI does the same). |
| **Compatibility network** | Master switch `ForceWiFi` and per-band `Enable` (AP3 / AP7) are independent; band switches report the effective state. See the switch table above. |
| **Reboot** | `POST ?_type=vueData&_tag=vue_derestart_data` with `IF_ACTION=Restart` — exactly what the web console sends. The router restarts immediately, so the HTTP reply is often cut off or never arrives; the integration therefore confirms the reboot by watching the router *leave the network* and only reports success once it is gone. |
| **Privacy** | All traffic stays on your LAN. Credentials are stored by Home Assistant only and are never sent anywhere else. |

### Troubleshooting

| Symptom | Cause | Fix |
| :-- | :-- | :-- |
| Entities intermittently show *unavailable* | A poll round failed (session taken by the router UI or the app) | Raise the status interval to 10–30 s, or turn on *Pause tracker* while you use the web console |
| A switch action fails with `-1452` | Session/page expired, or the radio restart invalidated it after a write | Retry once — the integration verifies by re-reading state. If it persists, pause polling and retry |
| A browser tab keeps getting logged out of the router | Admin session preemption | Turn on *Pause tracker* before opening the router UI |
| Wi-Fi settings revert unexpectedly | Two writers: HA and the web console | Edit Wi-Fi only from one place at a time |
| Duplicate `iPhone` / `空调伴侣` devices appear | The older `zte_tracker` integration is also installed | Uninstall `zte_tracker` — both register the same clients |
| MU-MIMO switch missing | Router does not expose the Wi-Fi 7 special-features endpoint | Expected; not every model has it |

<details>
<summary><b>Protocol notes (for developers)</b></summary>

`zte_client.py` implements the reversed protocol:

1. `GET /?_type=loginsceneData&_tag=login_token_json` → `logintoken` + `_sessionToken`.
2. `POST /?_type=loginData&_tag=login_entry` with `Password = sha256(password + logintoken)`.
3. If `loginErrType == e_exceed_max_user_preempt`: `preempt_cancel` then `login_preempt`.
4. Every response may rotate the CSRF token in the `X_XSRF_TOKEN` header; every mutating POST must carry the latest token as `_sessionTOKEN` in the body, otherwise the router answers `-1452`.
5. Data endpoints: `?_type=vueData|hiddenData|vuejsonData&_tag=<tag>`, returning XML (`ParaName` / `ParaValue` pairs) or JSON.
6. Wi-Fi passwords: `IF_ACTION=GetPassword`, decrypted with AES-256-CBC (key `sha256(token)`, iv `sha256(reverse(token))[:16]`); write-back encrypts with AES + RSA (`encode` field).
7. Config writes go through the UI channel `wiazrdAuthor_data` — AP1 fields have **no** numeric suffix, AP5 uses the `5` suffix, and the password field uses the sentinel `false` to mean "unchanged".

</details>

### Debug logging

```yaml
logger:
  logs:
    custom_components.zte_router_hass: debug
```

### Credits & disclaimer

- Inspired by [juacas/zte_tracker](https://github.com/juacas/zte_tracker) (device tracking for ZTE routers). This project started when I wanted Wi-Fi control and WAN monitoring on top of tracking.
- 5G CPE owners: see [Kajkac/ZTE-MC-Home-assistant-repo](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo).
- Unofficial and not affiliated with ZTE. The protocol is undocumented and may change with firmware updates — use at your own risk.

---

## 简体中文

把一台中兴家用路由器变成 Home Assistant 里的一等公民：每个连网终端变成跟踪实体，每个射频和 SSID 变成开关，WAN / Wi-Fi 健康状况变成传感器。全程走局域网，不经过云端，不搭 MQTT 桥，也不改路由器固件。

协议逆向自中兴 Vue Web 管理界面的 `?_type=...&_tag=...` 接口。已在 **ZTE 巡天 BE5100 Pro+（ZXSLC SR7110 / SR7115）**、固件 **V1.0.0.4B8.8000**（Mesh 主机 + 从机）上实测通过。

### 亮点

- **靠谱的在网状态** —— 每个 LAN / Wi-Fi 终端一个 `device_tracker`，带 IP、主机名、接入方式、频段、RSSI、是否访客、上级 Mesh 节点和上下行流量。
- **完整的 Wi-Fi 控制** —— 双频合一、MLO、分频开关、隐藏 SSID、访客网络，以及 Wi-Fi 5 兼容网络（总开关 + 分频）。
- **两档轮询** —— Wi-Fi / WAN 状态 5 秒一次，设备列表与拓扑 30 秒一次，两档都可调。
- **随时零打扰** —— *暂停跟踪器* 是纯本地开关，打开后完全停止访问路由器，不会和你的浏览器抢管理会话。

### 适用范围与支持机型

> **适用范围**：本集成针对中兴**家用 Wi-Fi 路由器**，理论上支持所有**双频 / Wi-Fi 6 / Wi-Fi 7 消费级路由**，如问天 BE7200 MAX、问天 BE7200 Pro+、问天 BE6800 Pro+、晴天 BE5100 Pro+、巡天 BE5100 Pro+、晴天 BE5100、巡天 BE5100、巡天 BE3600 Pro、巡天 BE3600 Pro 青云版、AX5400 Pro+、巡天 AX3000 Pro+、巡天 AX3000、晴天 AX3000 等，**需自行测试**。
>
> 中兴 **5G CPE** 机型（MC801A / MC888 / MC889 / G5 Ultra）请使用另一个项目 [Kajkac/ZTE-MC-Home-assistant-repo](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo)。

| 状态 | 机型 |
| :-- | :-- |
| ✅ **已实测** | 巡天 BE5100 Pro+（ZXSLC SR7110 / SR7115），固件 V1.0.0.4B8.8000，Mesh 主机 + 从机 |
| 🧪 **理论支持，待验证** | 问天 BE7200 MAX · 问天 BE7200 Pro+ · 问天 BE6800 Pro+ · 晴天 BE5100 Pro+ · 晴天 BE5100 · 巡天 BE5100 · 巡天 BE3600 Pro · 巡天 BE3600 Pro 青云版 · AX5400 Pro+ · 巡天 AX3000 Pro+ · 巡天 AX3000 · 晴天 AX3000 |

判断标准很简单：只要路由器管理页面是 Vue 架构、接口形如 `?_type=vueData|hiddenData|vuejsonData&_tag=...`，基本都能用（2022 年之后的 Wi-Fi 6 / Wi-Fi 7 机型大多如此）。部分功能会按机型自动降级——例如 MU-MIMO 开关只在路由器提供 Wi-Fi 7 高级特性接口时才创建。**测过能用欢迎[提 issue](https://github.com/MarcPolaris/ZTE-Home-Router/issues)告诉我型号，我把表补上。**

### 实体清单

#### 开关（13 个）

| 开关 | 对应字段 | 说明 |
| :-- | :-- | :-- |
| Wi-Fi 双频合一 | `DualBandSync` | 2.4 / 5GHz 合并为同一 SSID |
| Wi-Fi 频段聚合 (MLO) | `MLOEnable` | Wi-Fi 7 多链路聚合；与双频合一**互斥** |
| 2.4GHz Wi-Fi / 5GHz Wi-Fi | `AP1` / `AP5` 的 `Enable` | 主网络射频开关 |
| 隐藏 2.4GHz / 5GHz SSID | `ESSIDHideEnable` | |
| 访客 2.4GHz / 5GHz Wi-Fi | 访客 `Enable` | |
| Wi-Fi 5 兼容网络 | `ForceWiFi` | 兼容网络**总开关** |
| Wi-Fi 5 兼容网络 2.4GHz / 5GHz | `AP3` / `AP7` 的 `Enable` | 分频开关，与总开关相互独立 |
| MU-MIMO | Wi-Fi 7 高级特性 | 仅当接口存在时创建 |
| 暂停跟踪器 | *纯本地* | 停止全部轮询，实体保持最后状态 |

> **兼容网络的显示逻辑**：路由器页面上是「1 个总开关 + 2 个频段开关」，三者互相独立。固件有个特性：总开关关掉后，两个频段的 `Enable` 在底层仍是开的（只是不广播 SSID），重新打开总开关即原样恢复。为避免 HA 里出现「总开关关了、频段还显示开」的误导，两个频段开关显示的是**生效状态**（总开关开 **且** 该频段开）：总开关关闭时频段开关显示为关；此时打开任一频段会自动把总开关一起打开；总开关打开时若两个频段都关着，会自动把两个频段一起打开。

#### 传感器（59 个）

| 分组 | 实体 |
| :-- | :-- |
| **系统** | 运行时间 · 工作模式 · Mesh 组网 · 指示灯 · 自动重启 · 连接设备数 · 接入设备总数 |
| **WAN** | 连接状态 · 连接类型 · IP 地址 · 网关 · MAC · DNS 服务器 · 连接时长 · 双 WAN · 接收 / 发送流量 · IPv6 状态 / 地址 / LLA / 网关 · **实时上行 / 下行速率** · **协商速率** |
| **主 Wi-Fi** | 2.4GHz SSID + 状态 + 信道 + 理论速率 · 5GHz SSID + 状态 + 信道 + 理论速率 · Wi-Fi 频段优选 |
| **访客 Wi-Fi** | 访客 2.4GHz SSID + 状态 · 访客 5GHz SSID + 状态 |
| **兼容网络** | Wi-Fi 5 兼容网络 2.4GHz / 5GHz 名称 |
| **定时** | Wi-Fi 定时关闭 · 定时关闭时段（只读） |
| **流量统计** | 总接收流量 · 总发送流量 |
| **Mesh 漫游** | 漫游阈值 2.4GHz / 5GHz（dBm）· 老旧设备漫游 |
| **网络服务** | DMZ 主机 · DDNS 状态 · 智能 QoS · 端口转发规则数 · 家长控制设备数 |
| **诊断** | 设备型号 · 软件版本 · 硬件版本 · 制造商 · 序列号 · 固件发布日期 · NTP 同步 · 路由器本地时间 |

> `Wi-Fi 定时关闭` 该固件只提供读写接口 `vue_internet_advanced_rftimer_data`（hiddenData），当前做成了**只读传感器**；`Wi-Fi 中继`（`wlan_link_data`）与 `Preamble Puncturing` 在下发的固件里没有可用写接口，故未做成开关。

#### 按钮（1 个）

| 按钮 | 动作 |
| :-- | :-- |
| 重启路由器 | 重启路由器 |

#### 设备跟踪（每个终端一个）

`在家` / `离家`，属性含 `mac`、`ip`、`hostname`、`connection_type`（LAN / 2.4GHz / 5GHz）、`interface`、`band`、`rssi`、`is_guest`、`parent_device`（上级 Mesh 节点）、`device_type`、`rx_bytes`、`tx_bytes`，以及来自 App 端客户端表（`vue_client_data`）的：`alias`（在中兴智慧生活 App 里设置的备注名）、`ipv6` / `ipv6_gua`、`iface_type`、`last_connection`、`up_rate` / `down_rate`（实时速率）。

### 安装

**HACS（推荐）**

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MarcPolaris&repository=ZTE-Home-Router&category=integration)

1. HACS → 右上角 ⋮ → **自定义存储库** → 填入 `https://github.com/MarcPolaris/ZTE-Home-Router`，类别选 **集成**。
2. 搜索 **ZTE Home Router** 并安装。
3. 重启 Home Assistant。

**手动安装**

将 `custom_components/zte_router_hass` 复制到 HA 的 `config/custom_components/` 目录并重启。

### 配置

**设置 → 设备与服务 → 添加集成 → ZTE Home Router**

| 配置项 | 默认值 | 说明 |
| :-- | :-- | :-- |
| 主机地址 | `192.168.2.1` | 路由器 IP |
| 用户名 | `admin` | Web 管理用户名 |
| 密码 | `admin` | Web 管理密码 |
| 设备名称 | *型号 + IP* | 留空则自动生成 |

配置完成后可在集成的 **配置** 中调整轮询：

| 选项 | 默认值 | 范围 | 刷新内容 |
| :-- | :-- | :-- | :-- |
| 状态刷新间隔 | 5 秒 | 3–600 秒 | Wi-Fi、WAN、MU-MIMO——在路由器 Web 界面或手机 App 上改的开关，几秒内同步到 HA |
| 完整刷新间隔 | 30 秒 | — | 设备列表、Mesh 拓扑、指示灯 / 自动重启 |

所有实体都挂在配置流程中注册的同一个设备下（唯一 ID = 路由器序列号），集成自带品牌图标，设备卡片显示 ZTE 标志。

### 自动化示例

夜里关访客 Wi-Fi，早上再开：

```yaml
automation:
  - alias: "路由器：夜间关闭访客 Wi-Fi"
    triggers:
      - trigger: time
        at: "23:30:00"
    actions:
      - action: switch.turn_off
        target:
          entity_id: switch.guest_wifi_2g
```

连网设备数异常时提醒（有新设备涌入）：

```yaml
automation:
  - alias: "路由器：连接设备数过多"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.connected_devices
        above: 20
    actions:
      - action: notify.persistent_notification
        data:
          message: >-
            当前有 {{ states('sensor.connected_devices') }}
            台设备连接路由器。
```

打开路由器 Web 界面之前先让出管理会话：

```yaml
script:
  router_maintenance:
    alias: "路由器：暂停轮询 10 分钟"
    sequence:
      - action: switch.turn_on
        target:
          entity_id: switch.pause_tracker
      - delay: "00:10:00"
      - action: switch.turn_off
        target:
          entity_id: switch.pause_tracker
```

> 实体 ID 取决于你的设备名称，请到 **开发者工具 → 状态** 里核对真实值。

### 工作原理与注意事项

| 主题 | 说明 |
| :-- | :-- |
| **管理员会话抢占** | 中兴路由器允许的并发管理会话很少。会话占满时，集成会自动**踢掉最旧的会话**完成登录——这可能导致已登录路由器的浏览器标签页被登出。介意就用*暂停跟踪器*。 |
| **开关会提交完整表单** | 切换任意主 Wi-Fi 开关都会重新提交整个 Wi-Fi 配置（SSID、加密、功率等）。请勿同时在 Web 界面和 HA 里改 Wi-Fi 设置。 |
| **`-1452`「页面过期」是正常的** | 对射频重启类变更，该固件**先写入新配置、再返回 `-1452`**（射频重启让页面会话失效）。集成因此会回读真实状态，只要生效就判定为成功。 |
| **双频合一的权威数据源** | 双频合一与 MLO 读的是 `dualband_lua`——Web 界面同款接口。`wifi_advancedssid_data` 里同名字段是过期副本，直接忽略。 |
| **MLO 与双频合一互斥** | 固件行为：打开 MLO 会自动关闭双频合一（Web 界面同样如此）。 |
| **兼容网络** | 总开关 `ForceWiFi` 与分频 `Enable`（AP3 / AP7）相互独立，分频开关显示生效状态，详见上方开关表。 |
| **重启** | `POST ?_type=vueData&_tag=vue_derestart_data`，`IF_ACTION=Restart`——与 Web 界面完全同一调用。路由器会立刻重启，HTTP 响应经常被截断或根本收不到，因此集成以「路由器从网络上消失」作为成功判据，只有确认掉线才返回成功。 |
| **隐私** | 所有通信仅发生在局域网内；凭据只由 Home Assistant 存储，不会发送到任何其他地方。 |

### 常见问题

| 现象 | 原因 | 处理 |
| :-- | :-- | :-- |
| 实体偶尔显示*不可用* | 某一轮轮询失败（会话被 Web 界面或手机 App 占用） | 把状态刷新间隔调到 10–30 秒，或用网页端时打开*暂停跟踪器* |
| 开关操作报 `-1452` | 会话 / 页面过期，或射频重启让写操作后失效 | 重试一次即可（集成会回读校验）；持续失败就先暂停轮询再操作 |
| 浏览器里的管理页面总被登出 | 管理员会话抢占 | 打开路由器界面前先打开*暂停跟踪器* |
| Wi-Fi 设置会被改回去 | HA 和 Web 界面两个写入方 | 同一时间只在一个地方改 Wi-Fi |
| 设备列表里出现大量重复的 `iPhone`、`空调伴侣` | 同时装了旧的 `zte_tracker` 集成 | 卸载 `zte_tracker`，两者会重复登记同一批终端 |
| 没有 MU-MIMO 开关 | 路由器未提供 Wi-Fi 7 高级特性接口 | 属正常情况，并非所有机型都有 |

<details>
<summary><b>协议要点（供开发者参考）</b></summary>

客户端 `zte_client.py` 实现了逆向出的完整协议：

1. `GET /?_type=loginsceneData&_tag=login_token_json` → 获取 `logintoken` + `_sessionToken`。
2. `POST /?_type=loginData&_tag=login_entry`，`Password = sha256(密码 + logintoken)`。
3. 若返回 `loginErrType == e_exceed_max_user_preempt`：执行 `preempt_cancel` + `login_preempt` 抢占登录。
4. 每个响应的 `X_XSRF_TOKEN` 头会轮换 CSRF token；所有写操作 POST 必须在 body 中携带最新 token 作为 `_sessionTOKEN`，否则返回 `-1452`。
5. 数据接口：`?_type=vueData|hiddenData|vuejsonData&_tag=<tag>`，返回 XML（`ParaName` / `ParaValue` 对）或 JSON。
6. Wi-Fi 密码读写：`IF_ACTION=GetPassword` 取回密文（AES-256-CBC 解密，key=`sha256(token)`，iv=`sha256(reverse(token))[:16]`）；写入时用随机密钥 AES 加密 + RSA 加密密钥（`encode` 字段）。
7. 配置写入走 UI 提交通道 `wiazrdAuthor_data`（前端拼写如此）：AP1 字段**不带数字后缀**，AP5 用 `5` 后缀，密码字段用哨兵值 `false` 表示"不变"。

</details>

### 调试日志

```yaml
logger:
  logs:
    custom_components.zte_router_hass: debug
```

### 致谢与免责

- 灵感来自 [juacas/zte_tracker](https://github.com/juacas/zte_tracker)（中兴路由器设备跟踪）。本项目最初只是想在其基础上补上 Wi-Fi 控制与 WAN 监控。
- 5G CPE 用户请看 [Kajkac/ZTE-MC-Home-assistant-repo](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo)。
- 本项目为非官方项目，与中兴通讯无关。协议未公开，可能随固件升级失效，使用风险自负。

---

## License / 许可

[MIT](LICENSE)

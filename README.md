# ZTE Home Router for Home Assistant / 中兴家用路由器 Home Assistant 集成

[English](#english) | [中文](#中文)

---

## English

A Home Assistant custom integration for ZTE routers, reverse-engineered from the ZTE Vue web console. Verified on **ZTE 巡天 BE5100 Pro+ (ZXSLC SR7110 / SR7115)** with firmware **V1.0.0.4B8.8000** (Mesh master + slave), and likely compatible with other ZTE routers using the same `?_type=...&_tag=...` API style.

> **Scope**: this integration targets ZTE **home Wi-Fi routers** (dual-band / Wi-Fi 7 consumer routers). ZTE **5G CPE** models (MC801A / MC888 / MC889 / G5 Ultra) are covered by the separate [Kajkac/ZTE-MC-Home-assistant-repo](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo) — use that one for those devices.

### Features

- **Device tracking**: every LAN/WiFi client becomes a `device_tracker` entity (`home`/`not_home`) with IP, hostname, connection type (LAN/WiFi), band, RSSI, guest flag, upstream mesh node, and traffic counters.
- **Sensors** (状态监控):
  - Router uptime, working mode, Mesh status
  - WAN: connection status, connection type, IP, gateway, MAC, DNS, WAN uptime, IPv6 status/address, dual-WAN state
  - WiFi: 2.4GHz/5GHz SSID + status, guest 2.4GHz/5GHz SSID + status
  - System: LED indicator, auto restart
  - Traffic: connected device count, total received / sent volume
- **Diagnostic sensors**: model, firmware/hardware version, serial number, manufacturer.
- **Switches**:
  - Wi-Fi 双频合一 (dual band sync)
  - Wi-Fi 频段聚合 MLO
  - 2.4GHz WiFi on/off, hide 2.4GHz SSID
  - 5GHz WiFi on/off, hide 5GHz SSID
  - Guest 2.4GHz / 5GHz WiFi on/off
  - MU-MIMO (only created when the router exposes the Wi-Fi 7 special-features endpoint)
  - Pause tracker (suspend all polling with zero router traffic — turn it ON before managing the router web UI or mobile app, so the integration does not fight over the admin session; every entity freezes at its last known state and polling resumes when you turn it OFF)
- **Button**: reboot the router.

> **Note**: the *Preamble Puncturing* switch is not implemented — this firmware's web UI only ships the label, no working API endpoint was found.

### Installation

**HACS (recommended)**

1. Add this repository to HACS as a custom repository (category: *Integration*).
2. Install **ZTE Home Router**.
3. Restart Home Assistant.

**Manual**

Copy `custom_components/zte_router_hass` into your HA `config/custom_components/` directory and restart.

### Configuration

Settings → Devices & Services → **Add Integration** → search **ZTE Home Router**.

| Option | Default | Description |
| --- | --- | --- |
| Host | `192.168.2.1` | Router IP address |
| Username | `admin` | Web console username |
| Password | `admin` | Web console password |

Options (after setup): polling interval (10–600 s, default 30 s).

All entities are attached to a single router device registered during config flow (unique id = serial number).

### Important notes

- **Admin session preemption**: ZTE routers allow a very limited number of admin sessions. When all sessions are taken, the integration automatically *kicks* the oldest session to log in — this may sign out a browser tab that is logged into the router.
- **WiFi switches apply the full form**: toggling any main-WiFi switch re-submits the whole WiFi configuration (SSIDs, security, power). Do not change WiFi settings in the web console and in HA at the same time.
- **`-1452` "page expired" after a dual-band / MLO change is expected**: this firmware writes the new configuration first and only then answers `-1452`, because the radio restart invalidates the page session. The integration therefore re-reads the real state and treats the change as successful when it took effect. Dual-band-sync / MLO state is read from `dualband_lua` (the same endpoint the web console uses) — `wifi_advancedssid_data` keeps a stale copy of those two flags.
- **MLO and dual-band-sync are mutually exclusive** on this firmware: turning MLO on automatically turns dual-band-sync off (and the web UI behaves the same way).
- All traffic stays on your LAN; credentials are stored by Home Assistant only.

### Protocol (for developers)

The client (`zte_client.py`) implements the reversed protocol:

1. `GET /?_type=loginsceneData&_tag=login_token_json` → `logintoken` + `_sessionToken`
2. `POST /?_type=loginData&_tag=login_entry` with `Password = sha256(password + logintoken)`
3. If `loginErrType == e_exceed_max_user_preempt`: `preempt_cancel` + `login_preempt`
4. Every response may rotate the CSRF token in the `X_XSRF_TOKEN` response header; every mutating POST must carry the latest token as `_sessionTOKEN` in the body (error `-1452` otherwise).
5. Data endpoints: `?_type=vueData|hiddenData|vuejsonData&_tag=<tag>`, XML (`ParaName`/`ParaValue`) or JSON.
6. WiFi passwords: `IF_ACTION=GetPassword` (decrypt with AES-256-CBC, key `sha256(token)`, iv `sha256(reverse(token))[:16]`), write-back via AES + RSA (`encode` field).

### Debug logging

```yaml
logger:
  logs:
    custom_components.zte_router_hass: debug
```

---

## 中文

中兴路由器的 Home Assistant 自定义集成，协议逆向自中兴 Vue Web 管理界面。已在 **ZTE 巡天 BE5100 Pro+（ZXSLC SR7110 / SR7115）**、固件 **V1.0.0.4B8.8000**（Mesh 主机 + 从机）上实测通过，理论上兼容使用同款 `?_type=...&_tag=...` API 风格的中兴路由器。

> **适用范围**：本集成针对中兴**家用 Wi-Fi 路由器**（双频 / Wi-Fi 7 消费级路由）。中兴 **5G CPE** 机型（MC801A / MC888 / MC889 / G5 Ultra）请使用另一个项目 [Kajkac/ZTE-MC-Home-assistant-repo](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo)。

### 功能

- **设备跟踪（device_tracker）**：每个 LAN/WiFi 客户端生成一个跟踪实体（`home`/`not_home`），属性含 IP、主机名、连接类型（LAN/WiFi）、频段、RSSI、是否访客、上级 Mesh 节点、上下行流量。
- **传感器（状态监控类）**：
  - 路由器：运行时间、工作模式、Mesh 状态
  - WAN：连接状态、连接类型、IP 地址、网关、MAC、DNS、连接时长、IPv6 状态/地址、双 WAN 状态
  - Wi-Fi：2.4GHz / 5GHz SSID 及状态、访客 2.4GHz / 5GHz SSID 及状态
  - 系统：指示灯、自动重启
  - 统计：连接设备数、总接收 / 总发送流量
- **诊断类传感器**：设备型号、软件 / 硬件版本、序列号、制造商。
- **开关**：
  - Wi-Fi 双频合一
  - Wi-Fi 频段聚合（MLO）
  - 2.4GHz Wi-Fi 开关、隐藏 2.4GHz SSID
  - 5GHz Wi-Fi 开关、隐藏 5GHz SSID
  - 访客 2.4GHz / 5GHz Wi-Fi 开关
  - MU-MIMO（仅当路由器提供 Wi-Fi 7 高级特性接口时创建）
  - 暂停跟踪器（一键完全停止轮询、对路由器零流量——需要用浏览器管理路由器或使用手机 App 时先打开它，避免与集成抢占 admin 会话；期间所有实体保持最后状态，关闭开关即恢复轮询）
- **按钮**：重启路由器。

> **说明**：*Preamble Puncturing* 开关未实现——该固件 Web 界面只有文案，没有找到可用的 API 接口。

### 安装

**HACS（推荐）**

1. 在 HACS 中添加本仓库（类别：*集成*）。
2. 安装 **ZTE Home Router**。
3. 重启 Home Assistant。

**手动**

将 `custom_components/zte_router_hass` 复制到 HA 的 `config/custom_components/` 目录并重启。

### 配置

设置 → 设备与服务 → **添加集成** → 搜索 **ZTE Home Router**。

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| 主机地址 | `192.168.2.1` | 路由器 IP |
| 用户名 | `admin` | Web 管理用户名 |
| 密码 | `admin` | Web 管理密码 |

选项（配置完成后）：轮询间隔（10–600 秒，默认 30 秒）。

所有实体均关联到配置流程中注册的同一个路由器设备（唯一 ID = 序列号）。

### 注意事项

- **管理员会话抢占**：中兴路由器允许的管理会话数非常有限。会话占满时，集成会自动**踢掉**最旧的会话完成登录——这可能导致已登录路由器的浏览器标签页被登出。
- **Wi-Fi 开关会提交完整表单**：切换任意主 Wi-Fi 开关都会重新提交整个 Wi-Fi 配置（SSID、加密、功率等）。请勿同时在 Web 界面和 HA 中修改 Wi-Fi 设置。
- 所有通信仅发生在局域网内；凭据仅由 Home Assistant 存储。

### 协议要点（供开发者参考）

客户端（`zte_client.py`）实现了逆向出的完整协议：

1. `GET /?_type=loginsceneData&_tag=login_token_json` → 获取 `logintoken` + `_sessionToken`
2. `POST /?_type=loginData&_tag=login_entry`，`Password = sha256(密码 + logintoken)`
3. 若返回 `e_exceed_max_user_preempt`（会话占满）：执行 `preempt_cancel` + `login_preempt` 抢占登录
4. 每个响应的 `X_XSRF_TOKEN` 响应头会轮换 CSRF token；所有写操作 POST 必须在 body 中携带最新 token 作为 `_sessionTOKEN`，否则返回 `-1452`（页面过期）
5. 数据接口：`?_type=vueData|hiddenData|vuejsonData&_tag=<tag>`，返回 XML（`ParaName`/`ParaValue` 对）或 JSON
6. Wi-Fi 密码读写：`IF_ACTION=GetPassword` 取回密文（AES-256-CBC 解密，key=`sha256(token)`，iv=`sha256(reverse(token))[:16]`）；写入时用随机密钥 AES 加密 + RSA 加密密钥（`encode` 字段）

### 调试日志

```yaml
logger:
  logs:
    custom_components.zte_router_hass: debug
```

---

## License / 许可

MIT

---

## 2026-11-02 更新 / Update

### 实体命名 / Entity naming

所有实体按中兴路由器管理界面的中文命名，显示为"设备名 + 实体名"，例如
`ZXSLC SR7115 (192.168.2.3) 2.4GHz Wi-Fi 开关`。

| 开关 / Switch | 说明 |
|---|---|
| Wi-Fi 双频合一 | DualBandSync |
| Wi-Fi 频段聚合 (MLO) | MLOEnable |
| 2.4GHz Wi-Fi / 5GHz Wi-Fi | 主网络开关 |
| 隐藏 2.4GHz / 5GHz SSID | ESSIDHideEnable |
| 访客 2.4GHz / 5GHz Wi-Fi | 访客网络 |
| Wi-Fi 5 兼容网络 | 兼容网络**总开关**（`vue_wifi_merger` 的 `ForceWiFi`）**已实测** |
| Wi-Fi 5 兼容网络 2.4GHz / 5GHz | 兼容网络的**分频开关**（AP3 / AP7 的 `Enable`，可单独开关） |
| 暂停跟踪器 | 纯本地开关：开启后集成**完全不访问路由器**（实体保持最后状态），方便无干扰地使用路由器 Web 界面 / 手机 App；关闭即恢复轮询 |
| MU-MIMO | Wi-Fi 7 特性 |

> 「Wi-Fi 5 兼容网络」在路由器页面上是 1 个总开关 + 2 个频段开关，三者互相独立：
> 总开关对应 `ForceWiFi`，两个频段对应 `DEV.WIFI.AP3` / `DEV.WIFI.AP7` 的 `Enable`。
> 路由器有个特性：关掉总开关后两个频段的 `Enable` 仍是开的（只是不广播 SSID），
> 重新打开总开关即原样恢复。为避免 HA 里出现「总开关关了、频段还显示开」的误导，
> 两个频段开关在 HA 里显示的是**生效状态**（总开关开 且 该频段开）：
> 总开关关闭时频段开关显示为关；此时打开任一频段会自动把总开关一起打开。
> 总开关打开时若两个频段都关着，会自动把两个频段一起打开。

新增传感器：`2.4GHz/5GHz Wi-Fi 信道`、`2.4GHz/5GHz 理论速率`、
`Wi-Fi 5 兼容网络 2.4GHz/5GHz 名称`、`Wi-Fi 定时关闭` + `定时关闭时段`、
`IPv6 LLA`、`IPv6 网关`。

> 说明：`Wi-Fi 定时关闭` 该固件只提供读写接口 `vue_internet_advanced_rftimer_data`
> （hiddenData），当前做成了**只读传感器**；`Wi-Fi 中继`（`wlan_link_data`）
> 与 `Preamble Puncturing` 在下发的固件里没有可用写接口，故未做成开关；
> `端口状态` 在桥接（Bridge）模式下接口不返回数据。

### 刷新速度 / Refresh speed

轮询分两档，均可在「配置 → 选项」调整：

- **状态刷新间隔**（默认 5 秒，最小 3 秒）：Wi-Fi / WAN / MU-MIMO，手机 App 或
  Web 界面改了开关，几秒内同步到 HA。
- **完整刷新间隔**（默认 30 秒）：设备列表、Mesh 拓扑、指示灯等。

### 品牌图标 / Brand icon

`custom_components/zte_router_hass/brand/icon.png`（256×256）、`logo.png`、
`dark_icon.png`。更新后需重启 Home Assistant，浏览器可强制刷新一次缓存。

### 已知问题 / Known issues

- 管理页面「设备」里若出现大量 `iPhone`、`空调伴侣` 等单实体设备，来自另一个
  集成 `zte_tracker`（juacas/zte_tracker）；两者同时安装会重复登记设备，
  建议只保留本集成。

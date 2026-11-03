"""ZTE router web API client.

Reverse-engineered from the ZTE Vue web console (ZXSLC SR7110/SR7115,
firmware V1.0.0.4B8.8000). Also known to work with similar ZTE firmware
using the ``_type=...&_tag=...`` API style.

Key protocol details (all verified against live routers):

* Login: GET ``?_type=loginsceneData&_tag=login_token_json`` for
  ``logintoken``/``_sessionToken``, then POST
  ``?_type=loginData&_tag=login_entry`` with
  ``Password = sha256(password + logintoken)``.
* Session preemption: when login returns ``e_exceed_max_user_preempt``
  (max admin sessions), POST ``action=preempt_cancel`` followed by
  ``?_type=loginData&_tag=login_preempt`` with ``preempt_sessid``.
* CSRF token rotation: every response may carry a fresh ``X_XSRF_TOKEN``
  header. Every mutating POST must include the latest token in the body
  as ``_sessionTOKEN``, otherwise the router answers error ``-1452``
  ("page expired").
* GET data: ``?_type=vueData|hiddenData|vuejsonData&_tag=<tag>`` returns
  either XML (``ParaName``/``ParaValue`` pairs inside ``Instance`` nodes)
  or JSON.
* WiFi password round-trip:
  - Read: POST ``?_type=vueData&_tag=vuecfg_data`` with
    ``IF_ACTION=GetPassword`` returns an AES encrypted ``KeyPassphrase``.
    Decrypt with AES-256-CBC/ZeroPadding, key = ``sha256(token)``,
    iv = ``sha256(reverse(token))[:16]`` where ``token`` is the XSRF
    token that was current at request time.
  - Write: encrypt the password with AES-256-CBC/ZeroPadding using two
    random 16-digit strings ``d``/``s`` (key = ``sha256(d)``,
    iv = ``sha256(s)[:16]``) and append ``encode`` = base64(RSA-PKCS1v15
    public-key encryption of ``d + "+" + s``).
* Mutations: POST to the same ``_tag`` used for reading, with
  ``IF_ACTION=Apply`` (or ``Restart``) plus the full parameter set.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import random
import re
import threading
import time
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import unquote, urlencode

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_LOGGER = logging.getLogger(__name__)

# RSA public key embedded in the router's web UI (app.*.js -> encodeKey)
RSA_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAodPTerkUVCYmv28SOfRV
7UKHVujx/HjCUTAWy9l0L5H0JV0LfDudTdMNPEKloZsNam3YrtEnq6jqMLJV4ASb
1d6axmIgJ636wyTUS99gj4BKs6bQSTUSE8h/QkUYv4gEIt3saMS0pZpd90y6+B/9
hZxZE/RKU8e+zgRqp1/762TB7vcjtjOwXRDEL0w71Jk9i8VUQ59MR1Uj5E8X3WIc
fYSK5RWBkMhfaTRM6ozS9Bqhi40xlSOb3GBxCmliCifOJNLoO9kFoWgAIw5hkSIb
GH+4Csop9Uy8VvmmB+B3ubFLN35qIa5OG5+SDXn4L7FeAA5lRiGxRi8tsWrtew8w
nwIDAQAB
-----END PUBLIC KEY-----"""

ERROR_PAGE_EXPIRED = "-1452"

T_VUE = "vueData"
T_HIDDEN = "hiddenData"
T_VUEJSON = "vuejsonData"
T_LOGIN_SCENE = "loginsceneData"
T_LOGIN = "loginData"

# API tags (grouped by feature, matching the web console)
TAG_LOGIN_TOKEN = "login_token_json"
TAG_LOGIN_ENTRY = "login_entry"
TAG_LOGIN_PREEMPT = "login_preempt"
TAG_DEVICE_INFO = "home_managreg_lua"
TAG_WAN_MAIN = "vue_mainwan_data"
TAG_WAN_INTERNET = "home_internetreg_lua"
TAG_DUAL_WAN = "vue_dualwan_data"
TAG_WIFI_MAIN = "wifi_advancedssid_data"
TAG_WIFI_GUEST = "advanced_separated_data"
TAG_WIFI7_SPECIAL = "wifi7_special_data"
TAG_LED = "vue_managdiagLed_data"
TAG_RESTART_CFG = "smart_restart_data"
TAG_LAN_DEVICES = "localnet_lan_info_lua"
TAG_TOPO = "vue_topo_data"
TAG_REBOOT = "vue_derestart_data"
# cheapest endpoint that answers with data (used to rotate the CSRF token)
TAG_HEARTBEAT = "heartbeat_lua"
TAG_CFG_PASSWORD = "vuecfg_data"
TAG_WIFI_COMPAT = "vue_wifi_merger"
TAG_WIFI_RADIO = "wlanConfig_data"
TAG_WIFI_TIMER = "vue_internet_advanced_rftimer_data"
TAG_ETHPORT = "vue_internet_ethport_data"
# authoritative source for the dual-band-sync / MLO flags (the web UI reads
# these from here as well; ``wifi_advancedssid_data`` reports stale values)
TAG_DUALBAND = "dualband_lua"

COMPAT_INST_2G = "DEV.WIFI.AP3"
COMPAT_INST_5G = "DEV.WIFI.AP7"


class ZTEAuthError(Exception):
    """Authentication failed."""


class ZTEConnectionError(Exception):
    """Cannot reach the router."""


class ZTECommandError(Exception):
    """The router rejected a command."""


def _rand_digits(n: int = 16) -> str:
    """Random 16-digit string, mirroring JS randomNum(16)."""
    return "".join(str(random.randint(0, 9)) for _ in range(n))


def _is_page_expired(err: Exception) -> bool:
    """True when the router answered -1452 ("页面过期")."""
    return ERROR_PAGE_EXPIRED in str(err)


class ZTERouterClient:
    """Synchronous client for the ZTE router web API.

    All methods are blocking; the integration runs them in executors.
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        timeout: int = 15,
    ) -> None:
        self.host = host
        self.base_url = f"http://{host}"
        self.username = username
        self.password = password
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                ),
                "X-Requested-With": "XMLHttpRequest",
                "Referer": self.base_url + "/",
            }
        )
        self._session.hooks["response"] = [self._capture_token]
        self._token = ""
        # True while _token still comes from the login response. The firmware
        # refuses mutating POSTs that carry a login-issued token with -1452
        # ("page expired"): the token has to be refreshed by a normal data
        # response first. See _refresh_token().
        self._token_from_login = False
        self._logged_in = False
        # RLock: every HTTP round trip (GET/POST) is serialized, including the
        # token rotation done by the response hook and any re-login retries.
        # The router rotates X_XSRF_TOKEN on EVERY response, so a control
        # request interleaved with a background poll would otherwise submit a
        # stale _sessionTOKEN and fail with -1452 ("页面过期").
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # low level helpers
    # ------------------------------------------------------------------
    def _capture_token(self, response: requests.Response, *_args, **_kwargs):
        token = response.headers.get("X_XSRF_TOKEN")
        if token:
            self._token = token
        return response

    @staticmethod
    def _parse_xml(content: str) -> dict[str, Any]:
        try:
            root = ET.fromstring(content)
        except ET.ParseError as err:
            _LOGGER.warning("XML parse error: %s", err)
            return {"raw": content[:500]}
        result: dict[str, Any] = {"instances": []}
        for field in ("IF_ERRORSTR", "IF_ERRORPARAM", "IF_ERRORTYPE", "IF_ERRORID"):
            elem = root.find(field)
            if elem is not None and elem.text:
                result[field] = elem.text
        for instance in root.findall(".//Instance"):
            data: dict[str, str] = {}
            current: str | None = None
            for node in instance:
                if node.tag == "ParaName":
                    current = node.text
                elif node.tag == "ParaValue" and current is not None:
                    data[current] = unquote(node.text or "")
                    current = None
            if data:
                result["instances"].append(data)
        return result

    def _decode_body(self, text: str) -> dict[str, Any]:
        stripped = text.strip()
        if stripped.startswith("<?xml") or stripped.startswith("<ajax_response_xml_root"):
            return self._parse_xml(stripped)
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return json.loads(stripped)
            except ValueError:
                pass
        return {"raw": stripped[:500]}

    def _is_html(self, text: str) -> bool:
        return bool(re.match(r"\s*(<!DOCTYPE|<html)", text, re.I))

    def _get(self, tag: str, rtype: str = T_VUE) -> dict[str, Any]:
        url = f"{self.base_url}/?_type={rtype}&_tag={tag}&_={int(time.time() * 1000)}"
        with self._lock:
            response = self._session.get(url, timeout=self.timeout)
            text = response.text
            if self._is_html(text):
                # session lost -> re-login once
                _LOGGER.debug("Session lost while GET %s, re-logging in", tag)
                self.login()
                response = self._session.get(url, timeout=self.timeout)
                text = response.text
                if self._is_html(text):
                    raise ZTEConnectionError(f"GET {tag} returned login page")
            self._token_from_login = False
            return self._decode_body(text)

    def _post(self, tag: str, form: dict[str, Any], rtype: str = T_VUE) -> dict[str, Any]:
        url = f"{self.base_url}/?_type={rtype}&_tag={tag}"
        with self._lock:
            if self._token_from_login:
                # a login token is not accepted for writes; rotate it first
                self._refresh_token()
            body = dict(form)
            body["_sessionTOKEN"] = self._token
            response = self._session.post(url, data=body, timeout=self.timeout)
            text = response.text
            if self._is_html(text):
                self.login()
                self._refresh_token()
                body["_sessionTOKEN"] = self._token
                response = self._session.post(url, data=body, timeout=self.timeout)
                text = response.text
                if self._is_html(text):
                    raise ZTEConnectionError(f"POST {tag} returned login page")
            data = self._decode_body(text)
            error_id = str(data.get("IF_ERRORID", data.get("code", "0")))
            if error_id == ERROR_PAGE_EXPIRED:
                # token raced (or was rejected): re-login, rotate, retry once
                _LOGGER.debug("Page expired on POST %s, retrying with fresh token", tag)
                self.login()
                self._refresh_token()
                body["_sessionTOKEN"] = self._token
                response = self._session.post(url, data=body, timeout=self.timeout)
                data = self._decode_body(response.text)
                error_id = str(data.get("IF_ERRORID", data.get("code", "0")))
                if error_id == ERROR_PAGE_EXPIRED:
                    # some firmware revisions accept the write and only then
                    # report -1452 (e.g. radio restarts) - let the caller verify
                    raise ZTECommandError(
                        f"POST {tag} failed: {data.get('IF_ERRORSTR', 'page expired')} "
                        f"(id={error_id})"
                    )
            if error_id not in ("0", "SUCC"):
                raise ZTECommandError(
                    f"POST {tag} failed: {data.get('IF_ERRORSTR', data.get('errPara', error_id))}"
                    f" (id={error_id})"
                )
            return data

    # ------------------------------------------------------------------
    # login / session
    # ------------------------------------------------------------------
    def login(self) -> None:
        """Authenticate, preempting an existing admin session if needed."""
        with self._lock:
            self._session.cookies.clear()
            self._token = ""
            token_url = f"{self.base_url}/?_type={T_LOGIN_SCENE}&_tag={TAG_LOGIN_TOKEN}"
            try:
                token_data = self._session.get(token_url, timeout=self.timeout).json()
            except (requests.RequestException, ValueError) as err:
                raise ZTEConnectionError(f"Cannot reach router {self.host}: {err}") from err
            login_token = token_data.get("logintoken", "")
            form = {
                "Username": self.username,
                "Password": hashlib.sha256(
                    (self.password + login_token).encode()
                ).hexdigest(),
                "action": "login",
                "Frm_Logintoken": login_token,
                "captchaCode": "",
                "_sessionTOKEN": token_data.get("_sessionToken", ""),
            }
            login_url = f"{self.base_url}/?_type={T_LOGIN}&_tag={TAG_LOGIN_ENTRY}"
            try:
                result = self._session.post(login_url, data=form, timeout=self.timeout).json()
            except (requests.RequestException, ValueError) as err:
                raise ZTEConnectionError(f"Login request failed: {err}") from err
            self._token = result.get("sess_token", self._token)
            err_type = result.get("loginErrType", "")
            if err_type == "e_exceed_max_user_preempt" and self._token:
                # kick the stale session, then confirm preemption
                self._session.post(
                    f"{self.base_url}/",
                    data={"action": "preempt_cancel", "_sessionTOKEN": self._token},
                    timeout=self.timeout,
                )
                preempt = self._session.post(
                    f"{self.base_url}/?_type={T_LOGIN}&_tag={TAG_LOGIN_PREEMPT}",
                    data={"preempt_sessid": self._token, "action": "preempt"},
                    timeout=self.timeout,
                ).json()
                if not preempt.get("login_need_refresh"):
                    raise ZTEAuthError("Preempting the existing admin session failed")
                self._token = preempt.get("sess_token", self._token)
            elif not result.get("login_need_refresh"):
                raise ZTEAuthError("Login failed, check username/password")
            self._logged_in = True
            self._token_from_login = True
            _LOGGER.debug("Logged in to %s", self.host)

    def _refresh_token(self) -> None:
        """Trade the login token for a page token via a cheap data request.

        The firmware only accepts mutating POSTs whose ``_sessionTOKEN`` was
        issued by a normal API response; the token returned by the login
        response is rejected with ``-1452``. Any GET rotates it.
        """
        try:
            self._get(TAG_HEARTBEAT)
        except (ZTEConnectionError, requests.RequestException) as err:
            _LOGGER.debug("Token refresh failed, keeping current token: %s", err)
            return
        self._token_from_login = False

    def _ensure_login(self) -> None:
        if not self._logged_in:
            self.login()

    # ------------------------------------------------------------------
    # crypto helpers (password round-trip)
    # ------------------------------------------------------------------
    @staticmethod
    def _decode_para(value_b64: str, token: str) -> str:
        """JS decodePara: AES key=sha256(token), iv=sha256(reversed(token))[:16]."""
        key = hashlib.sha256(token.encode()).digest()
        iv = hashlib.sha256(token[::-1].encode()).digest()[:16]
        dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        raw = dec.update(base64.b64decode(value_b64)) + dec.finalize()
        return raw.rstrip(b"\x00").decode("utf-8", "replace")

    @staticmethod
    def _encode_para(value: str, d: str, s: str) -> str:
        """JS encodePara: AES key=sha256(d), iv=sha256(s)[:16], ZeroPadding."""
        key = hashlib.sha256(d.encode()).digest()
        iv = hashlib.sha256(s.encode()).digest()[:16]
        data = value.encode()
        if len(data) % 16 or not data:
            data += b"\x00" * (16 - len(data) % 16)
        enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        return base64.b64encode(enc.update(data) + enc.finalize()).decode()

    @staticmethod
    def _encode_key(d: str, s: str) -> str:
        """JS encodeKey: RSA-PKCS1v15 encrypt of ``d+"+"+s``, base64."""
        pub = serialization.load_pem_public_key(RSA_PUBLIC_KEY.encode())
        blob = pub.encrypt((d + "+" + s).encode(), asym_padding.PKCS1v15())
        return base64.b64encode(blob).decode()

    def _get_plaintext_password(self, inst_id: str) -> str:
        """Fetch and decrypt a WiFi passphrase (e.g. DEV.WIFI.AP1)."""
        # the passphrase is AES-encrypted with the token that was current at
        # request time, so the token must be captured atomically with the POST
        with self._lock:
            token_at_call = self._token
            result = self._post(
                TAG_CFG_PASSWORD,
                {
                    "IF_ACTION": "GetPassword",
                    "ACTION_TYPE": "wlanPassword",
                    "_InstID_PASS": f"{inst_id}.PSK1",
                    "PASSTYPE": "PSK",
                },
            )
        encrypted = None
        for instance in result.get("instances", []):
            if "KeyPassphrase" in instance:
                encrypted = instance["KeyPassphrase"]
        if not encrypted and isinstance(result.get("data"), dict):
            arr = result["data"].get("OBJ_WLANPSK_ID") or []
            if arr:
                encrypted = arr[0].get("KeyPassphrase")
        if not encrypted:
            raise ZTECommandError("GetPassword returned no KeyPassphrase")
        return self._decode_para(encrypted, token_at_call)

    def _encrypted_password_block(self, plaintext: str) -> tuple[str, str]:
        """Encrypt a passphrase: returns (encrypted_value, encode_key)."""
        d, s = _rand_digits(), _rand_digits()
        return self._encode_para(plaintext, d, s), self._encode_key(d, s)

    # ------------------------------------------------------------------
    # read APIs
    # ------------------------------------------------------------------
    def get_device_info(self) -> dict[str, Any]:
        self._ensure_login()
        data = self._get(TAG_DEVICE_INFO)
        info: dict[str, Any] = {}
        for instance in data.get("instances", []):
            iid = instance.get("_InstID")
            if iid == "IGD":
                # multiple IGD instances exist; only take fields actually present
                if instance.get("ModelName"):
                    info["model"] = instance["ModelName"]
                if instance.get("SoftwareVer"):
                    info["software_version"] = instance["SoftwareVer"]
                if instance.get("HardwareVer"):
                    info["hardware_version"] = instance["HardwareVer"]
                if instance.get("UpTime"):
                    try:
                        info["uptime_seconds"] = int(float(instance["UpTime"]))
                    except ValueError:
                        pass
                if instance.get("ManuFacturer"):
                    info["manufacturer"] = instance["ManuFacturer"]
                if instance.get("SerialNumber"):
                    info["serial_number"] = instance["SerialNumber"]
                if instance.get("BootVer"):
                    info["boot_version"] = instance["BootVer"]
            elif "_InstID" not in instance and "WEBTitle" in instance:
                info["web_title"] = instance.get("WEBTitle", "")
                info["mode"] = instance.get("Mode", "")
                info["mesh_enabled"] = instance.get("MeshEnable") == "1"
                info["work_mode"] = instance.get("curWorkMode", "")
        return info

    def get_wan_status(self) -> dict[str, Any]:
        self._ensure_login()
        wan: dict[str, Any] = {"wan1": {}, "wan2": {}, "ipv6": {}, "dual_wan": {}}
        main = self._get(TAG_WAN_MAIN)
        for instance in main.get("instances", []):
            iid = instance.get("_InstID", "")
            if iid.startswith("IGD.WD1.WCD1."):
                wan["wan1"].update(
                    {
                        "enabled": instance.get("Enable") == "1",
                        "connection_type": instance.get("WANCName", ""),
                        "wan_type": instance.get("WANCTYPE", ""),
                        "status": instance.get("Status", ""),
                        "vlan_id": instance.get("VLANID", "0"),
                        "rx_bytes": int(float(instance.get("RxBytes", 0) or 0)),
                        "tx_bytes": int(float(instance.get("TxBytes", 0) or 0)),
                        "rx_packets": int(float(instance.get("RxPackets", 0) or 0)),
                        "tx_packets": int(float(instance.get("TxPackets", 0) or 0)),
                    }
                )
            elif "WANPortStatus" in instance:
                wan["wan1"]["port_status"] = instance["WANPortStatus"]
            elif "SecWanLink" in instance:
                wan["dual_wan"] = {
                    "enabled": instance.get("Enable") == "1",
                    "mode": instance.get("SecWanLink", "0"),
                }
        internet = self._get(TAG_WAN_INTERNET)
        for instance in internet.get("instances", []):
            if instance.get("IpMode") in ("Both", "IPv4") and "IPAddress" in instance:
                wan["wan1"].update(
                    {
                        "connection_status": instance.get("ConnStatus", ""),
                        "ip_address": instance.get("IPAddress", ""),
                        "subnet_mask": instance.get("SubnetMask", ""),
                        "gateway": instance.get("GateWay", ""),
                        "dns1": instance.get("DNS1", ""),
                        "dns2": instance.get("DNS2", ""),
                        "dns3": instance.get("DNS3", ""),
                        "mac_address": instance.get("MacAddr", ""),
                        "wan_uptime_seconds": int(float(instance.get("UpTime", 0) or 0)),
                    }
                )
            if instance.get("IpMode") in ("Both", "IPv6") or "ConnStatus6" in instance:
                wan["ipv6"] = {
                    "connection_status": instance.get("ConnStatus6", ""),
                    "lla": instance.get("LLA", ""),
                    "global_address": instance.get("Gua1", ""),
                    "gateway": instance.get("Gateway6", ""),
                    "ip_mode": instance.get("IpMode", ""),
                    "uptime_seconds": int(float(instance.get("UpTimeV6", 0) or 0)),
                }
        return wan

    def get_dual_band_flags(self) -> tuple[bool, bool]:
        """Return ``(dual_band_sync, mlo_enabled)`` from the authoritative API.

        The web console drives its two switches from ``dualband_lua`` while
        ``wifi_advancedssid_data`` keeps a separate, frequently stale copy of
        ``DualBandSync`` / ``MLOEnable``. Reading the stale copy makes the HA
        switches show the opposite of reality, so always prefer this endpoint.
        """
        raw = self._get(TAG_DUALBAND, rtype=T_VUEJSON)
        data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
        for attempt in range(2):
            try:
                dual = str(data["OBJ_DUALBANDSYNC_ID"][0]["DualBandSync"]) == "1"
                mlo = str(data["OBJ_MLO_ID"][0]["MLOEnable"]) == "1"
                return dual, mlo
            except (KeyError, IndexError, TypeError):
                if attempt:
                    break
                # the payload occasionally comes back partially filled
                time.sleep(0.4)
                raw = self._get(TAG_DUALBAND, rtype=T_VUEJSON)
                data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
        raise ZTECommandError("dualband_lua returned an unexpected payload")

    def get_wifi_status(self) -> dict[str, Any]:
        self._ensure_login()
        data = self._get(TAG_WIFI_MAIN)
        wifi: dict[str, Any] = {
            "main": {"2.4ghz": {}, "5ghz": {}},
            "dual_band_sync": False,
            "mlo_enabled": False,
        }
        radios: dict[str, dict[str, Any]] = {}
        for instance in data.get("instances", []):
            iid = instance.get("_InstID", "")
            if iid == "DEV.WIFI.AP1":
                wifi["main"]["2.4ghz"] = {
                    "enabled": instance.get("Enable") == "1",
                    "ssid": instance.get("ESSID", ""),
                    "hidden": instance.get("ESSIDHideEnable") == "1",
                    "security": instance.get("BeaconType", ""),
                    "inst_id": iid,
                    "radio_id": instance.get("WLANViewName", "DEV.WIFI.RD1"),
                }
            elif iid == "DEV.WIFI.AP5":
                wifi["main"]["5ghz"] = {
                    "enabled": instance.get("Enable") == "1",
                    "ssid": instance.get("ESSID", ""),
                    "hidden": instance.get("ESSIDHideEnable") == "1",
                    "security": instance.get("BeaconType", ""),
                    "inst_id": iid,
                    "radio_id": instance.get("WLANViewName", "DEV.WIFI.RD2"),
                }
            elif iid in ("DEV.WIFI.RD1", "DEV.WIFI.RD2"):
                radios[iid] = {
                    "band": instance.get("Band", ""),
                    "power_enhance": instance.get("PowerEnhance", "1"),
                    "tx_power": instance.get("TxPower", "100%"),
                    "radio_status": instance.get("RadioStatus", "1"),
                    "standard": instance.get("Standard", ""),
                }
            elif "_InstID" not in instance and "DualBandSync" in instance:
                wifi["dual_band_sync"] = instance["DualBandSync"] == "1"
            elif "_InstID" not in instance and "MLOEnable" in instance:
                wifi["mlo_enabled"] = instance["MLOEnable"] == "1"
        for key in ("2.4ghz", "5ghz"):
            radio = radios.get(wifi["main"][key].get("radio_id", ""))
            if radio:
                wifi["main"][key].update(radio)
        try:
            wifi["dual_band_sync"], wifi["mlo_enabled"] = self.get_dual_band_flags()
        except (ZTEConnectionError, ZTECommandError, KeyError, IndexError, TypeError, ValueError):
            # keep the (possibly stale) values from the main form as fallback
            pass
        return wifi

    def get_guest_wifi_status(self) -> dict[str, Any]:
        self._ensure_login()
        data = self._get(TAG_WIFI_GUEST)
        guest: dict[str, Any] = {"2.4ghz": {}, "5ghz": {}}
        mapping = {"DEV.WIFI.AP2": "2.4ghz", "DEV.WIFI.AP6": "5ghz"}
        for instance in data.get("instances", []):
            key = mapping.get(instance.get("_InstID", ""))
            if key:
                guest[key] = {
                    "enabled": instance.get("Enable") == "1",
                    "ssid": instance.get("ESSID", ""),
                    "hidden": instance.get("ESSIDHideEnable") == "1",
                    "limit_enabled": instance.get("LimitEnable") == "1",
                    "inst_id": instance["_InstID"],
                }
        return guest

    def get_mumimo_status(self) -> dict[str, Any] | None:
        """WiFi7 special features (MU-MIMO/MRU). None when unsupported."""
        self._ensure_login()
        data = self._get(TAG_WIFI7_SPECIAL, rtype=T_VUEJSON)
        arr = (data.get("data") or {}).get("OBJ_WIFISPECIAL_ID") if isinstance(
            data.get("data"), dict
        ) else data.get("OBJ_WIFISPECIAL_ID")
        if not arr:
            return None
        first = arr[0]
        return {
            "mumimo": first.get("DownMUMIMO") == "1" or first.get("UPMUMIMO") == "1",
            "mru": first.get("MRUEnable") == "1",
            "instances": arr,
        }

    def get_system_settings(self) -> dict[str, Any]:
        self._ensure_login()
        system: dict[str, Any] = {"led": {}, "auto_restart": {}}
        led = self._get(TAG_LED, rtype=T_HIDDEN)
        for instance in led.get("instances", []):
            if "LedSchedule" in instance:
                system["led"] = {
                    "schedule_enabled": instance.get("LedSchedule") == "1",
                    "open_time": instance.get("LedOpenTime", ""),
                    "close_time": instance.get("LedCloseTime", ""),
                }
        restart = self._get(TAG_RESTART_CFG)
        for instance in restart.get("instances", []):
            if "Enable" in instance and "Day" in instance:
                system["auto_restart"] = {
                    "enabled": instance.get("Enable") == "1",
                    "day": instance.get("Day", ""),
                    "time": instance.get("RealTime1", ""),
                }
        return system

    def get_lan_devices(self) -> list[dict[str, Any]]:
        self._ensure_login()
        data = self._get(TAG_LAN_DEVICES)
        devices: list[dict[str, Any]] = []
        for instance in data.get("instances", []):
            mac = instance.get("MACAddress")
            if not mac or mac == "00:00:00:00:00:00":
                continue
            connect_type = instance.get("ConnectType", "0")
            devices.append(
                {
                    "mac": mac.lower(),
                    "ip": instance.get("IPAddress", ""),
                    "hostname": instance.get("HostName")
                    or instance.get("DevName")
                    or instance.get("DisplayedType")
                    or "unknown",
                    "active": instance.get("Active") == "1",
                    "connection_type": "WiFi" if connect_type == "1" else "LAN",
                    "interface": instance.get("Interface", ""),
                    "band": instance.get("Band", ""),
                    "rssi": instance.get("Rssi", ""),
                    "is_guest": instance.get("isGuestAcessDev") == "1",
                    "parent_device": instance.get("ParentDeviceName", ""),
                    "device_type": instance.get("DisplayedType", ""),
                    "online_time": instance.get("OnlineTime", ""),
                    "down_speed": float(instance.get("DownloadSpeed", 0) or 0),
                    "up_speed": float(instance.get("UploadSpeed", 0) or 0),
                    "rx_bytes": int(float(instance.get("BytesReceived", 0) or 0)),
                    "tx_bytes": int(float(instance.get("BytesSend", 0) or 0)),
                }
            )
        return devices

    def get_topology(self) -> dict[str, Any]:
        """Mesh topology: controller + agent nodes (JSON)."""
        self._ensure_login()
        try:
            data = self._get(TAG_TOPO)
        except (ZTEConnectionError, ZTECommandError):
            return {}
        topo: dict[str, Any] = {"controller": {}, "agents": []}
        controller = data.get("controllerData") or {}
        if controller:
            topo["controller"] = {
                "name": controller.get("DeviceName", ""),
                "model": controller.get("ModelName", ""),
                "ip": controller.get("IpAddr", ""),
                "mac": controller.get("MacAddr", ""),
                "software": controller.get("SoftwareVer", ""),
            }
        for layer in ("agentlay1", "agentlay2", "agentlay3"):
            for agent in data.get(layer) or []:
                if isinstance(agent, dict):
                    topo["agents"].append(
                        {
                            "name": agent.get("DeviceName", ""),
                            "model": agent.get("ModelName", ""),
                            "ip": agent.get("IpAddr", ""),
                            "mac": agent.get("MacAddr", ""),
                            "access_type": agent.get("AccessType", ""),
                            "connected_devices": agent.get("accdevCount", 0),
                        }
                    )
        return topo

    def get_wifi_compat(self) -> dict[str, Any]:
        """Wi-Fi 5 compatibility network (the extra "wifi5" SSIDs)."""
        self._ensure_login()
        data = self._get(TAG_WIFI_COMPAT)
        compat: dict[str, Any] = {"force_wifi": False, "2.4ghz": {}, "5ghz": {}}
        mapping = {COMPAT_INST_2G: "2.4ghz", COMPAT_INST_5G: "5ghz"}
        for instance in data.get("instances", []):
            key = mapping.get(instance.get("_InstID", ""))
            if not key:
                continue
            compat[key] = {
                "enabled": instance.get("Enable") == "1",
                "ssid": instance.get("ESSID", ""),
                "hidden": instance.get("ESSIDHideEnable") == "1",
                "beacon_type": instance.get("BeaconType", "11i"),
                "wpa_auth": instance.get("WPAAuthMode", "PSKAuthentication"),
                "11i_auth": instance.get("11iAuthMode", "PSKAuthentication"),
                "wpa_enc": instance.get("WPAEncryptType", "AESEncryption"),
                "11i_enc": instance.get("11iEncryptType", "AESEncryption"),
            }
            compat["force_wifi"] = instance.get("ForceWiFi") == "1"
        return compat

    def get_wifi_radio(self) -> dict[str, Any]:
        """Radio parameters: channel, bandwidth, standard, max rate."""
        self._ensure_login()
        data = self._get(TAG_WIFI_RADIO)
        radio: dict[str, Any] = {"2.4ghz": {}, "5ghz": {}}
        mapping = {"DEV.WIFI.RD1": "2.4ghz", "DEV.WIFI.RD2": "5ghz"}
        for instance in data.get("instances", []):
            key = mapping.get(instance.get("_InstID", ""))
            if not key:
                continue
            rate = instance.get("MaxRate", "")
            try:
                max_rate = round(int(float(rate)) / 1000, 1)
            except (TypeError, ValueError):
                max_rate = None
            radio[key] = {
                "channel": instance.get("Channel", ""),
                "auto_channel": instance.get("AutoChannelEnabled") == "1",
                "bandwidth": instance.get("BandWidth", ""),
                "standard": instance.get("Standard", ""),
                "max_rate_mbps": max_rate,
            }
        return radio

    def get_wifi_timer(self) -> dict[str, Any]:
        """Wi-Fi schedule (定时关闭) settings."""
        self._ensure_login()
        data = self._get(TAG_WIFI_TIMER, rtype=T_HIDDEN)
        timer: dict[str, Any] = {"enabled": False, "start": "", "end": ""}
        for instance in data.get("instances", []):
            if "TimerEnable" in instance:
                timer["enabled"] = instance.get("TimerEnable") == "1"
            if "TimeStartHour" in instance:
                try:
                    timer["start"] = (
                        f"{int(instance.get('TimeStartHour', 0)):02d}:"
                        f"{int(instance.get('TimeStartMin', 0)):02d}"
                    )
                    timer["end"] = (
                        f"{int(instance.get('TimeEndHour', 0)):02d}:"
                        f"{int(instance.get('TimeEndMin', 0)):02d}"
                    )
                except (TypeError, ValueError):
                    pass
        return timer

    def get_port_status(self) -> dict[str, Any]:
        """Ethernet port status (端口状态). Empty dict when unsupported."""
        self._ensure_login()
        try:
            data = self._get(TAG_ETHPORT)
        except (ZTEConnectionError, ZTECommandError):
            return {}
        ports: dict[str, Any] = {}
        for instance in data.get("instances", []):
            iid = instance.get("_InstID", "")
            if not iid:
                continue
            link_state = instance.get("LinkStatus") or instance.get("Status")
            port = {
                "name": instance.get("PortName") or instance.get("PortType") or iid,
                "link": link_state,
                "speed": instance.get("Speed") or instance.get("NegotiatedSpeed"),
                "max_speed": instance.get("MaxSpeed"),
                "rx_rate": instance.get("RxRate"),
                "tx_rate": instance.get("TxRate"),
            }
            if any(v is not None for v in (link_state, port["speed"], port["rx_rate"])):
                ports[iid] = port
        return ports

    def set_wifi_compat(
        self,
        enabled: bool | None = None,
        enable_2g: bool | None = None,
        enable_5g: bool | None = None,
    ) -> None:
        """Configure the Wi-Fi 5 compatibility network.

        The router page exposes three independent switches:

        * ``ForceWiFi`` — the page master switch (兼容网络总开关)
        * ``EnableI`` on AP3 — the 2.4GHz band of the compat network
        * ``EnableY`` on AP7 — the 5GHz band of the compat network

        ``enabled`` drives the master switch, ``enable_2g``/``enable_5g``
        drive the two band switches. Anything left as ``None`` keeps its
        current value, so a band can be toggled without touching the other.
        """
        self._ensure_login()
        data = self._get(TAG_WIFI_COMPAT)
        insts = {
            inst.get("_InstID", ""): inst
            for inst in data.get("instances", [])
            if inst.get("_InstID") in (COMPAT_INST_2G, COMPAT_INST_5G)
        }
        if COMPAT_INST_2G not in insts or COMPAT_INST_5G not in insts:
            raise ZTECommandError(
                "This router does not expose the Wi-Fi 5 compatibility network"
            )
        inst_2g, inst_5g = insts[COMPAT_INST_2G], insts[COMPAT_INST_5G]
        cur_2g = inst_2g.get("Enable") == "1"
        cur_5g = inst_5g.get("Enable") == "1"
        cur_master = inst_2g.get("ForceWiFi") == "1" or inst_5g.get("ForceWiFi") == "1"

        if enabled is not None:
            master = enabled
            # master ON while both bands are off would be a no-op: turn them on
            if enabled and not cur_2g and not cur_5g:
                if enable_2g is None:
                    enable_2g = True
                if enable_5g is None:
                    enable_5g = True
        else:
            master = cur_master
        if (enable_2g or enable_5g) and enabled is None:
            # turning a band on implies the master switch
            master = True

        pwd_2g = self._get_plaintext_password(COMPAT_INST_2G)
        pwd_5g = self._get_plaintext_password(COMPAT_INST_5G)
        d, s = _rand_digits(), _rand_digits()
        enc_2g = self._encode_para(pwd_2g, d, s)
        enc_5g = self._encode_para(pwd_5g, d, s)
        flag = "1" if master else "0"
        form = {
            "IF_ACTION": "Apply",
            "SubmitFlag": "SSIDIY",
            "ESSIDI": inst_2g.get("ESSID", ""),
            "ESSIDY": inst_5g.get("ESSID", ""),
            "EnableI": "1" if (cur_2g if enable_2g is None else enable_2g) else "0",
            "EnableY": "1" if (cur_5g if enable_5g is None else enable_5g) else "0",
            "ForceWiFi": flag,
            "KeyPassphraseI": enc_2g,
            "KeyPassphraseY": enc_5g,
            "HideKeyPassphraseI": enc_2g,
            "HideKeyPassphraseY": enc_5g,
            "_InstID_PSKI": f"{COMPAT_INST_2G}.PSK1",
            "_InstID_PSKY": f"{COMPAT_INST_5G}.PSK1",
            "BeaconTypeI": inst_2g.get("BeaconType", "11i"),
            "BeaconTypeY": inst_5g.get("BeaconType", "11i"),
            "WPAAuthModeI": inst_2g.get("WPAAuthMode", "PSKAuthentication"),
            "WPAAuthModeY": inst_5g.get("WPAAuthMode", "PSKAuthentication"),
            "11iAuthModeI": inst_2g.get("11iAuthMode", "PSKAuthentication"),
            "11iAuthModeY": inst_5g.get("11iAuthMode", "PSKAuthentication"),
            "WPAEncryptTypeI": inst_2g.get("WPAEncryptType", "AESEncryption"),
            "WPAEncryptTypeY": inst_5g.get("WPAEncryptType", "AESEncryption"),
            "11iEncryptTypeI": inst_2g.get("11iEncryptType", "AESEncryption"),
            "11iEncryptTypeY": inst_5g.get("11iEncryptType", "AESEncryption"),
            "ESSIDHideEnableI": inst_2g.get("ESSIDHideEnable", "0"),
            "ESSIDHideEnableY": inst_5g.get("ESSIDHideEnable", "0"),
            "encode": self._encode_key(d, s),
        }
        self._post(TAG_WIFI_COMPAT, form)

    def poll_fast(self) -> dict[str, Any]:
        """Fetch only the fast-changing endpoints (WiFi, WAN, MU-MIMO).

        Used on the short polling cycle so that toggles made in the router web
        UI or the ZTE app are reflected in Home Assistant within seconds.
        """
        state: dict[str, Any] = {}
        readers = {
            "wan": self.get_wan_status,
            "wifi": self.get_wifi_status,
            "guest_wifi": self.get_guest_wifi_status,
            "wifi_compat": self.get_wifi_compat,
        }
        for key, reader in readers.items():
            try:
                state[key] = reader()
            except (ZTEConnectionError, ZTECommandError) as err:
                _LOGGER.debug("Fast poll failed for %s: %s", key, err)
        state["mumimo"] = None
        try:
            state["mumimo"] = self.get_mumimo_status()
        except (ZTEConnectionError, ZTECommandError) as err:
            _LOGGER.debug("MU-MIMO endpoint unavailable: %s", err)
        return state

    def poll_all(self) -> dict[str, Any]:
        """Fetch every read endpoint; individual failures are tolerated."""
        state: dict[str, Any] = {}
        readers = {
            "device": self.get_device_info,
            "wan": self.get_wan_status,
            "wifi": self.get_wifi_status,
            "guest_wifi": self.get_guest_wifi_status,
            "wifi_compat": self.get_wifi_compat,
            "system": self.get_system_settings,
            "wifi_radio": self.get_wifi_radio,
            "wifi_timer": self.get_wifi_timer,
            "ports": self.get_port_status,
            "lan_devices": self.get_lan_devices,
            "topology": self.get_topology,
        }
        for key, reader in readers.items():
            try:
                state[key] = reader()
            except (ZTEConnectionError, ZTECommandError) as err:
                # leave the key out entirely: the coordinator merges onto the
                # previous payload, so a single failed endpoint keeps the last
                # known value instead of flashing its entities "unavailable"
                _LOGGER.warning("Failed to read %s: %s", key, err)
        state["mumimo"] = None
        try:
            state["mumimo"] = self.get_mumimo_status()
        except (ZTEConnectionError, ZTECommandError) as err:
            _LOGGER.debug("MU-MIMO endpoint unavailable: %s", err)
        return state

    # ------------------------------------------------------------------
    # control APIs
    # ------------------------------------------------------------------
    def set_main_wifi(self, **overrides: Any) -> None:
        """Apply the main WiFi form (2.4G + 5G bands).

        Supported overrides (values applied on top of current state):
        ``enable_2g``, ``enable_5g``, ``hide_2g``, ``hide_5g``,
        ``dual_band_sync``, ``mlo``.
        """
        self._ensure_login()
        data = self._get(TAG_WIFI_MAIN)
        aps: dict[str, dict[str, str]] = {}
        radios: dict[str, dict[str, str]] = {}
        current = {"dual_band_sync": "0", "mlo": "0"}
        for instance in data.get("instances", []):
            iid = instance.get("_InstID", "")
            if iid in ("DEV.WIFI.AP1", "DEV.WIFI.AP5"):
                aps[iid] = instance
            elif iid in ("DEV.WIFI.RD1", "DEV.WIFI.RD2"):
                radios[iid] = instance
            elif "_InstID" not in instance and "DualBandSync" in instance:
                current["dual_band_sync"] = instance["DualBandSync"]
            elif "_InstID" not in instance and "MLOEnable" in instance:
                current["mlo"] = instance["MLOEnable"]

        if "dual_band_sync" in overrides:
            current["dual_band_sync"] = "1" if overrides["dual_band_sync"] else "0"
        if "mlo" in overrides:
            current["mlo"] = "1" if overrides["mlo"] else "0"

        pwd_2g = self._get_plaintext_password("DEV.WIFI.AP1")
        pwd_5g = self._get_plaintext_password("DEV.WIFI.AP5")
        # one random key pair encrypts both passphrases (mirrors the web UI)
        d, s = _rand_digits(), _rand_digits()
        enc_pwd_2g = self._encode_para(pwd_2g, d, s)
        enc_pwd_5g = self._encode_para(pwd_5g, d, s)
        encode_key = self._encode_key(d, s)

        form: dict[str, Any] = {
            "IF_ACTION": "Apply",
            "DualBandSync": current["dual_band_sync"],
            "MLOEnable": current["mlo"],
        }
        for idx, ap_id, rd_id in ((1, "DEV.WIFI.AP1", "DEV.WIFI.RD1"), (5, "DEV.WIFI.AP5", "DEV.WIFI.RD2")):
            ap = aps.get(ap_id, {})
            radio = radios.get(rd_id, {})
            band_key = "2g" if idx == 1 else "5g"
            enable = overrides.get(f"enable_{band_key}", ap.get("Enable", "1") == "1")
            hide = overrides.get(f"hide_{band_key}", ap.get("ESSIDHideEnable", "0") == "1")
            form.update(
                {
                    f"Enable{idx}": "1" if enable else "0",
                    f"ESSID{idx}": ap.get("ESSID", ""),
                    f"_InstID{idx}": ap_id,
                    f"_WLANCONIG{idx}": "Y",
                    f"_WEPCONIG{idx}": "N",
                    f"_PSKCONIG{idx}": "Y",
                    f"KeyPassphrase{idx}": enc_pwd_2g if idx == 1 else enc_pwd_5g,
                    f"WEPKey{idx}": enc_pwd_2g if idx == 1 else enc_pwd_5g,
                    f"_InstID_PSK{idx}": f"{ap_id}.PSK1",
                    f"BeaconType{idx}": ap.get("BeaconType", "11i"),
                    f"WEPAuthMode{idx}": ap.get("WEPAuthMode", "None"),
                    f"WEPEncryptionLevel{idx}": ap.get("WEPEncryptionLevel", "40-bit"),
                    f"WEPKeyIndex{idx}": ap.get("WEPKeyIndex", "1"),
                    f"WPAAuthMode{idx}": ap.get("WPAAuthMode", "PSKAuthentication"),
                    f"WPAEncryptType{idx}": ap.get("WPAEncryptType", "AESEncryption"),
                    f"11iAuthMode{idx}": ap.get("11iAuthMode", "PSKAuthentication"),
                    f"11iEncryptType{idx}": ap.get("11iEncryptType", "AESEncryption"),
                    f"ESSIDHideEnable{idx}": "1" if hide else "0",
                    f"WEPEncryptionLevel_Bit{idx}": ap.get("WEPEncryptionLevel", "40-bit"),
                    f"PowerEnhance{idx}": radio.get("PowerEnhance", "1"),
                    f"TxPower{idx}": radio.get("TxPower", "100%"),
                    f"Band{idx}": radio.get("Band", "2.4GHz" if idx == 1 else "5GHz"),
                    f"_InstID_Frq{idx}": rd_id,
                    f"RadioStatus{idx}": radio.get("RadioStatus", "1"),
                }
            )
        form["encode"] = encode_key
        try:
            self._post(TAG_WIFI_MAIN, form)
        except ZTECommandError as err:
            # This firmware writes the new dual-band / MLO configuration FIRST
            # and only then answers -1452 ("page expired"), because the radio
            # restart tears the page session down. Waiting for the change to
            # show up is more reliable than trusting the error code.
            if not _is_page_expired(err) or not self._main_wifi_applied(overrides):
                raise
            _LOGGER.debug(
                "Router answered page-expired for %s but the new state is live",
                overrides,
            )
        else:
            if ("dual_band_sync" in overrides or "mlo" in overrides) and not self._main_wifi_applied(
                overrides
            ):
                raise ZTECommandError("Router accepted the form but did not apply the change")

    def _main_wifi_applied(self, overrides: dict[str, Any], attempts: int = 6) -> bool:
        """True once the requested dual-band / MLO state is visible."""
        want_dual = overrides.get("dual_band_sync")
        want_mlo = overrides.get("mlo")
        if want_dual is None and want_mlo is None:
            return False
        for _ in range(attempts):
            time.sleep(0.8)
            try:
                dual, mlo = self.get_dual_band_flags()
            except (
                ZTEConnectionError,
                ZTECommandError,
                KeyError,
                IndexError,
                TypeError,
                ValueError,
            ):
                continue
            if (want_dual is None or dual == bool(want_dual)) and (
                want_mlo is None or mlo == bool(want_mlo)
            ):
                return True
        return False

    def set_guest_wifi(self, enable_2g: bool, enable_5g: bool) -> None:
        """Toggle guest WiFi networks (AP2/AP6)."""
        self._ensure_login()
        data = self._get(TAG_WIFI_GUEST)
        aps: dict[str, dict[str, str]] = {}
        for instance in data.get("instances", []):
            if instance.get("_InstID") in ("DEV.WIFI.AP2", "DEV.WIFI.AP6"):
                aps[instance["_InstID"]] = instance
        form: dict[str, Any] = {
            "IF_ACTION": "Apply",
            "_InstID2": "DEV.WIFI.AP2",
            "Enable2": "1" if enable_2g else "0",
            "_WLANCONIG2": "Y",
            "_PSKCONIG2": "N",
            "_InstID6": "DEV.WIFI.AP6",
            "Enable6": "1" if enable_5g else "0",
            "_WLANCONIG6": "Y",
            "_PSKCONIG6": "N",
        }
        if enable_2g or enable_5g:
            pwd = self._get_plaintext_password("DEV.WIFI.AP2")
            d, s = _rand_digits(), _rand_digits()
            enc_pwd = self._encode_para(pwd, d, s)
            for idx, ap_id in ((2, "DEV.WIFI.AP2"), (6, "DEV.WIFI.AP6")):
                ap = aps.get(ap_id, {})
                enabled = enable_2g if idx == 2 else enable_5g
                form.update(
                    {
                        f"guestAccessTime{idx}": ap.get("guestAccessTime", "0"),
                        f"GuestOffTime{idx}": ap.get("GuestOffTime", "0"),
                        f"ESSIDHideEnable{idx}": ap.get("ESSIDHideEnable", "0"),
                        f"ACLPolicy{idx}": ap.get("ACLPolicy", "Ban"),
                        f"LimitEnable{idx}": ap.get("LimitEnable", "0"),
                        f"DownRate{idx}": ap.get("DownRate", "0"),
                        f"UpRate{idx}": ap.get("UpRate", "0"),
                    }
                )
                if enabled:
                    form.update(
                        {
                            f"ESSID{idx}": ap.get("ESSID", ""),
                            f"_InstID_PSK{idx}": f"{ap_id}.PSK1",
                            f"_WEPCONIG{idx}": "N",
                            f"_PSKCONIG{idx}": "Y",
                            f"KeyPassphrase{idx}": enc_pwd,
                            f"BeaconType{idx}": ap.get("BeaconType", "11iandWPA3"),
                            f"WEPAuthMode{idx}": ap.get("WEPAuthMode", "SharedAuthentication"),
                            f"WEPEncryptionLevel{idx}": ap.get("WEPEncryptionLevel", "40-bit"),
                            f"WEPKeyIndex{idx}": ap.get("WEPKeyIndex", "1"),
                            f"WPAAuthMode{idx}": ap.get("WPAAuthMode", "PSKAuthentication"),
                            f"WPAEncryptType{idx}": ap.get("WPAEncryptType", "AESEncryption"),
                            f"11iAuthMode{idx}": ap.get("11iAuthMode", "PSKAuthentication"),
                            f"11iEncryptType{idx}": ap.get("11iEncryptType", "AESEncryption"),
                        }
                    )
            form["encode"] = self._encode_key(d, s)
        self._post(TAG_WIFI_GUEST, form)

    def set_mumimo(self, enabled: bool) -> None:
        """Toggle MU-MIMO (WiFi7 special features, Down+Up together)."""
        self._ensure_login()
        data = self._get(TAG_WIFI7_SPECIAL, rtype=T_VUEJSON)
        arr = (data.get("data") or {}).get("OBJ_WIFISPECIAL_ID") if isinstance(
            data.get("data"), dict
        ) else data.get("OBJ_WIFISPECIAL_ID")
        mru = "0"
        if arr:
            mru = arr[0].get("MRUEnable", "0")
        form = {
            "IF_ACTION": "Apply",
            "MRUEnable": mru,
            "DownMUMIMO": "1" if enabled else "0",
            "UPMUMIMO": "1" if enabled else "0",
        }
        self._post(TAG_WIFI7_SPECIAL, form, rtype=T_VUEJSON)

    def _probe_alive(self, timeout: float = 3.0) -> bool:
        """True while the router's web server still answers.

        The root page needs no session, so this is safe to call before login
        and while the router is going down.
        """
        try:
            response = self._session.get(self.base_url + "/", timeout=timeout)
        except requests.RequestException:
            return False
        return response.status_code < 500

    def _wait_for_reboot(self, attempts: int = 12, delay: float = 1.0) -> bool:
        """Watch the router drop off the network after a reboot request.

        Returns True once two consecutive probes fail (one failure alone can
        be a dropped packet or a momentarily busy web server).
        """
        for _ in range(attempts):
            time.sleep(delay)
            if not self._probe_alive():
                time.sleep(delay)
                if not self._probe_alive():
                    return True
        return False

    def _reset_session(self) -> None:
        """Forget the session after the router restarted."""
        self._logged_in = False
        self._token = ""
        self._token_from_login = False
        try:
            self._session.cookies.clear()
        except Exception:  # pragma: no cover - defensive
            pass

    def reboot(self) -> None:
        """Reboot the router.

        ``POST ?_type=vueData&_tag=vue_derestart_data`` with
        ``IF_ACTION=Restart`` is what the web console sends (verified against
        the Vue bundle). The reply is fire-and-forget: the router starts
        restarting immediately, so the answer is often truncated, arrives as
        the login page, or never arrives at all. A failed POST therefore does
        **not** mean the reboot did not happen — the outcome is decided by
        watching the router drop off the network, not by the HTTP status.
        """
        self._ensure_login()
        last_err: Exception | None = None
        for attempt in (1, 2):
            try:
                self._post(TAG_REBOOT, {"IF_ACTION": "Restart"})
            except (ZTECommandError, ZTEConnectionError, requests.RequestException) as err:
                last_err = err
                _LOGGER.debug(
                    "Reboot POST attempt %s did not answer cleanly "
                    "(expected while the router restarts): %s",
                    attempt,
                    err,
                )

            if self._wait_for_reboot(attempts=10):
                _LOGGER.debug("Router went offline after attempt %s: reboot accepted", attempt)
                self._reset_session()
                return
            _LOGGER.debug("Router still reachable after reboot attempt %s", attempt)

        raise ZTECommandError(
            "reboot was not confirmed - the router is still reachable"
            + (f" (last error: {last_err})" if last_err else "")
        )

"""Minimal EZVIZ cloud backend for Felis Plug.

Only the consumer-cloud operations needed by the application are implemented:
login/session refresh, MFA, dynamic smart-plug discovery and relay switching.

No account password is persisted.  Only the EZVIZ session/refresh token and
account name are stored in the application's private config directory.
"""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


DEFAULT_API = "apiieu.ezvizlife.com"
TIMEOUT = 25
PLUG_SWITCH_TYPE = 14

LOGIN_PATH = "/v3/users/login/v5"
LOGOUT_PATH = "/v3/users/logout/v2"
REFRESH_PATH = "/v3/apigateway/login"
MFA_SEND_PATH = "/v3/sms/nologin/checkcode"
PAGELIST_PATH = "/v3/userdevices/v1/resources/pagelist"
SWITCH_LEGACY_PATH = "/api/device/switchStatus"

CONFIG_DIR = Path.home() / ".config" / "cz.feliscatus" / "felisplug"
SESSION_FILE = CONFIG_DIR / "session.json"

_token = {}
_pending_account = None
_pending_password_hash = None


class EzvizError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class AuthRequired(EzvizError):
    pass


class MfaRequired(EzvizError):
    pass


def _feature_code():
    mac = uuid.getnode()
    mac_text = ":".join(
        "{:02x}".format((mac >> shift) & 0xFF)
        for shift in range(40, -1, -8)
    )
    return hashlib.md5(mac_text.encode("utf-8")).hexdigest()


FEATURE_CODE = _feature_code()


def _headers(include_session=True):
    headers = {
        "featureCode": FEATURE_CODE,
        "clientType": "3",
        "osVersion": "",
        "clientVersion": "",
        "netType": "WIFI",
        "customno": "1000001",
        "ssid": "",
        "clientNo": "web_site",
        "appId": "ys7",
        "language": "en_GB",
        "lang": "en",
        "User-Agent": "okhttp/3.12.1",
    }
    if include_session and _token.get("session_id"):
        headers["sessionId"] = str(_token["session_id"])
    else:
        headers["sessionId"] = ""
    return headers


def _load_token():
    global _token
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        _token = data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        _token = {}
    return _token


def _save_token():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(CONFIG_DIR), 0o700)
    except OSError:
        pass

    fd, tmp_name = tempfile.mkstemp(
        prefix="session-",
        suffix=".json",
        dir=str(CONFIG_DIR),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(_token, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, str(SESSION_FILE))
        os.chmod(str(SESSION_FILE), 0o600)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass


def _api_host():
    return str(_token.get("api_url") or DEFAULT_API)


def _json_from_response(response):
    raw = response.read().decode("utf-8", "replace")
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise EzvizError("EZVIZ returned invalid JSON: {}".format(raw[:300])) from exc


def _http_json(method, path, params=None, data=None, host=None,
               include_session=True, retry_401=True):
    if host is None:
        host = _api_host()

    query = ""
    if params:
        query = "?" + urllib.parse.urlencode(params)

    url = "https://{}{}{}".format(host, path, query)
    body = None
    headers = _headers(include_session=include_session)

    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return _json_from_response(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 401 and retry_401 and _token.get("rf_session_id"):
            _refresh_session()
            return _http_json(
                method,
                path,
                params=params,
                data=data,
                host=_api_host(),
                include_session=include_session,
                retry_401=False,
            )

        try:
            detail = exc.read().decode("utf-8", "replace")[:500]
        except Exception:
            detail = ""
        raise EzvizError("HTTP {}: {}".format(exc.code, detail or exc.reason)) from exc
    except urllib.error.URLError as exc:
        raise EzvizError("Network error: {}".format(exc.reason)) from exc


def _meta_code(payload):
    meta = payload.get("meta")
    if isinstance(meta, dict):
        return meta.get("code")
    return None


def _is_ok(payload):
    code = _meta_code(payload)
    if code is not None:
        return code in (200, "200")
    result = payload.get("resultCode")
    return result in (0, "0")


def _refresh_session():
    if not _token.get("rf_session_id"):
        raise AuthRequired("Login required")

    payload = _http_json(
        "PUT",
        REFRESH_PATH,
        data={
            "refreshSessionId": _token["rf_session_id"],
            "featureCode": FEATURE_CODE,
        },
        retry_401=False,
    )

    code = _meta_code(payload)
    if code in (200, "200"):
        info = payload.get("sessionInfo") or {}
        _token["session_id"] = str(info.get("sessionId") or "")
        _token["rf_session_id"] = str(info.get("refreshSessionId") or "")
        if not _token["session_id"] or not _token["rf_session_id"]:
            raise AuthRequired("EZVIZ returned an incomplete session")
        _save_token()
        return

    if code in (403, "403"):
        _token["session_id"] = None
        _token["rf_session_id"] = None
        _save_token()
        raise AuthRequired("Session expired")

    raise EzvizError("Could not refresh EZVIZ session: {}".format(payload.get("meta")))


def _send_mfa_code(account):
    payload = _http_json(
        "POST",
        MFA_SEND_PATH,
        data={"from": account, "bizType": "TERMINAL_BIND"},
        include_session=False,
        retry_401=False,
    )
    if not _is_ok(payload):
        raise EzvizError("Could not request MFA code: {}".format(payload.get("meta")))


def _perform_login(sms_code=None):
    global _token, _pending_account, _pending_password_hash

    if not _pending_account or not _pending_password_hash:
        raise AuthRequired("Enter account and password again")

    host = str(_token.get("api_url") or DEFAULT_API)
    payload = {
        "account": _pending_account,
        "password": _pending_password_hash,
        "featureCode": FEATURE_CODE,
        "msgType": "3" if sms_code else "0",
        "bizType": "TERMINAL_BIND" if sms_code else "",
        "cuName": "SGFzc2lv",
        "smsCode": sms_code if sms_code else "",
    }

    result = _http_json(
        "POST",
        LOGIN_PATH,
        data=payload,
        host=host,
        include_session=False,
        retry_401=False,
    )
    code = _meta_code(result)

    if code in (1100, "1100"):
        area = result.get("loginArea") or {}
        new_host = area.get("apiDomain")
        if not new_host:
            raise EzvizError("EZVIZ did not return the account region")
        _token["api_url"] = str(new_host)
        return _perform_login(sms_code)

    if code in (6002, "6002") and not sms_code:
        _send_mfa_code(_pending_account)
        raise MfaRequired("Verification code sent")

    if code in (1011, "1011", 1012, "1012"):
        raise EzvizError("Invalid verification code", code=int(code))
    if code in (1013, "1013"):
        raise EzvizError("Incorrect account", code=1013)
    if code in (1014, "1014"):
        raise EzvizError("Incorrect password", code=1014)
    if code in (1015, "1015"):
        raise EzvizError("Account is locked", code=1015)
    if code in (1226, "1226"):
        raise EzvizError("Incorrect account or password", code=1226)
    if code not in (200, "200"):
        try:
            error_code = int(code)
        except (TypeError, ValueError):
            error_code = None
        raise EzvizError("EZVIZ login failed", code=error_code)

    login_session = result.get("loginSession") or {}
    login_area = result.get("loginArea") or {}
    login_user = result.get("loginUser") or {}

    _token = {
        "session_id": str(login_session.get("sessionId") or ""),
        "rf_session_id": str(login_session.get("rfSessionId") or ""),
        "username": str(login_user.get("username") or ""),
        "api_url": str(login_area.get("apiDomain") or host),
        "account": _pending_account,
    }

    if not _token["session_id"] or not _token["rf_session_id"]:
        raise EzvizError("EZVIZ returned an incomplete login session")

    _save_token()
    _pending_password_hash = None
    return True


def _as_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _fetch_pagelist_filter(page_filter):
    offset = 0
    limit = 30

    merged = {
        "deviceInfos": [],
        "resourceInfos": [],
        page_filter: {},
    }

    while True:
        payload = _http_json(
            "GET",
            PAGELIST_PATH,
            params={
                "groupId": -1,
                "limit": limit,
                "offset": offset,
                "filter": page_filter,
            },
        )

        if not _is_ok(payload):
            raise EzvizError("Could not load devices: {}".format(payload.get("meta")))

        device_infos = payload.get("deviceInfos")
        if isinstance(device_infos, list):
            merged["deviceInfos"].extend(device_infos)

        resource_infos = payload.get("resourceInfos")
        if isinstance(resource_infos, list):
            merged["resourceInfos"].extend(resource_infos)

        section = payload.get(page_filter)
        if isinstance(section, dict):
            merged[page_filter].update(section)

        page = payload.get("page") or {}
        if not page.get("hasNext"):
            break

        offset += limit
        if offset > 3000:
            raise EzvizError("Too many EZVIZ devices")

    return merged


def _fetch_pagelist():
    switch_page = _fetch_pagelist_filter("SWITCH")
    status_page = _fetch_pagelist_filter("STATUS")

    merged = switch_page
    merged["STATUS"] = status_page.get("STATUS") or {}

    known_devices = {
        str(item.get("deviceSerial"))
        for item in merged.get("deviceInfos", [])
        if isinstance(item, dict) and item.get("deviceSerial")
    }
    for item in status_page.get("deviceInfos", []):
        if not isinstance(item, dict):
            continue
        serial = item.get("deviceSerial")
        if serial and str(serial) not in known_devices:
            merged["deviceInfos"].append(item)
            known_devices.add(str(serial))

    return merged


def _get_plugs_raw():
    page = _fetch_pagelist()

    names = {}
    for item in page.get("deviceInfos", []):
        if not isinstance(item, dict):
            continue
        serial = item.get("deviceSerial")
        name = item.get("name") or item.get("deviceName") or item.get("deviceAlias")
        if serial and name:
            names[str(serial)] = str(name)

    resource_names = {}
    group_ids = {}
    for item in page.get("resourceInfos", []):
        if not isinstance(item, dict):
            continue
        serial = item.get("deviceSerial")
        if not serial:
            continue
        serial = str(serial)

        resource_name = item.get("resourceName")
        if resource_name and serial not in resource_names:
            resource_names[serial] = str(resource_name)

        group_id = item.get("groupId")
        if group_id not in (None, -1, "-1") and serial not in group_ids:
            group_ids[serial] = group_id

    plugs = []
    switches = page.get("SWITCH") or {}
    statuses = page.get("STATUS") or {}

    for serial, entries in switches.items():
        if not isinstance(entries, list):
            continue

        relay_state = None
        found = False
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                switch_type = int(entry.get("type"))
            except (TypeError, ValueError):
                continue

            if switch_type == PLUG_SWITCH_TYPE:
                found = True
                if "enable" in entry:
                    relay_state = _as_bool(entry.get("enable"))
                elif "status" in entry:
                    relay_state = _as_bool(entry.get("status"))
                break

        if not found:
            continue

        serial = str(serial)
        status_entry = statuses.get(serial) or {}
        optionals = status_entry.get("optionals") or {}
        online_raw = optionals.get("OnlineStatus")
        online = None
        try:
            online_value = int(online_raw)
            if online_value == 1:
                online = True
            elif online_value == 2:
                online = False
        except (TypeError, ValueError):
            pass

        plugs.append(
            {
                "serial": serial,
                "name": names.get(serial) or resource_names.get(serial) or serial,
                "is_on": relay_state,
                "online": online,
                "online_status": online_raw,
                "group_id": group_ids.get(serial),
            }
        )

    plugs.sort(key=lambda item: item["name"].casefold())
    return plugs


def _set_switch_request(serial, enabled):
    enable_flag = 1 if bool(enabled) else 0
    v3_path = "/v3/devices/{}/0/{}/{}/switchStatus".format(
        urllib.parse.quote(str(serial), safe=""),
        enable_flag,
        PLUG_SWITCH_TYPE,
    )

    first_error = None
    try:
        payload = _http_json("PUT", v3_path)
        if not _is_ok(payload):
            error_code = _meta_code(payload)
            if error_code is None:
                error_code = payload.get("resultCode")
            try:
                error_code = int(error_code)
            except (TypeError, ValueError):
                error_code = None
            raise EzvizError("V3 switch request failed", code=error_code)
        return
    except EzvizError as exc:
        if exc.code in (2003, 2009):
            raise
        first_error = exc

    payload = _http_json(
        "POST",
        SWITCH_LEGACY_PATH,
        data={
            "serial": str(serial),
            "enable": str(enable_flag),
            "type": str(PLUG_SWITCH_TYPE),
            "channel": "0",
        },
    )
    if not _is_ok(payload):
        if first_error is not None:
            raise first_error
        error_code = _meta_code(payload)
        if error_code is None:
            error_code = payload.get("resultCode")
        try:
            error_code = int(error_code)
        except (TypeError, ValueError):
            error_code = None
        raise EzvizError("Switch request failed", code=error_code)


def _result_ok(plugs=None):
    return {
        "status": "ok",
        "plugs": plugs if plugs is not None else _get_plugs_raw(),
        "account": str(_token.get("account") or ""),
    }


def _result_error(message, plugs=None, serial=None, device_name=None, error_kind=None):
    result = {
        "status": "error",
        "error": str(message),
        "account": str(_token.get("account") or ""),
    }
    error_code = getattr(message, "code", None)
    if error_code is not None:
        result["error_code"] = error_code
    if error_kind:
        result["error_kind"] = str(error_kind)
    if plugs is not None:
        result["plugs"] = plugs
    if serial:
        result["serial"] = str(serial)
    if device_name:
        result["device_name"] = str(device_name)
    return result


def initialize():
    """Load saved session and, when possible, return the live plug list."""
    _load_token()
    account = str(_token.get("account") or "")

    if not _token.get("session_id") or not _token.get("rf_session_id"):
        return {"status": "login_required", "account": account}

    try:
        _refresh_session()
        return _result_ok()
    except AuthRequired:
        return {"status": "login_required", "account": account}
    except Exception as exc:
        return _result_error(exc)


def login(account, password):
    """Authenticate with account/password. Password is retained only in RAM for MFA."""
    global _pending_account, _pending_password_hash, _token

    account = str(account or "").strip()
    password = str(password or "")

    if not account or not password:
        return _result_error("Enter account and password")

    _pending_account = account
    _pending_password_hash = hashlib.md5(password.encode("utf-8")).hexdigest()

    if not _token:
        _load_token()
    _token["account"] = account
    if not _token.get("api_url"):
        _token["api_url"] = DEFAULT_API

    try:
        _perform_login()
        return _result_ok()
    except MfaRequired:
        return {
            "status": "mfa_required",
            "account": account,
            "message": "Verification code sent",
        }
    except Exception as exc:
        return _result_error(exc)


def submit_mfa(code):
    code = str(code or "").strip()
    if not code.isdigit():
        return _result_error("Verification code must contain digits only")

    try:
        _perform_login(int(code))
        return _result_ok()
    except Exception as exc:
        return _result_error(exc)


def refresh():
    try:
        if not _token:
            _load_token()
        if not _token.get("session_id"):
            raise AuthRequired("Login required")
        return _result_ok()
    except AuthRequired:
        return {
            "status": "login_required",
            "account": str(_token.get("account") or ""),
        }
    except Exception as exc:
        return _result_error(exc)


def set_plug(serial, enabled, device_name=None):
    serial = str(serial)
    wanted = bool(enabled)

    try:
        current = _get_plugs_raw()
        for plug in current:
            if plug.get("serial") == serial and plug.get("online") is False:
                return _result_error(
                    EzvizError("Device is unavailable"),
                    plugs=current,
                    serial=serial,
                    device_name=device_name or plug.get("name"),
                    error_kind="device_unavailable",
                )

        _set_switch_request(serial, wanted)

        delays = (0.25, 0.50, 0.75, 1.00, 1.50, 2.00)
        latest = None
        for delay in delays:
            time.sleep(delay)
            latest = _get_plugs_raw()
            for plug in latest:
                if plug.get("serial") == serial:
                    if plug.get("online") is False:
                        return _result_error(
                            EzvizError("Device is unavailable"),
                            plugs=latest,
                            serial=serial,
                            device_name=device_name or plug.get("name"),
                            error_kind="device_unavailable",
                        )
                    if plug.get("is_on") is wanted:
                        return {
                            "status": "ok",
                            "plugs": latest,
                            "account": str(_token.get("account") or ""),
                        }
                    break

        return _result_error(
            EzvizError("EZVIZ cloud did not confirm the new state"),
            plugs=latest,
            serial=serial,
            device_name=device_name,
        )

    except AuthRequired:
        return {
            "status": "login_required",
            "account": str(_token.get("account") or ""),
        }
    except Exception as exc:
        try:
            plugs = _get_plugs_raw()
        except Exception:
            plugs = None

        code = getattr(exc, "code", None)
        unavailable = code in (2003, 2009)
        if unavailable and plugs is not None:
            for plug in plugs:
                if plug.get("serial") == serial:
                    plug["online"] = False
                    break

        return _result_error(
            exc,
            plugs=plugs,
            serial=serial,
            device_name=device_name,
            error_kind="device_unavailable" if unavailable else None,
        )


def logout():
    global _token, _pending_account, _pending_password_hash

    account = str(_token.get("account") or "")
    try:
        if _token.get("session_id"):
            _http_json("DELETE", LOGOUT_PATH, retry_401=False)
    except Exception:
        pass

    _token = {"account": account, "api_url": DEFAULT_API}
    _pending_account = None
    _pending_password_hash = None
    _save_token()
    return {"status": "login_required", "account": account}

#!/usr/bin/env python3
"""Waybar on/off buttons driven by services.json.

`service-toggle.py ID` prints one JSON object.
`service-toggle.py ID toggle` flips that service, then signals Waybar.
Add a service by appending one object to services.json and rebuilding the theme.

A socket entry is mint only when its socket is active, its app unit is active,
and its upstream port is listening. Anything in between is an error the tooltip
names. A click in that state starts the missing pieces instead of stopping them.
"""

import fcntl
import json
import os
import re
import subprocess
import sys
from pathlib import Path


ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
RESERVED_IDS = {"service", "service-open", "codex", "grok", "tray", "tray-open"}
SOCKET_KEYS = {"id", "kind", "unit", "stop", "interval", "detail", "app", "upstream"}
COMMAND_KEYS = {"id", "kind", "status", "on", "off", "interval", "detail"}
UNIT_RE = re.compile(r"^[a-zA-Z0-9@_.-]+$")
LISTEN_STATE = "0A"
STATE_TEXT = {
    "active": "켜짐",
    "inactive": "꺼짐",
    "failed": "실패",
    "activating": "켜는 중",
    "deactivating": "끄는 중",
    "reloading": "다시 읽는 중",
}


class CatalogError(ValueError):
    pass


def catalog_path():
    override = os.environ.get("YURU_SERVICE_CATALOG")
    if override:
        return Path(override)
    return Path.home() / ".config/waybar/services.json"


def _argv(value, label):
    if not isinstance(value, list) or not value or not all(isinstance(part, str) and part for part in value):
        raise CatalogError(label + " must be a non-empty list of strings")
    if any(any(ch.isspace() for ch in part) for part in value):
        raise CatalogError(label + " arguments must not contain whitespace")
    return value


def _detail(service):
    if "detail" not in service:
        return
    detail = service["detail"]
    service_id = service.get("id", "?")
    if not isinstance(detail, list) or not detail or len(detail) > 8:
        raise CatalogError(service_id + " detail must be 1 to 8 lines")
    for line in detail:
        if not isinstance(line, str) or not line.strip() or len(line) > 160:
            raise CatalogError(service_id + " detail lines must be short text")
        if any(ord(ch) < 32 for ch in line):
            raise CatalogError(service_id + " detail lines must be a single line")


def _interval(service):
    interval = service.get("interval", 5)
    if not isinstance(interval, int) or isinstance(interval, bool) or not 1 <= interval <= 3600:
        raise CatalogError(service.get("id", "?") + " interval must be a whole number of seconds from 1 to 3600")
    return interval


def _unit(value, label):
    if not isinstance(value, str) or UNIT_RE.fullmatch(value) is None:
        raise CatalogError(label + " must be a systemd unit name")
    return value


def _ipv4(host):
    parts = host.split(".")
    if len(parts) != 4:
        return None
    numbers = []
    for part in parts:
        if not part.isdigit() or (len(part) > 1 and part.startswith("0")):
            return None
        number = int(part)
        if number > 255:
            return None
        numbers.append(number)
    return numbers


def _upstream(value, service_id):
    if not isinstance(value, str):
        raise CatalogError(service_id + " upstream must be an IPv4 host:port")
    host, separator, port_text = value.rpartition(":")
    if not separator or _ipv4(host) is None or not port_text.isdigit():
        raise CatalogError(service_id + " upstream must be an IPv4 host:port")
    if not 1 <= int(port_text) <= 65535:
        raise CatalogError(service_id + " upstream port must be from 1 to 65535")
    return value


def load_catalog(path):
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"cannot read service catalog {path}: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"signal", "services"}:
        raise CatalogError("service catalog must contain signal and services")
    signal = data["signal"]
    if not isinstance(signal, int) or isinstance(signal, bool) or not 1 <= signal <= 15:
        raise CatalogError("signal must be a whole number from 1 to 15")
    services = data["services"]
    if not isinstance(services, list):
        raise CatalogError("services must be a list")
    seen = set()
    for service in services:
        if not isinstance(service, dict):
            raise CatalogError("each service must be an object")
        service_id = service.get("id")
        if not isinstance(service_id, str) or ID_RE.fullmatch(service_id) is None:
            raise CatalogError(f"invalid service id: {service_id!r}")
        if service_id in RESERVED_IDS or service_id in seen:
            raise CatalogError("duplicate or reserved service id: " + service_id)
        seen.add(service_id)
        kind = service.get("kind")
        if kind == "socket":
            unknown = set(service) - SOCKET_KEYS
            if unknown:
                raise CatalogError(service_id + " has unknown fields: " + ", ".join(sorted(unknown)))
            unit = _unit(service.get("unit"), service_id + " unit")
            stop = service.get("stop", [unit])
            if (not isinstance(stop, list) or not stop
                    or not all(isinstance(item, str) and UNIT_RE.fullmatch(item) for item in stop)):
                raise CatalogError(service_id + " stop must be a list of unit names")
            if unit not in stop:
                raise CatalogError(service_id + " stop must include its unit")
            if "app" in service:
                app = _unit(service.get("app"), service_id + " app")
                if app not in stop:
                    raise CatalogError(service_id + " stop must include its app")
            if "upstream" in service:
                _upstream(service.get("upstream"), service_id)
            service["stop"] = stop
        elif kind == "command":
            unknown = set(service) - COMMAND_KEYS
            if unknown:
                raise CatalogError(service_id + " has unknown fields: " + ", ".join(sorted(unknown)))
            for key in ("status", "on", "off"):
                _argv(service.get(key), service_id + " " + key)
        else:
            raise CatalogError(service_id + " kind must be socket or command")
        _detail(service)
        _interval(service)
    return data


def apply_catalog(config, catalog):
    """Insert one Waybar custom module per catalog entry. The handle stays first."""
    drawer = config.get("group/service-drawer")
    if not isinstance(drawer, dict) or not isinstance(drawer.get("modules"), list):
        raise CatalogError("waybar config is missing group/service-drawer")
    signal = catalog["signal"]
    modules = ["group/service-handle"]
    for service in catalog["services"]:
        key = "custom/" + service["id"]
        if key in config and "exec" not in config[key]:
            raise CatalogError(key + " already exists and is not a service button")
        command = "python3 $HOME/.config/waybar/scripts/service-toggle.py " + service["id"]
        config[key] = {
            "exec": command,
            "return-type": "json",
            "interval": _interval(service),
            "signal": signal,
            "exec-on-event": False,
            "on-click": command + " toggle",
        }
        modules.append(key)
    drawer["modules"] = modules
    return config


def run(argv):
    env = os.environ.copy()
    local = str(Path.home() / ".local/bin")
    parts = [part for part in env.get("PATH", "").split(":") if part]
    if local not in parts:
        env["PATH"] = ":".join([local, *parts])
    return subprocess.run(argv, check=False, capture_output=True, text=True, env=env)


def notify(signal):
    completed = run(["pkill", f"-RTMIN+{signal}", "-x", "waybar"])
    if completed.returncode not in (0, 1):
        detail = completed.stderr.strip() or f"pkill exited {completed.returncode}"
        print(detail, file=sys.stderr)


def _require(completed, label):
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(detail or f"{label} exited {completed.returncode}")


def _state_text(state):
    return STATE_TEXT.get(state, state)


def _ipv4_from_proc(ip_hex):
    if len(ip_hex) != 8:
        return None
    try:
        raw = bytes.fromhex(ip_hex)
    except ValueError:
        return None
    return list(reversed(raw))


def proc_listening(text, host, port):
    """True when text is a /proc/net/tcp table with host:port listening.

    0.0.0.0 counts: a wildcard listener accepts that address too.
    """
    wanted = _ipv4(host)
    if wanted is None:
        return False
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 4 or parts[3] != LISTEN_STATE:
            continue
        local, separator, port_hex = parts[1].partition(":")
        if not separator:
            continue
        try:
            seen_port = int(port_hex, 16)
        except ValueError:
            continue
        seen = _ipv4_from_proc(local)
        if seen_port == port and (seen == [0, 0, 0, 0] or seen == wanted):
            return True
    return False


def port_listening(host, port):
    """Read the kernel listen table. Connecting on each poll would hit the app."""
    path = Path("/proc/net/tcp")
    try:
        text = path.read_text()
    except OSError as exc:
        raise RuntimeError(f"{host}:{port} 확인 실패: {exc.strerror or exc}") from exc
    return proc_listening(text, host, port)


def tcp_status(upstream):
    host, _, port_text = upstream.rpartition(":")
    return "open" if port_listening(host, int(port_text)) else "closed"


def unit_state(unit):
    completed = run(["systemctl", "--user", "is-active", unit])
    if completed.returncode == 4:
        raise RuntimeError(unit + " 유닛이 없음")
    if completed.returncode not in (0, 3):
        detail = completed.stderr.strip() or f"systemctl is-active exited {completed.returncode}"
        raise RuntimeError(detail)
    state = completed.stdout.strip()
    if not state:
        raise RuntimeError(unit + " 상태를 읽지 못함")
    return state


def _upstream_text(result, app_state):
    if result == "open":
        return "연결됨"
    if result == "closed" and app_state in {"active", "activating", "reloading"}:
        return "아직 연결 안 됨"
    if result == "closed":
        return "연결 거부"
    return result


def _problem(service, socket_state, app, app_state, upstream, upstream_state):
    if app and app_state == "failed":
        return f"문제: 앱 {app} 실패"
    if app and app_state == "activating":
        return f"문제: 앱 {app} 켜는 중"
    if app and app_state != "active":
        return f"문제: 앱 {app} {_state_text(app_state)}"
    if upstream and upstream_state == "closed":
        if app_state in {"active", "activating", "reloading"}:
            return f"문제: {upstream} 아직 연결 안 됨"
        return f"문제: {upstream} 연결 거부"
    if socket_state != "active":
        return f"문제: 소켓 {service['unit']} {_state_text(socket_state)}"
    return "문제: 아직 준비되지 않음"


def socket_status(service):
    socket_state = unit_state(service["unit"])
    app = service.get("app")
    app_state = unit_state(app) if app else None
    upstream = service.get("upstream")
    upstream_state = tcp_status(upstream) if upstream else None
    ready = (
        socket_state == "active"
        and (app_state == "active" if app else True)
        and (upstream_state == "open" if upstream else True)
    )
    off = (
        socket_state == "inactive"
        and (app_state == "inactive" if app else True)
        and upstream_state in (None, "closed")
    )
    if ready:
        lines = ["켜짐", f"소켓 {service['unit']}: 켜짐"]
        if app:
            lines.append(f"앱 {app}: 켜짐")
        if upstream:
            lines.append(f"업스트림 {upstream}: 연결됨")
        return {"ready": True, "off": False, "lines": lines}
    if off:
        return {"ready": False, "off": True, "lines": ["꺼짐"]}
    lines = [
        _problem(service, socket_state, app, app_state, upstream, upstream_state),
        f"소켓 {service['unit']}: {_state_text(socket_state)}",
    ]
    if app:
        lines.append(f"앱 {app}: {_state_text(app_state)}")
    if upstream:
        lines.append(f"업스트림 {upstream}: {_upstream_text(upstream_state, app_state)}")
    return {"ready": False, "off": False, "lines": lines}


def command_status(service):
    completed = run(service["status"])
    text = completed.stdout.strip()
    if completed.returncode != 0 or text not in {"on", "off"}:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(detail or f"{service['id']} status exited {completed.returncode}")
    active = text == "on"
    return {"ready": active, "off": not active, "lines": ["켜짐" if active else "꺼짐"]}


def inspect(service):
    if service["kind"] == "socket":
        return socket_status(service)
    return command_status(service)


def toggle(service, signal):
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
    lock_path = runtime / ("waybar-service-" + service["id"] + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        found = inspect(service)
        if service["kind"] == "socket":
            if found["ready"]:
                _require(run(["systemctl", "--user", "stop", *service["stop"]]), "systemctl stop")
            else:
                # Start the app before the socket. A listening proxy with no app is the Bad Gateway.
                if service.get("app"):
                    _require(run(["systemctl", "--user", "start", service["app"]]), "systemctl start")
                _require(run(["systemctl", "--user", "start", service["unit"]]), "systemctl start")
        else:
            argv = service["off"] if found["ready"] else service["on"]
            _require(run(argv), service["id"])
        notify(signal)


def _markup(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tooltip_text(service, active=None, error=None, lines=None):
    if error is not None:
        rows = ["확인 실패: " + error]
    elif lines is not None:
        rows = list(lines)
    elif active:
        rows = ["켜짐"]
    else:
        rows = ["꺼짐"]
    return "\n".join(_markup(line) for line in [*rows, *service.get("detail", [])])


def payload(service, active=None, error=None, lines=None, ready=None, off=None):
    classes = ["service"]
    if ready is not None or off is not None:
        active = bool(ready)
    if error is not None:
        classes.append("error")
    elif active:
        classes.append("on")
    elif not off and lines not in (None, ["꺼짐"]):
        classes.append("error")
    return {
        "text": service["id"],
        "class": classes,
        "tooltip": tooltip_text(service, active, error, lines),
    }


def print_status(service):
    try:
        found = inspect(service)
    except RuntimeError as exc:
        json.dump(payload(service, error=str(exc)), sys.stdout, ensure_ascii=False)
    else:
        json.dump(payload(service, ready=found["ready"], off=found["off"], lines=found["lines"]),
                  sys.stdout, ensure_ascii=False)
    print()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        catalog = load_catalog(catalog_path())
    except CatalogError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    known = {service["id"]: service for service in catalog["services"]}
    if len(argv) not in (1, 2) or argv[0] not in known or (len(argv) == 2 and argv[1] != "toggle"):
        print("usage: service-toggle.py ID [toggle]", file=sys.stderr)
        return 2
    service = known[argv[0]]
    if len(argv) == 2:
        try:
            toggle(service, catalog["signal"])
        except RuntimeError as exc:
            json.dump(payload(service, error=str(exc)), sys.stdout, ensure_ascii=False)
            print()
            return 0
    print_status(service)
    return 0


if __name__ == "__main__":
    sys.exit(main())

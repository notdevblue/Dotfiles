#!/usr/bin/env python3
"""Waybar on/off buttons driven by services.json.

`service-toggle.py ID` prints one JSON object.
`service-toggle.py ID toggle` flips that service, then signals Waybar.
Add a service by appending one object to services.json and rebuilding the theme.
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
SOCKET_KEYS = {"id", "kind", "unit", "stop", "interval", "detail"}
COMMAND_KEYS = {"id", "kind", "status", "on", "off", "interval", "detail"}
UNIT_RE = re.compile(r"^[a-zA-Z0-9@_.-]+$")


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
            unit = service.get("unit")
            if not isinstance(unit, str) or UNIT_RE.fullmatch(unit) is None:
                raise CatalogError(service_id + " needs a systemd unit name")
            stop = service.get("stop", [unit])
            if (not isinstance(stop, list) or not stop
                    or not all(isinstance(item, str) and UNIT_RE.fullmatch(item) for item in stop)):
                raise CatalogError(service_id + " stop must be a list of unit names")
            if unit not in stop:
                raise CatalogError(service_id + " stop must include its unit")
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


def is_on(service):
    if service["kind"] == "socket":
        completed = run(["systemctl", "--user", "is-active", "--quiet", service["unit"]])
        if completed.returncode == 0:
            return True
        if completed.returncode == 3:
            return False
        detail = completed.stderr.strip() or f"systemctl is-active exited {completed.returncode}"
        raise RuntimeError(detail)
    completed = run(service["status"])
    text = completed.stdout.strip()
    if completed.returncode != 0 or text not in {"on", "off"}:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(detail or f"{service['id']} status exited {completed.returncode}")
    return text == "on"


def toggle(service, signal):
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
    lock_path = runtime / ("waybar-service-" + service["id"] + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if service["kind"] == "socket":
            if is_on(service):
                _require(run(["systemctl", "--user", "stop", *service["stop"]]), "systemctl stop")
            else:
                _require(run(["systemctl", "--user", "start", service["unit"]]), "systemctl start")
        else:
            argv = service["off"] if is_on(service) else service["on"]
            _require(run(argv), service["id"])
        notify(signal)


def _markup(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tooltip_text(service, active=None, error=None):
    if error is not None:
        head = "확인 실패: " + error
    elif active:
        head = "켜짐"
    else:
        head = "꺼짐"
    return "\n".join(_markup(line) for line in [head, *service.get("detail", [])])


def payload(service, active=None, error=None):
    classes = ["service"]
    body = {"text": service["id"], "class": classes, "tooltip": tooltip_text(service, active, error)}
    if error is not None:
        classes.append("error")
    elif active:
        classes.append("on")
    return body


def print_status(service):
    try:
        active = is_on(service)
    except RuntimeError as exc:
        json.dump(payload(service, error=str(exc)), sys.stdout)
    else:
        json.dump(payload(service, active=active), sys.stdout)
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
            json.dump(payload(service, error=str(exc)), sys.stdout)
            print()
            return 0
    print_status(service)
    return 0


if __name__ == "__main__":
    sys.exit(main())

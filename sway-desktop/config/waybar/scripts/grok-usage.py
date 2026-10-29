#!/usr/bin/env python3
"""Show Grok subscription quota using CLI auth, without model requests.

The billing route is undocumented. Reject unexpected responses rather than
inventing a quota. Only percentages and timestamps go into the local cache.
Grok owns credential refresh and writes its own auth file under its own lock.
"""

import fcntl
import html
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


AUTH = Path.home() / ".grok/auth.json"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "waybar/grok-usage.json"
BILLING_URL = "https://cli-chat-proxy.grok.com/v1/billing?format=credits"
CACHE_SECONDS = 180
ERROR_SECONDS = 60


class Unavailable(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the bearer token to another URL.
        return None


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Missing timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timestamp has no timezone")
    return dt.timestamp()


def auth_revision():
    try:
        return AUTH.stat().st_mtime_ns
    except OSError:
        return None


def credential():
    try:
        entries = json.loads(AUTH.read_text())
        candidates = [
            value for key, value in entries.items()
            if key.startswith("https://auth.x.ai::")
            and isinstance(value, dict)
            and value.get("auth_mode") == "oidc"
            and isinstance(value.get("key"), str)
            and value["key"]
        ]
    except (OSError, ValueError, AttributeError):
        raise Unavailable("Grok 로그인 정보를 읽을 수 없습니다. grok login을 실행하세요.") from None
    if len(candidates) != 1:
        raise Unavailable("Grok 로그인 계정을 확인할 수 없습니다. grok login을 실행하세요.")
    return candidates[0]


def refresh_auth():
    grok = str(Path.home() / ".local/bin/grok")
    if not Path(grok).is_file():
        grok = shutil.which("grok")
    if not grok:
        raise Unavailable("Grok CLI를 찾을 수 없어 인증을 갱신할 수 없습니다.")
    # Initialize the native agent and immediately close stdin. No session/new,
    # prompt, tools, browser login, or model request is sent.
    message = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": 1, "clientCapabilities": {},
            "clientInfo": {"name": "waybar-usage", "version": "1"},
        },
    }
    try:
        result = subprocess.run(
            [grok, "agent", "--no-leader", "stdio"],
            input=json.dumps(message) + "\n", text=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            cwd="/tmp", timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise Unavailable("Grok 인증 갱신 실패. grok login을 실행하세요.") from None
    if result.returncode != 0:
        raise Unavailable("Grok 인증 갱신 실패. grok login을 실행하세요.")


def request_billing(token):
    request = urllib.request.Request(BILLING_URL, headers={
        "Authorization": "Bearer " + token,
        "X-XAI-Token-Auth": "xai-grok-cli",
        "Accept": "application/json",
    })
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=12) as response:
        return json.load(response)


def parse_billing(data):
    try:
        config = data["config"]
        used = config["creditUsagePercent"]
        period = config["currentPeriod"]
        if (type(used) not in (int, float) or not math.isfinite(used)
                or not 0 <= used <= 100
                or period.get("type") != "USAGE_PERIOD_TYPE_WEEKLY"):
            raise ValueError("Unexpected quota")
        reset = timestamp(period.get("end") or config.get("billingPeriodEnd"))
        if reset <= time.time():
            raise ValueError("Expired quota")
        return {"remaining": 100 - used, "resets_at": reset}
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
        raise Unavailable("Grok 한도 응답 형식이 바뀌었거나 초기화 반영을 기다리는 중입니다.") from None


def fetch_quota():
    auth = credential()
    refreshed = False
    try:
        expires = timestamp(auth.get("expires_at"))
    except ValueError:
        expires = 0
    if expires <= time.time() + 300:
        refresh_auth()
        auth = credential()
        refreshed = True
    try:
        try:
            data = request_billing(auth["key"])
        except urllib.error.HTTPError as error:
            if error.code != 401 or refreshed:
                raise
            refresh_auth()
            data = request_billing(credential()["key"])
        return parse_billing(data)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise Unavailable("Grok 인증 만료 또는 접근 거부. grok login을 실행하세요.") from None
        raise Unavailable(f"Grok 사용량 조회 실패 (HTTP {error.code}).") from None
    except (OSError, ValueError):
        raise Unavailable("Grok 사용량 조회 실패. 네트워크 또는 서버 응답을 확인하세요.") from None


def load_cache():
    try:
        data = json.loads(CACHE.read_text())
        if not isinstance(data, dict) or data.get("auth_revision") != auth_revision():
            return None
        age = time.time() - data["checked_at"]
        ttl = ERROR_SECONDS if data.get("error") else CACHE_SECONDS
        if not 0 <= age < ttl:
            return None
        if not data.get("error"):
            remaining = data["remaining"]
            reset = data["resets_at"]
            if (type(remaining) not in (int, float) or not math.isfinite(remaining)
                    or not 0 <= remaining <= 100
                    or type(reset) not in (int, float) or not math.isfinite(reset)
                    or reset <= time.time()):
                return None
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_cache(data):
    temporary = None
    try:
        CACHE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=CACHE.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False)
        temporary.replace(CACHE)
    except OSError:
        pass  # Quota display still works when the cache cannot be written.
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def local_time(value):
    return datetime.fromtimestamp(value, timezone.utc).astimezone().strftime("%m/%d %H:%M")


def status():
    data = load_cache()
    if data is None:
        try:
            data = fetch_quota()
        except Unavailable as error:
            data = {"error": str(error)}
        data.update(checked_at=time.time(), auth_revision=auth_revision())
        save_cache(data)
    if data.get("error"):
        return {
            "text": "grok ?", "class": "unavailable",
            "tooltip": html.escape("Grok 남은 사용량\n" + data["error"] + "\n다음 주기에 자동 재시도"),
        }
    return {
        "text": f"grok {data['remaining']:g}%",
        "tooltip": "\n".join([
            "Grok 주간 남은 사용량",
            f"남은 한도: {data['remaining']:g}%",
            "초기화: " + local_time(data["resets_at"]),
            "마지막 조회: " + local_time(data["checked_at"]),
            "3분 캐시 · Grok CLI 인증 자동 갱신 · 모델 호출 없음",
        ]),
    }


def locked_status():
    # Waybar can execute the module once per monitor. Share the request/cache
    # and serialize native credential refresh across those instances.
    try:
        CACHE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(CACHE.with_suffix(".lock"), os.O_CREAT | os.O_RDWR, 0o600)
    except OSError:
        return status()
    with os.fdopen(descriptor, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return status()


if __name__ == "__main__":
    print(json.dumps(locked_status(), ensure_ascii=False))

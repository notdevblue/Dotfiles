#!/usr/bin/env python3
"""Read saved Codex rate limits without making network or model requests."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def latest_usage(sessions):
    candidates = []
    for path in sessions.rglob("*.jsonl"):
        try:
            candidates.append((path.stat().st_mtime, path))
        except OSError:
            continue

    latest = None
    for modified, path in sorted(candidates, reverse=True):
        if latest and modified < latest[0].timestamp():
            break
        try:
            with path.open("rb") as stream:
                # Usage events are frequent; bound reads even for long sessions.
                stream.seek(max(0, os.fstat(stream.fileno()).st_size - 1024 * 1024))
                lines = stream.read().splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            if b'"rate_limits"' not in line:
                continue
            try:
                event = json.loads(line)
                limits = event["payload"]["rate_limits"]
                if not isinstance(limits, dict) or limits.get("limit_id") not in (None, "codex"):
                    continue
                if not any(limits.get(key) for key in ("primary", "secondary")):
                    continue
                timestamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    continue
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
            if latest is None or timestamp > latest[0]:
                latest = (timestamp, limits)
            break
    return latest


def window_label(minutes):
    if minutes and minutes % 1440 == 0:
        return f"{minutes // 1440}일"
    if minutes and minutes % 60 == 0:
        return f"{minutes // 60}시간"
    return f"{minutes}분" if minutes else "사용 한도"


def status(snapshot):
    if snapshot is None:
        return {"text": "codex ?", "tooltip": "저장된 Codex 사용량 기록이 없습니다."}

    timestamp, limits = snapshot
    now = datetime.now(timezone.utc).timestamp()
    values = []
    tooltip = ["Codex 남은 사용량"]
    for key in ("primary", "secondary"):
        bucket = limits.get(key)
        if not isinstance(bucket, dict):
            continue
        used = bucket.get("used_percent")
        if not isinstance(used, (float, int)) or not 0 <= used <= 100:
            continue
        reset = bucket.get("resets_at")
        expired = isinstance(reset, (float, int)) and reset <= now
        value = "?" if expired else f"{100 - used:g}%"
        values.append(value)
        detail = f"{window_label(bucket.get('window_minutes'))}: {value}"
        if isinstance(reset, (float, int)):
            detail += datetime.fromtimestamp(reset).astimezone().strftime(" · 초기화 %m/%d %H:%M")
        if expired:
            detail += " (새 기록 대기)"
        tooltip.append(detail)
    tooltip.append(timestamp.astimezone().strftime("마지막 기록: %m/%d %H:%M"))
    tooltip.append("로컬 기록 갱신 시 반영 · 추가 사용량 없음")
    return {"text": "codex " + ("/".join(values) or "?"), "tooltip": "\n".join(tooltip)}


if __name__ == "__main__":
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    print(json.dumps(status(latest_usage(codex_home / "sessions")), ensure_ascii=False))

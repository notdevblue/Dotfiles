#!/usr/bin/env python3
"""Yeelight LAN discovery, one connection per lamp, and local Waybar RPC.

The selected scope and local display names are saved by device ID. Addresses
come from fresh discovery on an active private LAN interface.
"""
import argparse
import concurrent.futures
import colorsys
from collections import deque
import fcntl
import html
import ipaddress
import json
import math
import os
import re
from pathlib import Path
import select
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time
import unicodedata
from urllib.parse import urlsplit

GROUP = ('239.255.255.250', 1982)
SEARCH = (b'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1982\r\n'
          b'MAN: "ssdp:discover"\r\nST: wifi_bulb\r\n\r\n')
PROPERTIES = ('power', 'bright', 'ct', 'rgb', 'color_mode', 'hue', 'sat')
PRIVATE = tuple(ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
MAX_FRAME = 65536
SLIDERS = ('set_bright', 'set_ct_abx', 'set_rgb')
WRITE_PROPS = {'set_power': ('power',), 'set_bright': ('bright',),
               'set_ct_abx': ('ct', 'color_mode'),
               'set_rgb': ('rgb', 'color_mode', 'hue', 'sat')}
QUOTA_MESSAGE = '요청 제한 · 잠시 대기'


def runtime_path():
    root = Path(os.environ.get('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid())))
    return root / 'yuru-yeelight.sock'


def selection_path():
    return Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'yuru-yeelight/selection.json'


def display_name(value):
    if not isinstance(value, str):
        raise ValueError('이름은 문자열이어야 합니다')
    if any(unicodedata.category(c) in ('Cc', 'Zl', 'Zp') for c in value):
        raise ValueError('이름은 줄바꿈 없이 64자까지 입력할 수 있습니다')
    value = value.strip()
    if len(value) > 64:
        raise ValueError('이름은 줄바꿈 없이 64자까지 입력할 수 있습니다')
    return value


def lan_interfaces():
    result = subprocess.run(['ip', '-j', '-4', 'address', 'show'], capture_output=True,
                            text=True, timeout=3, check=True)
    interfaces = []
    for row in json.loads(result.stdout):
        flags = row.get('flags', [])
        name = row.get('ifname', '').split('@')[0]
        # Physical LAN only: never probe public uplinks, VPNs or container bridges.
        if not {'UP', 'MULTICAST'}.issubset(flags) or 'LOOPBACK' in flags:
            continue
        if not (Path('/sys/class/net') / name / 'device').exists():
            continue
        for address in row.get('addr_info', []):
            ip = ipaddress.ip_address(address.get('local', '0.0.0.0'))
            if ip.version == 4 and any(ip in block for block in PRIVATE):
                interfaces.append((str(ip), ipaddress.ip_network(f'{ip}/{address["prefixlen"]}', strict=False)))
    return interfaces


def parse_discovery(data, peer, network):
    if len(data) > 8192:
        raise ValueError('oversized discovery')
    lines = data.decode('utf-8', errors='strict').split('\r\n')
    if lines[0] != 'HTTP/1.1 200 OK':
        raise ValueError('not a discovery response')
    headers = {}
    for line in lines[1:]:
        if ':' in line:
            key, value = line.split(':', 1)
            headers[key.lower().strip()] = value.strip()
    location = urlsplit(headers.get('location', ''))
    ip = ipaddress.ip_address(location.hostname or '')
    if location.scheme != 'yeelight' or str(ip) != peer[0] or ip not in network:
        raise ValueError('discovery endpoint does not match LAN sender')
    if ip.version != 4 or not any(ip in block for block in PRIVATE):
        raise ValueError('endpoint is not a private LAN address')
    port = location.port
    if not port or location.username or location.password or location.query or location.fragment:
        raise ValueError('invalid discovery endpoint')
    identity = headers.get('id', '')
    if not identity or len(identity) > 128 or any(ord(c) < 33 for c in identity):
        raise ValueError('invalid device ID')
    return {'id': identity, 'name': headers.get('name', '')[:100],
            'model': headers.get('model', 'Yeelight')[:48], 'address': (str(ip), port),
            'support': set(headers.get('support', '').split()),
            'props': {key: headers[key] for key in PROPERTIES if key in headers}}



def neighbors():
    result = subprocess.run(['ip', '-j', '-4', 'neighbor', 'show'], capture_output=True,
                            text=True, timeout=3, check=True)
    return {row['dst']: row['lladdr'].lower() for row in json.loads(result.stdout)
            if isinstance(row.get('lladdr'), str) and
            re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', row['lladdr'])}


def fallback_targets(interfaces, known_neighbors):
    targets = set()
    own = {address for address, _ in interfaces}
    for _, network in interfaces:
        if network.prefixlen >= 24:
            targets.update(str(ip) for ip in network.hosts())
        else:
            targets.update(ip for ip in known_neighbors if ipaddress.ip_address(ip) in network)
    return sorted(targets - own, key=ipaddress.ip_address)


def probe_lamp(address):
    """Read-only identification: a listening port alone never counts as a lamp."""
    fields = list(PROPERTIES) + ['name', 'model', 'id']
    try:
        with socket.create_connection((address, 55443), timeout=2) as connection:
            connection.settimeout(2)
            connection.sendall((json.dumps({'id': 1, 'method': 'get_prop', 'params': fields}) + '\r\n').encode())
            data = b''
            until = time.monotonic() + 2
            while time.monotonic() < until:
                connection.settimeout(max(.01, until - time.monotonic()))
                part = connection.recv(4096)
                if not part:
                    return None
                data += part
                if len(data) > MAX_FRAME:
                    return None
                while b'\n' in data:
                    line, data = data.split(b'\n', 1)
                    message = json.loads(line)
                    if not isinstance(message, dict) or message.get('id') != 1:
                        continue
                    values = message.get('result')
                    if not isinstance(values, list) or len(values) != len(fields):
                        return None
                    props = {key: str(value) for key, value in zip(fields, values)}
                    model = props.pop('model')
                    identity = props.pop('id')
                    name = props.pop('name')
                    if props['power'] not in ('on', 'off') or not re.fullmatch(
                            r'(?:yeelink\.light\.)?(?:color|strip|stripe|ceiling|bslamp|mono|lamp|light)[a-zA-Z0-9_.-]*', model):
                        return None
                    support = {'get_prop', 'toggle', 'set_power'}
                    for key, method, low, high in [('bright', 'set_bright', 1, 100),
                                                   ('ct', 'set_ct_abx', 1700, 6500),
                                                   ('rgb', 'set_rgb', 0, 16777215)]:
                        if props[key].isdigit() and low <= int(props[key]) <= high:
                            support.add(method)
                    return {'id': identity, 'name': name[:100], 'model': model[:48],
                            'address': (address, 55443), 'props': props, 'support': support}
    except (OSError, ValueError, TypeError):
        return None


def fallback_due(manual, now, last):
    # A responding SSDP lamp says nothing about other silent models on the LAN.
    return manual or now - last >= 120


def probe_with_retries(address, attempts, stop):
    for attempt in range(attempts):
        if stop.is_set():
            return None
        item = probe_lamp(address)
        if item:
            return item
        if attempt + 1 < attempts:
            stop.wait(.2)
    return None


def fallback_discovery(interfaces, stop, selected=None, neighbor_only=False, probe=None):
    """At most 254 hosts per attached /24; prioritize/retry the selected MAC.

    Yield known neighbors as soon as they answer rather than waiting for all
    absent hosts to time out. A WiFi lamp may miss its first reply after restart.
    """
    existing = neighbors()
    targets = ([address for address in existing
                if any(ipaddress.ip_address(address) in network for _, network in interfaces)]
               if neighbor_only else fallback_targets(interfaces, existing))
    probe = probe or probe_with_retries
    selected_mac = selected[4:] if isinstance(selected, str) and selected.startswith('mac:') else None
    targets.sort(key=lambda address: (0 if existing.get(address) == selected_mac and selected_mac else
                                     1 if address in existing else 2, ipaddress.ip_address(address)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4 if neighbor_only else 12) as pool:
        futures = [pool.submit(probe, address,
                               1 if neighbor_only else
                               3 if (selected_mac and existing.get(address) == selected_mac) or (selected == 'all' and address in existing) else
                               2 if address in existing else 1, stop) for address in targets]
        for future in concurrent.futures.as_completed(futures):
            if stop.is_set():
                for pending in futures:
                    pending.cancel()
                break
            item = future.result()
            if not item:
                continue
            # Connect probes populate the neighbor cache. No MAC, no stable ID.
            mac = item.get('mac') or existing.get(item['address'][0]) or neighbors().get(item['address'][0])
            if not mac:
                continue
            item['mac'] = mac
            item['id'] = 'mac:' + mac
            yield item


def validate_command(method, params):
    if not isinstance(params, list):
        raise ValueError('params must be a list')
    if method == 'toggle' and not params:
        return
    if method not in ('set_power', 'set_bright', 'set_ct_abx', 'set_rgb'):
        raise ValueError('unsupported command')
    if len(params) != 3 or params[1] not in ('smooth', 'sudden'):
        raise ValueError('expected value, effect, duration')
    if type(params[2]) is not int or not 30 <= params[2] <= 5000:
        raise ValueError('invalid transition duration')
    if method == 'set_power':
        valid = params[0] in ('on', 'off')
    else:
        limits = {'set_bright': (1, 100), 'set_ct_abx': (1700, 6500), 'set_rgb': (0, 16777215)}
        low, high = limits[method]
        valid = type(params[0]) is int and low <= params[0] <= high
    if not valid:
        raise ValueError('value out of range')


class Device:
    def __init__(self, manager, record):
        self.manager = manager
        self.id = record['id']
        self.mac = record.get('mac')
        self.address = record['address']
        self.name, self.model = record['name'], record['model']
        self.support = record['support']
        self.props = record['props'].copy()
        self.stale = bool(record.get('stale', False))
        self.online = False
        self.error = None
        self.pending = deque()
        self.inflight = {}
        self.sequence = 0
        self.sent = deque()
        self.last_sent = 0
        self.last_sync = 0
        self.last_control_sent = 0
        self.pending_first = {}
        self.latest_write = {}
        saved = manager.saved_budgets.get(self.id, {})
        self.sent = deque(saved.get('sent', []))
        self.quota_until = saved.get('quota_until', 0)
        self.wake_read = self.wake_write = None
        self.connection = None
        self.buffer = b''
        self.retry_at = 0
        self.thread = threading.Thread(target=self.run, daemon=True)

    def update(self, record):
        self.mac = record.get('mac') or self.mac
        changed = record['address'] != self.address
        self.address = record['address']
        self.name, self.model = record['name'], record['model']
        self.support = record['support']
        # A discovery snapshot must not overwrite newer command results.
        if not self.connection:
            self.props.update(record['props'])
            self.stale = bool(record.get('stale', False))
        if changed:
            self.disconnect('주소 변경 후 다시 연결 중')
            self.retry_at = 0

    def disconnect(self, reason):
        if self.connection:
            self.connection.close()
        self.connection = None
        self.online = False
        self.stale = True
        self.error = reason
        self.buffer = b''
        self.inflight.clear()
        # Never replay a delayed toggle or old slider command after reconnect.
        self.pending.clear()
        self.pending_first.clear()
        self.latest_write.clear()
        self.wake()
        self.retry_at = time.monotonic() + 3

    def wake(self):
        if self.wake_write is not None:
            try:
                self.wake_write.send(b'x')
            except (BlockingIOError, OSError):
                pass

    def queue(self, method, params):
        validate_command(method, params)
        if not self.online:
            raise ValueError('조명에 연결되지 않았습니다')
        if method not in self.support:
            raise ValueError('이 조명이 지원하지 않는 기능입니다')
        now = time.monotonic()
        if now < self.quota_until and method == 'toggle':
            power = self.props.get('power', 'off')
            for queued, values, _ in self.pending:
                if queued == 'set_power':
                    power = values[0]
            method, params = 'set_power', ['off' if power == 'on' else 'on', 'smooth', 100]
        merge = method in SLIDERS or (now < self.quota_until and method == 'set_power')
        existing = [item for item in self.pending if item[0] == method]
        if merge:
            latest = existing[-1][1][0] if existing else next(
                (values[0] for queued, values, _ in reversed(list(self.inflight.values())) if queued == method), None)
            if latest == params[0]:
                return
            first = self.pending_first.get(method, now) if existing else now
            self.pending = deque(item for item in self.pending if item[0] != method)
            self.pending_first[method] = first
        if len(self.pending) >= 16:
            raise ValueError('조작이 너무 빠릅니다. 잠시 기다려 주세요')
        self.pending.append((method, params, now))
        self.wake()

    def adjust(self, delta):
        if type(delta) is not int or delta not in (-5, 5):
            raise ValueError('brightness step must be -5 or 5')
        value = self.props.get('bright', '100')
        for method, params, _ in self.inflight.values():
            if method == 'set_bright':
                value = params[0]
        for method, params, _ in self.pending:
            if method == 'set_bright':
                value = params[0]
        target = max(1, min(100, int(value) + delta))
        if target != int(value):
            self.queue('set_bright', [target, 'smooth', 80])

    def quota_rejected(self, identity, method, params, now):
        self.quota_until = now + 60
        self.error = QUOTA_MESSAGE
        # Keep the rejected absolute target only when no newer target supersedes it.
        newer = any(seq > identity and queued == method for seq, (queued, _, _) in self.inflight.items())
        if method != 'get_prop' and not newer and not any(item[0] == method for item in self.pending):
            self.pending.appendleft((method, params, now))
        # A blocked minute must never replay a long sequence of power toggles.
        latest = {}
        power = self.props.get('power', 'off')
        for queued, values, stamp in self.pending:
            if queued == 'toggle':
                power = 'off' if power == 'on' else 'on'
                queued, values = 'set_power', [power, 'smooth', 100]
            elif queued == 'set_power':
                power = values[0]
            latest.pop(queued, None)
            latest[queued] = (queued, values, stamp)
        self.pending = deque(latest.values())
        self.pending_first = {queued: now for queued in latest}
        self.manager.persist_budget()

    def pending_values(self):
        mapping = {'set_power': 'power', 'set_bright': 'bright', 'set_ct_abx': 'ct', 'set_rgb': 'rgb'}
        values = {}
        for method, params, _ in list(self.inflight.values()) + list(self.pending):
            if method in mapping:
                values[mapping[method]] = str(params[0])
        return values

    def process(self, data):
        self.buffer += data
        if len(self.buffer) > MAX_FRAME:
            raise ValueError('oversized device frame')
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            if not line.strip():
                continue
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError('invalid device frame')
            if message.get('method') == 'props' and isinstance(message.get('params'), dict):
                self.props.update({key: str(value) for key, value in message['params'].items() if key in PROPERTIES})
                self.manager.persist_budget()
                continue
            identity = message.get('id')
            if type(identity) is not int:
                continue
            pending = self.inflight.pop(identity, None)
            if not pending:
                continue
            method, params, _ = pending
            if 'error' in message:
                text = str(message['error'].get('message', '조명 명령 실패'))[:200] if isinstance(message['error'], dict) else '조명 명령 실패'
                if 'quota' in text.lower():
                    self.quota_rejected(identity, method, params, time.monotonic())
                else:
                    self.error = text
                continue
            result = message.get('result')
            if method == 'get_prop' and isinstance(result, list):
                self.props.update({key: str(value) for key, value in zip(PROPERTIES, result)
                                   if value != '' and identity >= self.latest_write.get(key, 0)})
                if len(result) == len(PROPERTIES) and str(result[0]) in ('on', 'off') and str(result[1]).isdigit():
                    self.stale = False
            elif result == ['ok']:
                mapping = {'set_power': 'power', 'set_bright': 'bright', 'set_ct_abx': 'ct', 'set_rgb': 'rgb'}
                current = all(identity >= self.latest_write.get(key, 0) for key in WRITE_PROPS.get(method, ()))
                if method in mapping and current:
                    self.props[mapping[method]] = str(params[0])
                if method == 'set_ct_abx' and current:
                    self.props['color_mode'] = '2'
                elif method == 'set_rgb' and current:
                    self.props['color_mode'] = '1'
                # toggle's authoritative state arrives through props/get_prop.
                elif method == 'toggle':
                    self.last_sync = 0
            if time.monotonic() >= self.quota_until:
                self.error = None
            self.manager.persist_budget()

    def pending_delay(self, now):
        method, _, stamp = self.pending[0]
        if method not in SLIDERS or now - self.last_control_sent >= .25:
            return 0
        first = self.pending_first.get(method, stamp)
        return max(0, min(stamp + .06, first + .15) - now)

    def send_next(self, now):
        if self.inflight and now - min(item[2] for item in self.inflight.values()) > 6:
            raise OSError('조명이 응답하지 않습니다')
        if now < self.quota_until:
            return
        command = None
        if self.pending:
            method = self.pending[0][0]
            # At most two absolute slider writes may be in flight. Discrete power
            # events remain ordered; a slow ACK cannot delay the latest slider forever.
            if len(self.inflight) >= 2 or (self.inflight and
                    (method not in SLIDERS or any(m not in SLIDERS + ('get_prop',)
                                                 for m, _, _ in self.inflight.values()))):
                return
            if self.pending_delay(now) == 0:
                command = self.pending[0][:2]
        elif not self.inflight and now - self.last_sync >= 45 and 'get_prop' in self.support:
            command = ('get_prop', list(PROPERTIES))
        if command is None:
            return
        if not self.manager.allow_send(self, now):
            if self.pending:
                self.error = QUOTA_MESSAGE
            return
        method, params = command
        self.sequence += 1
        self.connection.sendall((json.dumps({'id': self.sequence, 'method': method, 'params': params}) + '\r\n').encode())
        self.inflight[self.sequence] = (method, params, now)
        for key in WRITE_PROPS.get(method, ()):
            self.latest_write[key] = self.sequence
        if method == 'get_prop':
            self.last_sync = now
        else:
            self.last_control_sent = now
            self.pending.popleft()
            self.pending_first.pop(method, None)

    def wait_delay(self, now):
        if not self.pending or len(self.inflight) >= 2:
            return .5
        method = self.pending[0][0]
        if self.inflight and (method not in SLIDERS or any(m not in SLIDERS + ('get_prop',)
                                                          for m, _, _ in self.inflight.values())):
            return .5
        return max(.001, min(.5, max(self.pending_delay(now), self.manager.send_delay(self, now))))

    def run(self):
        self.wake_read, self.wake_write = socket.socketpair()
        self.wake_read.setblocking(False)
        self.wake_write.setblocking(False)
        try:
            while not self.manager.stop.is_set():
                try:
                    with self.manager.lock:
                        address = self.address
                        connection = self.connection
                        retry = self.retry_at
                    if connection is None:
                        if time.monotonic() < retry:
                            self.manager.stop.wait(.2)
                            continue
                        opened = socket.create_connection(address, timeout=2)
                        opened.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        opened.settimeout(1)
                        with self.manager.lock:
                            if address != self.address:
                                opened.close()
                                continue
                            self.connection = connection = opened
                            self.online = True
                            self.error = QUOTA_MESSAGE if time.monotonic() < self.quota_until else None
                            self.last_sync = 0
                    with self.manager.lock:
                        self.send_next(time.monotonic())
                        delay = self.wait_delay(time.monotonic())
                    ready, _, _ = select.select([connection, self.wake_read], [], [], delay)
                    if self.wake_read in ready:
                        try:
                            self.wake_read.recv(65536)
                        except BlockingIOError:
                            pass
                    if connection in ready:
                        data = connection.recv(8192)
                        if not data:
                            raise OSError('조명 연결이 끊어졌습니다')
                        with self.manager.lock:
                            if connection is self.connection:
                                self.process(data)
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    with self.manager.lock:
                        self.disconnect(str(exc)[:200])
        finally:
            with self.manager.lock:
                self.disconnect('종료됨')
            self.wake_read.close()
            self.wake_write.close()
            self.wake_read = self.wake_write = None


class Manager:
    def __init__(self, state_path=None, budget_path=None):
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.discover_now = threading.Event()
        self.last_fallback = -120
        self.last_neighbors = -10
        self.full_scan = None
        self.probing = set()
        self.known_addresses = set()
        self.devices = {}
        self.selected = None
        self.names = {}
        self.error = None
        self.sent = deque()
        self.budget_path = (Path(budget_path) if budget_path is not None else
                            runtime_path().with_suffix('.budget.json') if state_path is None else None)
        self.saved_budgets = {}
        self.load_budget()
        self.state_path = state_path or selection_path()
        try:
            preferences = json.loads(self.state_path.read_text())
            value = preferences.get('id')
            if isinstance(value, str) and len(value) <= 128:
                self.selected = value
            names = preferences.get('names', {})
            if isinstance(names, dict):
                for identity, value in names.items():
                    if (not isinstance(identity, str) or not identity or len(identity) > 128
                            or identity == 'all' or any(ord(c) < 33 for c in identity)):
                        continue
                    try:
                        name = display_name(value)
                    except ValueError:
                        continue
                    if name:
                        self.names[identity] = name
        except (OSError, ValueError, AttributeError):
            pass

    def save_preferences(self, identity, names):
        preferences = {'id': identity}
        if names:
            preferences['names'] = names
        self.state_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix('.tmp')
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, 'w') as output:
                os.fchmod(output.fileno(), 0o600)
                json.dump(preferences, output, ensure_ascii=False)
            os.replace(temporary, self.state_path)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def load_budget(self):
        if self.budget_path is None:
            return
        now = time.monotonic()
        def history(value):
            if not isinstance(value, list):
                return []
            return sorted(stamp for stamp in value[:144] if type(stamp) in (int, float)
                          and math.isfinite(stamp) and now - 60 < stamp <= now)
        try:
            data = json.loads(self.budget_path.read_text())
            saved = data['saved_at']
            if type(saved) not in (int, float) or not math.isfinite(saved) or saved > now:
                return
            self.sent = deque(history(data.get('sent')))
            for identity, record in data.get('devices', {}).items():
                if not isinstance(identity, str) or not isinstance(record, dict):
                    continue
                until = record.get('quota_until', 0)
                until = until if type(until) in (int, float) and math.isfinite(until) and now < until <= now + 60 else 0
                self.saved_budgets[identity] = {'sent': history(record.get('sent')), 'quota_until': until}
                cached = record.get('record')
                if isinstance(cached, dict) and re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', str(cached.get('mac', ''))):
                    model, support, props = cached.get('model'), cached.get('support'), cached.get('props')
                    if (isinstance(model, str) and model and len(model) <= 48 and isinstance(support, list)
                            and all(isinstance(method, str) and len(method) <= 64 for method in support)
                            and isinstance(props, dict)):
                        self.saved_budgets[identity]['record'] = {
                            'mac': cached['mac'], 'name': str(cached.get('name', ''))[:100], 'model': model,
                            'support': support[:64], 'props': {key: str(props[key])[:100] for key in PROPERTIES if key in props}}

        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            pass

    def persist_budget(self):
        if self.budget_path is None:
            return
        devices = dict(self.saved_budgets)
        devices.update({d.id: {'sent': list(d.sent), 'quota_until': d.quota_until,
                              'record': {'mac': d.mac, 'name': d.name, 'model': d.model,
                                         'support': sorted(d.support), 'props': d.props.copy()}}
                        for d in self.devices.values()})
        self.saved_budgets = devices
        data = {'saved_at': time.monotonic(), 'sent': list(self.sent), 'devices': devices}
        temporary = self.budget_path.with_suffix('.tmp')
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, 'w') as output:
                os.fchmod(output.fileno(), 0o600)
                json.dump(data, output)
            os.replace(temporary, self.budget_path)
        except OSError:
            self.error = '요청 제한 기록 저장 실패'

    def send_delay(self, device, now):
        for queue in (device.sent, self.sent):
            while queue and queue[0] <= now - 60:
                queue.popleft()
        return max(0, device.quota_until - now,
                   device.sent[0] + 60 - now if len(device.sent) >= 48 else 0,
                   self.sent[0] + 60 - now if len(self.sent) >= 120 else 0)

    def allow_send(self, device, now):
        # A rolling budget allows quick short bursts without inventing a 1.25s
        # delay for every command. Includes background reads and failed writes.
        if self.send_delay(device, now) > 0:
            return False
        device.last_sent = now
        device.sent.append(now)
        self.sent.append(now)
        self.persist_budget()
        return True

    def found(self, record, start=True):
        with self.lock:
            existing = next((device for device in self.devices.values()
                             if (record.get('mac') and device.mac == record['mac']) or
                             device.address == record['address']), None)
            if existing:
                record = dict(record, id=existing.id)
            if record['id'] in self.devices:
                self.devices[record['id']].update(record)
            else:
                device = Device(self, record)
                self.devices[device.id] = device
                if start:
                    device.thread.start()
            if self.selected is None:
                self.selected = record['id']
            self.error = None
            self.persist_budget()

    def restore_known(self, interfaces, start=True):
        """Resolve verified runtime identities through current LAN neighbors, never saved IPs."""
        current = neighbors()
        own = {address for address, _ in interfaces}
        records = []
        for identity, saved in self.saved_budgets.items():
            cached = saved.get('record')
            if not cached:
                continue
            for address, mac in current.items():
                if mac == cached['mac'] and address not in own and any(
                        ipaddress.ip_address(address) in network for _, network in interfaces):
                    records.append(dict(cached, id=identity, address=(address, 55443),
                                        support=set(cached['support']), stale=True))
                    break
        with self.lock:
            self.known_addresses = {item['address'][0] for item in records}
            for item in records:
                existing = self.devices.get(item['id'])
                if existing is None or existing.address != item['address']:
                    self.found(item, start=start)

    def tcp_probe(self, address, attempts, stop):
        # Full subnet discovery and fast neighbor recovery share address claims.
        # Once a lamp is online its persistent TCP stream owns the connection.
        with self.lock:
            if address in self.probing or address in self.known_addresses or any((d.online or d.connection is not None) and d.address[0] == address
                                             for d in self.devices.values()):
                return None
            self.probing.add(address)
        try:
            item = probe_with_retries(address, attempts, stop)
            if item and not stop.is_set():
                mac = neighbors().get(address)
                if mac:
                    item.update(mac=mac, id='mac:' + mac)
                    self.found(item)
                    return item
            return None
        finally:
            with self.lock:
                self.probing.discard(address)

    def scan_tcp(self, interfaces, neighbor_only=False):
        try:
            for _ in fallback_discovery(interfaces, self.stop, self.selected,
                                        neighbor_only=neighbor_only, probe=self.tcp_probe):
                pass  # tcp_probe registers the lamp before releasing its claim.
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            with self.lock:
                self.error = str(exc)[:200]

    def start_full_scan(self, interfaces, now):
        if self.full_scan is not None and self.full_scan.is_alive():
            return False
        self.last_fallback = now
        self.full_scan = threading.Thread(target=self.scan_tcp, args=(interfaces,), daemon=True)
        self.full_scan.start()
        return True

    def multicast(self, interfaces):
        probes = []
        try:
            for address, network in interfaces:
                probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    probe.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(address))
                    probe.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
                    probe.bind((address, 0))
                    probe.sendto(SEARCH, GROUP)
                    probes.append((probe, network))
                except OSError:
                    probe.close()
            if not probes:
                raise OSError('LAN 검색 요청을 보낼 수 없습니다')
            until = time.monotonic() + 2.5
            while time.monotonic() < until and not self.stop.is_set():
                readable, _, _ = select.select([p for p, _ in probes], [], [], .2)
                for probe in readable:
                    data, peer = probe.recvfrom(8193)
                    try:
                        network = next(network for p, network in probes if p is probe)
                        item = parse_discovery(data, peer, network)
                        item['mac'] = neighbors().get(peer[0])
                        self.found(item)
                    except (ValueError, UnicodeError):
                        continue
        finally:
            for probe, _ in probes:
                probe.close()

    def discover(self):
        next_multicast = 0
        manual = True
        while not self.stop.is_set():
            now = time.monotonic()
            neighbor_due = manual or now - self.last_neighbors >= 10
            multicast_due = manual or now >= next_multicast
            full_due = fallback_due(manual, now, self.last_fallback)
            try:
                if neighbor_due or multicast_due or full_due:
                    interfaces = lan_interfaces()
                    if not interfaces:
                        raise OSError('검색 가능한 사설 LAN 인터페이스가 없습니다')
                    if self.saved_budgets:
                        self.restore_known(interfaces)
                    if full_due:
                        self.start_full_scan(interfaces, now)
                    if neighbor_due:
                        self.last_neighbors = now
                        self.scan_tcp(interfaces, neighbor_only=True)
                    if multicast_due:
                        next_multicast = now + 30
                        self.multicast(interfaces)
                    with self.lock:
                        self.error = None
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                with self.lock:
                    self.error = str(exc)[:200]
            self.discover_now.wait(.5)
            manual = self.discover_now.is_set()
            self.discover_now.clear()

    def status(self):
        return {'selected': self.selected, 'error': self.error,
                'devices': [{'id': d.id, 'name': self.names.get(d.id, d.name), 'model': d.model, 'online': d.online,
                             'support': sorted(d.support), 'props': d.props.copy(), 'error': d.error, 'stale': d.stale,
                             'pending': d.pending_values(),
                             'cooldown': max(0, int(self.send_delay(d, time.monotonic()) + .999))}
                            for d in sorted(self.devices.values(), key=lambda d: d.id)]}

    def dispatch(self, data):
        with self.lock:
            action = data.get('action')
            if action == 'status':
                return self.status()
            if action == 'discover':
                self.discover_now.set()
                return {'queued': True}
            identity = data.get('id') or self.selected
            if not isinstance(identity, str) or (identity != 'all' and identity not in self.devices):
                raise ValueError('조명을 아직 찾지 못했습니다. 다시 검색해 주세요')
            if action == 'select':
                self.save_preferences(identity, self.names)
                self.selected = identity
                return self.status()
            if action == 'rename':
                if identity == 'all':
                    raise ValueError('개별 조명을 선택해 주세요')
                name = display_name(data.get('name'))
                names = self.names.copy()
                if name:
                    names[identity] = name
                else:
                    names.pop(identity, None)
                self.save_preferences(self.selected, names)
                self.names = names
                return self.status()
            if identity == 'all':
                return self.group_action(action, data)
            device = self.devices[identity]
            if action == 'command':
                device.queue(data.get('method'), data.get('params'))
            elif action == 'adjust':
                device.adjust(data.get('delta'))
            else:
                raise ValueError('unknown action')
            return {'queued': True}

    def group_action(self, action, data):
        """Queue one intent across the current online lamps, retaining skip details."""
        if action == 'command':
            method, params = data.get('method'), data.get('params')
            validate_command(method, params)
            if method == 'toggle':
                power = 'on' if any(d.online and d.props.get('power') != 'on'
                                    for d in self.devices.values()) else 'off'
                method, params = 'set_power', [power, 'smooth', 300]
        elif action == 'adjust':
            if type(data.get('delta')) is not int or data['delta'] not in (-5, 5):
                raise ValueError('brightness step must be -5 or 5')
            method = 'set_bright'
        else:
            raise ValueError('unknown action')
        targets, skipped = [], []
        for device in sorted(self.devices.values(), key=lambda d: d.id):
            reason = ('offline' if not device.online else
                      'unsupported' if method not in device.support else None)
            if reason is None:
                try:
                    if action == 'adjust':
                        device.adjust(data['delta'])
                    else:
                        device.queue(method, params.copy())
                    targets.append(device.id)
                except ValueError as exc:
                    reason = str(exc)
            if reason:
                skipped.append({'id': device.id, 'reason': reason})
        if not targets:
            raise ValueError('조절할 수 있는 조명이 없습니다')
        return {'queued': True, 'targets': targets, 'skipped': skipped}


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(2)
        try:
            line = self.rfile.readline(MAX_FRAME + 1)
            if len(line) > MAX_FRAME or not line.endswith(b'\n'):
                raise ValueError('invalid RPC frame')
            data = json.loads(line)
            if not isinstance(data, dict):
                raise ValueError('invalid RPC request')
            result = self.server.manager.dispatch(data)
            response = {'ok': True, 'result': result}
        except (OSError, ValueError, TypeError) as exc:
            response = {'ok': False, 'error': str(exc)[:250]}
        try:
            self.wfile.write((json.dumps(response, ensure_ascii=False) + '\n').encode())
        except OSError:
            pass


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True


def serve():
    path = runtime_path()
    # A second/manual daemon cannot unlink the live service's socket.
    with path.with_suffix('.lock').open('w') as ownership:
        try:
            fcntl.flock(ownership, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Yeelight service is already running')
        path.unlink(missing_ok=True)
        manager = Manager()
        previous_umask = os.umask(0o077)
        try:
            server = Server(str(path), Handler)
        finally:
            os.umask(previous_umask)
        server.manager = manager
        server.timeout = .5
        worker = threading.Thread(target=manager.discover, daemon=True)
        worker.start()
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, lambda *_: (manager.stop.set(), manager.discover_now.set()))
        try:
            while not manager.stop.is_set():
                server.handle_request()
        finally:
            manager.stop.set()
            manager.discover_now.set()
            server.server_close()
            path.unlink(missing_ok=True)


def request(action, **kwargs):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(3)
            connection.connect(str(runtime_path()))
            connection.sendall((json.dumps(dict(kwargs, action=action)) + '\n').encode())
            data = b''
            while b'\n' not in data:
                part = connection.recv(8192)
                if not part:
                    raise RuntimeError('조명 서비스 연결이 끊어졌습니다')
                data += part
                if len(data) > MAX_FRAME:
                    raise RuntimeError('조명 서비스 응답이 너무 큽니다')
            response = json.loads(data.split(b'\n', 1)[0])
            if not response.get('ok'):
                raise RuntimeError(response.get('error', '조명 서비스 오류'))
            return response['result']
    except (OSError, ValueError, KeyError, AttributeError) as exc:
        raise RuntimeError('조명 서비스에 연결할 수 없습니다: ' + str(exc)) from exc


def lamp_summary(device):
    if not device['online'] or device.get('stale'):
        return '—'
    props = device['props']
    if props.get('power') != 'on':
        return 'off'
    if props.get('color_mode') == '2':
        mode = props.get('ct', '?') + ' K'
    else:
        if props.get('color_mode') == '3':
            hue = max(0, min(359, float(props.get('hue') or 0)))
            saturation = max(0, min(100, float(props.get('sat') or 0)))
            channels = colorsys.hsv_to_rgb(hue / 360, saturation / 100, 1)
            rgb = sum(round(value * 255) << shift for value, shift in zip(channels, (16, 8, 0)))
        else:
            rgb = int(props.get('rgb') or 0)
        mode = '컬러 #' + format(rgb, '06X')
    return props.get('bright', '?') + '% · ' + mode


def waybar(status):
    devices = status['devices']
    if status['selected'] == 'all':
        online = [d for d in devices if d['online'] and not d.get('stale')]
        powered = [d for d in online if d['props'].get('power') == 'on']
        tooltip = '\n'.join(['전체'] + [
            (d['name'] or d['model']) + ' · ' + lamp_summary(d) +
            (' · ' + d['error'] if d.get('error') else '') for d in devices])
        if not online:
            text, state = '—', 'unavailable'
        elif not powered:
            text, state = 'off', 'off'
        elif len(powered) != len(online):
            text, state = f'{len(powered)}/{len(online)}', 'on'
        else:
            values = sorted(int(d['props']['bright']) for d in powered
                            if str(d['props'].get('bright', '')).isdigit())
            text = ('?' if not values else str(values[0]) if values[0] == values[-1]
                    else f'{values[0]}–{values[-1]}') + '%'
            state = 'on'
        if online and any(not d['online'] or d.get('stale') or d.get('error') for d in devices):
            state = 'error'
        return {'text': 'light ' + text, 'class': state, 'tooltip': html.escape(tooltip)}
    selected = next((d for d in devices if d['id'] == status['selected']), None)
    if not selected:
        return {'text': 'light —', 'class': 'unavailable', 'tooltip': html.escape(status.get('error') or '')}
    name = selected['name'] or selected['model']
    on = selected['props'].get('power') == 'on'
    text = ('—' if not selected['online'] or selected.get('stale') else
            selected['props'].get('bright', '?') + '%' if on else 'off')
    state = ('unavailable' if not selected['online'] or selected.get('stale') else
             'error' if selected.get('error') else 'on' if on else 'off')
    tooltip = name + '\n' + lamp_summary(selected)
    if selected.get('error'):
        tooltip += '\n' + selected['error']
    return {'text': 'light ' + text, 'class': state, 'tooltip': html.escape(tooltip)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['serve', 'watch', 'status', 'toggle', 'adjust', 'discover'])
    parser.add_argument('delta', nargs='?', type=int, choices=[-5, 5])
    args = parser.parse_args()
    if args.action == 'serve':
        serve()
        return
    if args.action == 'watch':
        last_start = -60
        last_output = None
        while True:
            try:
                output = waybar(request('status'))
            except (RuntimeError, ValueError, TypeError) as exc:
                if time.monotonic() - last_start >= 60:
                    subprocess.run(['systemctl', '--user', 'start', 'yuru-yeelight.service'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8, check=False)
                    last_start = time.monotonic()
                output = {'text': 'light —', 'class': 'unavailable', 'tooltip': html.escape(str(exc))}
            try:
                if output != last_output:
                    print(json.dumps(output, ensure_ascii=False), flush=True)
                    last_output = output
            except BrokenPipeError:
                return
            time.sleep(.1)
    try:
        if args.action == 'toggle':
            output = request('command', method='toggle', params=[])
        elif args.action == 'adjust':
            if args.delta is None:
                parser.error('adjust requires -5 or 5')
            output = request('adjust', delta=args.delta)
        else:
            output = request(args.action)
        print(json.dumps(output, ensure_ascii=False))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        subprocess.run(['notify-send', '-a', 'Yeelight', '조명 제어', str(exc)], check=False)
        raise SystemExit(1)


if __name__ == '__main__':
    main()

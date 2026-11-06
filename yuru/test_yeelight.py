"""LAN protocol/RPC regressions using local mock lamps, never real room lights."""
from collections import deque
import importlib.util
import ipaddress
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('yeelight', Path(__file__).parent / 'templates/waybar/scripts/yeelight.py')
y = importlib.util.module_from_spec(spec)
spec.loader.exec_module(y)


def record(address=('192.168.0.30', 55443)):
    return {'id': '0x1234', 'name': 'Room', 'model': 'color', 'address': address,
            'support': {'get_prop', 'toggle', 'set_power', 'set_bright', 'set_ct_abx', 'set_rgb'},
            'props': {'power': 'on', 'bright': '50', 'ct': '4000', 'rgb': '16711680', 'color_mode': '2'}}


def frame(**kwargs):
    return (json.dumps(kwargs) + '\r\n').encode()


class DiscoveryTests(unittest.TestCase):
    def response(self, ip='192.168.0.30'):
        return (f'HTTP/1.1 200 OK\r\nLocation: yeelight://{ip}:55443\r\n'
                'ID: 0x1234\r\nModel: color\r\nSupport: get_prop toggle set_rgb\r\n'
                'power: on\r\nbright: 50\r\n\r\n').encode()

    def test_discovery_validates_source_and_parses_capabilities(self):
        item = y.parse_discovery(self.response(), ('192.168.0.30', 1982), ipaddress.ip_network('192.168.0.0/24'))
        self.assertEqual(item['address'], ('192.168.0.30', 55443))
        self.assertEqual(item['support'], {'get_prop', 'toggle', 'set_rgb'})
        for data, peer in [(self.response('8.8.8.8'), ('8.8.8.8', 1982)),
                           (self.response('192.168.0.31'), ('192.168.0.30', 1982)),
                           (b'garbage', ('192.168.0.30', 1982)),
                           (b'x' * 9000, ('192.168.0.30', 1982))]:
            with self.assertRaises(ValueError):
                y.parse_discovery(data, peer, ipaddress.ip_network('192.168.0.0/24'))

    def test_interfaces_skip_public_vpn_loopback_and_down(self):
        rows = [{'ifname': name, 'flags': flags, 'addr_info': [{'local': ip, 'prefixlen': 24}]}
                for name, flags, ip in [('enp1', ['UP', 'MULTICAST'], '14.34.74.19'),
                                       ('wlp1', ['UP', 'MULTICAST'], '192.168.0.3'),
                                       ('tailscale0', ['UP', 'MULTICAST'], '10.0.0.2'),
                                       ('lo', ['UP', 'LOOPBACK'], '127.0.0.1'),
                                       ('enp2', ['MULTICAST'], '192.168.0.2')]]
        class Result:
            stdout = json.dumps(rows)
        with patch.object(y.subprocess, 'run', return_value=Result()), patch.object(y.Path, 'exists', lambda p: 'tailscale0' not in str(p)):
            self.assertEqual([r[0] for r in y.lan_interfaces()], ['192.168.0.3'])


class FallbackTests(unittest.TestCase):
    def test_targets_bound_small_subnets_and_only_neighbors_on_large_lans(self):
        interfaces = [('192.168.0.3', ipaddress.ip_network('192.168.0.0/24')),
                      ('10.0.0.2', ipaddress.ip_network('10.0.0.0/16'))]
        targets = y.fallback_targets(interfaces, {'10.0.3.9': 'aa', '8.8.8.8': 'bb'})
        self.assertEqual(len(targets), 254)
        self.assertNotIn('192.168.0.3', targets)
        self.assertIn('10.0.3.9', targets)
        self.assertNotIn('8.8.8.8', targets)
        self.assertNotIn('10.0.3.10', targets)

    def test_verified_lamp_gets_mac_id_and_unknown_listener_is_rejected(self):
        payload = frame(id=1, result=['on', '100', '2772', '3026726', '2', '1', '2', '', 'strip6', ''])
        class Connection:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def settimeout(self, timeout):
                pass
            def sendall(self, data):
                self.sent = json.loads(data)
            def recv(self, size):
                return payload
        connection = Connection()
        with patch.object(y.socket, 'create_connection', return_value=connection):
            lamp = y.probe_lamp('192.168.0.6')
            self.assertEqual(lamp['model'], 'strip6')
            self.assertIn('set_ct_abx', lamp['support'])
            self.assertEqual(connection.sent['method'], 'get_prop')
        payload = frame(id=1, result=['on', '100', '2772', '0', '2', '', '', '', 'not-a-lamp', ''])
        with patch.object(y.socket, 'create_connection', return_value=connection):
            self.assertIsNone(y.probe_lamp('192.168.0.6'))
        with patch.object(y, 'neighbors', return_value={'192.168.0.6': 'aa:bb:cc:dd:ee:ff'}), \
             patch.object(y, 'fallback_targets', return_value=['192.168.0.6']), \
             patch.object(y, 'probe_lamp', return_value=lamp):
            lamps = list(y.fallback_discovery([], threading.Event()))
            self.assertEqual(lamps[0]['id'], 'mac:aa:bb:cc:dd:ee:ff')

    def test_wifi_response_over_old_half_second_cutoff_is_accepted(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        real_connect = socket.create_connection
        def lamp():
            connection, _ = listener.accept()
            with connection:
                connection.recv(4096)
                time.sleep(.65)
                connection.sendall(frame(id=1, result=['on', '100', '2772', '0', '2', '67', '19', '', 'colorb', '']))
        worker = threading.Thread(target=lamp, daemon=True)
        worker.start()
        try:
            with patch.object(y.socket, 'create_connection',
                              side_effect=lambda address, timeout: real_connect(listener.getsockname(), timeout=timeout)):
                lamp = y.probe_lamp('192.168.0.8')
            self.assertEqual(lamp['model'], 'colorb')
        finally:
            worker.join(2)
            listener.close()

    def test_neighbor_discovery_yields_before_missing_hosts_finish_and_retries(self):
        selected = 'mac:aa:bb:cc:dd:ee:ff'
        release = threading.Event()
        calls = []
        def probe(address, attempts, stop):
            calls.append((address, attempts))
            if address == '192.168.0.8':
                return dict(record(), address=(address, 55443))
            release.wait(2)
            return None
        with patch.object(y, 'neighbors', return_value={'192.168.0.8': selected[4:]}), \
             patch.object(y, 'fallback_targets', return_value=['192.168.0.30', '192.168.0.8']), \
             patch.object(y, 'probe_with_retries', side_effect=probe):
            discovery = y.fallback_discovery([], threading.Event(), selected)
            started = time.monotonic()
            try:
                item = next(discovery)
                self.assertLess(time.monotonic() - started, .5)
                self.assertEqual(item['id'], selected)
                self.assertEqual(calls[0], ('192.168.0.8', 3))
            finally:
                release.set()
                discovery.close()
        with patch.object(y, 'probe_lamp', side_effect=[None, None, record()]) as attempted:
            self.assertEqual(y.probe_with_retries('192.168.0.8', 3, threading.Event())['model'], 'color')
            self.assertEqual(attempted.call_count, 3)

    def test_partial_ssdp_does_not_suppress_fallback(self):
        self.assertTrue(y.fallback_due(True, 10, 0))
        self.assertTrue(y.fallback_due(False, 121, 0))
        self.assertFalse(y.fallback_due(False, 100, 0))

    def test_neighbor_retry_recovers_missing_lamp_while_subnet_scan_is_blocked(self):
        interfaces = [('192.168.0.3', ipaddress.ip_network('192.168.0.0/24'))]
        release, full_started = threading.Event(), threading.Event()
        attempts = []
        def probe(address, count, stop):
            if address == '192.168.0.200':
                full_started.set()
                release.wait(3)
                return None
            attempts.append(address)
            return None if len(attempts) == 1 else record((address, 55443))
        with tempfile.TemporaryDirectory() as directory:
            manager = y.Manager(Path(directory) / 'selection.json')
            found = manager.found
            with patch.object(y, 'neighbors', return_value={'192.168.0.8': 'aa:bb:cc:dd:ee:ff'}), \
                 patch.object(y, 'fallback_targets', return_value=['192.168.0.200']), \
                 patch.object(y, 'probe_with_retries', side_effect=probe), \
                 patch.object(manager, 'found', side_effect=lambda item: found(item, start=False)):
                try:
                    self.assertTrue(manager.start_full_scan(interfaces, 100))
                    self.assertTrue(full_started.wait(1))
                    self.assertFalse(manager.start_full_scan(interfaces, 101))
                    manager.scan_tcp(interfaces, neighbor_only=True)
                    self.assertFalse(manager.devices)
                    started = time.monotonic()
                    manager.scan_tcp(interfaces, neighbor_only=True)
                    self.assertLess(time.monotonic() - started, .5)
                    self.assertIn('mac:aa:bb:cc:dd:ee:ff', manager.devices)
                    self.assertTrue(manager.full_scan.is_alive())
                finally:
                    release.set()
                    manager.full_scan.join(2)

    def test_recovery_schedule_is_ten_seconds_and_skips_online_or_claimed_addresses(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = y.Manager(Path(directory) / 'selection.json')
            neighbor_times = []
            clock = [100]
            def start_full(interfaces, now):
                manager.last_fallback = now
            def scan(interfaces, neighbor_only=False):
                neighbor_times.append(clock[0])
                if len(neighbor_times) == 2:
                    manager.stop.set()
            def advance(timeout):
                clock[0] += 1
                return False
            with patch.object(y, 'lan_interfaces', return_value=[('192.168.0.3', ipaddress.ip_network('192.168.0.0/24'))]), \
                 patch.object(y.time, 'monotonic', side_effect=lambda: clock[0]), \
                 patch.object(manager, 'start_full_scan', side_effect=start_full), \
                 patch.object(manager, 'scan_tcp', side_effect=scan), \
                 patch.object(manager, 'multicast'), patch.object(manager.discover_now, 'wait', side_effect=advance):
                manager.discover()
            self.assertEqual(neighbor_times, [100, 110])
            manager.stop.clear()
            manager.found(record(), start=False)
            manager.devices['0x1234'].online = True
            manager.probing.add('192.168.0.31')
            with patch.object(y, 'probe_with_retries') as probe:
                self.assertIsNone(manager.tcp_probe('192.168.0.30', 1, manager.stop))
                self.assertIsNone(manager.tcp_probe('192.168.0.31', 1, manager.stop))
                probe.assert_not_called()

    def test_mac_identity_survives_ip_change_and_later_ssdp_deduplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = y.Manager(Path(directory) / 'selection.json')
            item = dict(record(), id='mac:aa:bb:cc:dd:ee:ff', mac='aa:bb:cc:dd:ee:ff')
            manager.found(item, start=False)
            manager.found(dict(item, address=('192.168.0.40', 55443)), start=False)
            manager.found(dict(item, id='0x1234', address=('192.168.0.40', 55443)), start=False)
            self.assertEqual(list(manager.devices), ['mac:aa:bb:cc:dd:ee:ff'])
            self.assertEqual(manager.devices[item['id']].address[0], '192.168.0.40')


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manager = y.Manager(Path(self.temp.name) / 'selection.json')
        self.manager.found(record(), start=False)
        self.device = self.manager.devices['0x1234']
        self.device.online = True

    def test_address_changes_reuse_id_and_drop_stale_commands(self):
        self.device.queue('toggle', [])
        self.manager.found(record(('192.168.0.40', 55443)), start=False)
        self.assertEqual(len(self.manager.devices), 1)
        self.assertEqual(self.device.address, ('192.168.0.40', 55443))
        self.assertFalse(self.device.online)
        self.assertFalse(self.device.pending)
        self.assertEqual(self.manager.selected, self.device.id)

    def test_selection_persists_only_id(self):
        self.manager.dispatch({'action': 'select', 'id': self.device.id})
        data = json.loads(self.manager.state_path.read_text())
        self.assertEqual(data, {'id': '0x1234'})
        self.assertEqual(self.manager.state_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(y.Manager(self.manager.state_path).selected, '0x1234')

    def test_local_rename_offline_persists_across_selection_and_changed_address(self):
        self.device.online = False
        now = time.monotonic()
        self.device.sent.append(now)
        self.manager.sent.append(now)
        with patch.object(self.device, 'queue', side_effect=AssertionError('LAN write')), \
             patch.object(self.manager, 'allow_send', side_effect=AssertionError('quota write')), \
             patch.object(self.manager, 'persist_budget', side_effect=AssertionError('LAN cache write')):
            result = self.manager.dispatch({'action': 'rename', 'id': self.device.id, 'name': '  침실 🌙  '})
        self.assertEqual(result['devices'][0]['name'], '침실 🌙')
        self.assertEqual(self.device.name, 'Room')
        self.assertEqual(list(self.device.sent), [now])
        self.assertEqual(list(self.manager.sent), [now])
        self.assertFalse(self.device.pending)
        self.manager.dispatch({'action': 'select', 'id': 'all'})
        data = json.loads(self.manager.state_path.read_text())
        self.assertEqual(data, {'id': 'all', 'names': {'0x1234': '침실 🌙'}})
        self.assertEqual(self.manager.state_path.stat().st_mode & 0o777, 0o600)
        restarted = y.Manager(self.manager.state_path)
        fresh = dict(record(('192.168.0.44', 55443)), name='Remote name')
        restarted.found(fresh, start=False)
        self.assertEqual(restarted.selected, 'all')
        self.assertEqual(restarted.status()['devices'][0]['name'], '침실 🌙')
        self.assertEqual(restarted.devices[self.device.id].name, 'Remote name')
        restarted.dispatch({'action': 'select', 'id': self.device.id})
        self.assertEqual(json.loads(restarted.state_path.read_text())['names'], {'0x1234': '침실 🌙'})
        reset = restarted.dispatch({'action': 'rename', 'id': self.device.id, 'name': '   '})
        self.assertEqual(reset['devices'][0]['name'], 'Remote name')
        self.assertEqual(json.loads(restarted.state_path.read_text()), {'id': '0x1234'})
        self.assertFalse(y.Manager(restarted.state_path).names)

    def test_rename_does_not_replace_raw_discovery_or_runtime_cache_names(self):
        self.manager.budget_path = Path(self.temp.name) / 'budget.json'
        self.device.mac = 'aa:bb:cc:dd:ee:ff'
        self.manager.dispatch({'action': 'rename', 'id': self.device.id, 'name': '<작업등>'})
        self.manager.found(dict(record(), name='Fresh device name'), start=False)
        self.device.process(frame(method='props', params={'bright': '42'}))
        self.assertEqual(self.manager.status()['devices'][0]['name'], '<작업등>')
        self.assertEqual(self.device.name, 'Fresh device name')
        cached = json.loads(self.manager.budget_path.read_text())['devices'][self.device.id]['record']
        self.assertEqual(cached['name'], 'Fresh device name')
        self.assertNotIn('<작업등>', self.manager.budget_path.read_text())

    def test_rename_rejects_group_unknown_id_and_invalid_names_without_writing(self):
        self.manager.dispatch({'action': 'select', 'id': self.device.id})
        original = self.manager.state_path.read_bytes()
        for name in (None, True, 1, [], {}, 'x' * 65, 'a\nb', '\x00', '\x85', '\u2028'):
            with self.subTest(name=repr(name)), self.assertRaises(ValueError):
                self.manager.dispatch({'action': 'rename', 'id': self.device.id, 'name': name})
            self.assertEqual(self.manager.state_path.read_bytes(), original)
            self.assertFalse(self.manager.names)
        for identity in ('all', 'unknown'):
            with self.assertRaises(ValueError):
                self.manager.dispatch({'action': 'rename', 'id': identity, 'name': 'Valid'})
            self.assertEqual(self.manager.state_path.read_bytes(), original)
        self.manager.dispatch({'action': 'rename', 'id': self.device.id, 'name': '  ' + '가' * 64 + '  '})
        self.assertEqual(self.manager.names[self.device.id], '가' * 64)

    def test_failed_preference_replace_preserves_rename_and_selection(self):
        self.manager.dispatch({'action': 'rename', 'id': self.device.id, 'name': 'Original'})
        self.manager.dispatch({'action': 'select', 'id': 'all'})
        original = self.manager.state_path.read_bytes()
        with patch.object(y.os, 'replace', side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):
                self.manager.dispatch({'action': 'rename', 'id': self.device.id, 'name': 'Changed'})
            with self.assertRaises(OSError):
                self.manager.dispatch({'action': 'select', 'id': self.device.id})
        self.assertEqual(self.manager.names, {self.device.id: 'Original'})
        self.assertEqual(self.manager.selected, 'all')
        self.assertEqual(self.manager.state_path.read_bytes(), original)
        self.assertFalse(self.manager.state_path.with_suffix('.tmp').exists())

    def test_preference_load_ignores_invalid_alias_entries(self):
        names = {'good': '  Saved 🌙  ', 'bad': 2, 'long': 'x' * 65, 'all': 'Group',
                 'empty': '   ', 'line': 'two\nlines', 'bad id': 'Name'}
        self.manager.state_path.write_text(json.dumps({'id': 'all', 'names': names}))
        restarted = y.Manager(self.manager.state_path)
        self.assertEqual(restarted.selected, 'all')
        self.assertEqual(restarted.names, {'good': 'Saved 🌙'})
        self.manager.state_path.write_text(json.dumps({'id': 'all', 'names': []}))
        self.assertFalse(y.Manager(self.manager.state_path).names)

    def test_brightness_wheel_accumulates_coalesces_and_clamps(self):
        for _ in range(20):
            self.manager.dispatch({'action': 'adjust', 'delta': 5})
        self.assertEqual(len(self.device.pending), 1)
        self.assertEqual(self.device.pending[0][1][0], 100)
        for _ in range(30):
            self.device.adjust(-5)
        self.assertEqual(self.device.pending[0][1][0], 1)
        self.device.inflight[1] = ('set_bright', [35, 'smooth', 200], 0)
        self.device.pending.clear()
        self.device.adjust(5)
        self.assertEqual(self.device.pending[0][1][0], 40)

    def test_command_validation_capabilities_and_offline(self):
        for method, params in [('set_bright', [0, 'smooth', 200]), ('set_rgb', [-1, 'sudden', 200]),
                               ('set_power', ['broken', 'smooth', 200]), ('set_ct_abx', [6501, 'smooth', 200]),
                               ('set_music', [1]), ('set_bright', [True, 'smooth', 200])]:
            with self.assertRaises(ValueError):
                self.device.queue(method, params)
        self.device.support.remove('set_rgb')
        with self.assertRaises(ValueError):
            self.device.queue('set_rgb', [12, 'smooth', 200])
        self.device.online = False
        with self.assertRaises(ValueError):
            self.device.queue('toggle', [])

    def test_fragmented_notifications_and_reply_do_not_double_toggle(self):
        self.device.inflight[1] = ('toggle', [], time.monotonic())
        data = frame(method='props', params={'power': 'off', 'bright': 42}) + frame(id=1, result=['ok'])
        self.device.process(data[:15])
        self.device.process(data[15:])
        self.assertEqual(self.device.props['power'], 'off')
        self.assertEqual(self.device.props['bright'], '42')
        self.assertFalse(self.device.inflight)
        self.assertEqual(self.device.last_sync, 0)

    def test_rate_budget_covers_all_devices_and_ping_commands(self):
        now = 1000
        self.assertTrue(self.manager.allow_send(self.device, now))
        self.assertTrue(self.manager.allow_send(self.device, now + .05))
        self.device.sent = deque([now] * 48)
        self.assertFalse(self.manager.allow_send(self.device, now + 2))
        self.device.sent.clear()
        self.manager.sent = deque([now] * 120)
        self.assertFalse(self.manager.allow_send(self.device, now + 2))
        self.assertTrue(self.manager.allow_send(self.device, now + 61))

    def capture_connection(self):
        class Connection:
            def __init__(self):
                self.messages = []
            def sendall(self, data):
                self.messages.append(json.loads(data))
        self.device.connection = Connection()
        self.device.last_sync = 1000
        return self.device.connection.messages

    def test_first_step_is_immediate_and_rapid_wheel_sends_coalesced_final(self):
        messages = self.capture_connection()
        with patch.object(y.time, 'monotonic', return_value=1000):
            self.device.adjust(5)
            self.device.send_next(1000)
        self.assertEqual([m['params'][0] for m in messages], [55])
        with patch.object(y.time, 'monotonic', return_value=1000.02):
            for _ in range(5):
                self.device.adjust(5)
        self.device.send_next(1000.07)
        self.assertEqual(len(messages), 1)
        self.device.send_next(1000.081)
        self.assertEqual([m['params'][0] for m in messages], [55, 80])
        self.assertEqual(len(self.device.inflight), 2)
        self.assertFalse(self.device.pending)

    def test_continuous_wheel_is_not_starved_by_trailing_debounce(self):
        messages = self.capture_connection()
        with patch.object(y.time, 'monotonic', return_value=1000):
            self.device.adjust(5)
            self.device.send_next(1000)
        for elapsed in [.02, .05, .08, .11, .14, .17]:
            with patch.object(y.time, 'monotonic', return_value=1000 + elapsed):
                self.device.adjust(5)
                self.device.send_next(1000 + elapsed)
        self.assertEqual([m['params'][0] for m in messages], [55, 85])
        self.assertLessEqual(messages[-1]['params'][2], 100)

    def test_older_slider_ack_and_getter_do_not_revert_newer_target(self):
        messages = self.capture_connection()
        with patch.object(y.time, 'monotonic', return_value=1000):
            self.device.queue('set_bright', [55, 'smooth', 80])
            self.device.send_next(1000)
        with patch.object(y.time, 'monotonic', return_value=1000.02):
            self.device.queue('set_bright', [80, 'smooth', 80])
        self.device.send_next(1000.081)
        self.device.process(frame(id=messages[1]['id'], result=['ok']))
        self.device.process(frame(id=messages[0]['id'], result=['ok']))
        self.assertEqual(self.device.props['bright'], '80')
        self.device.inflight[0] = ('get_prop', list(y.PROPERTIES), 1000)
        self.device.process(frame(id=0, result=['on', '50', '4000', '16711680', '2', '0', '100']))
        self.assertEqual(self.device.props['bright'], '80')

    def test_power_events_are_ordered_while_slider_pipeline_is_bounded(self):
        messages = self.capture_connection()
        self.device.inflight[1] = ('set_bright', [55, 'smooth', 80], 1000)
        with patch.object(y.time, 'monotonic', return_value=1000):
            self.device.queue('toggle', [])
        self.device.send_next(1000)
        self.assertFalse(messages)
        self.device.inflight.clear()
        self.device.send_next(1000)
        self.assertEqual(messages[0]['method'], 'toggle')
        with patch.object(y.time, 'monotonic', return_value=1000.02):
            self.device.adjust(5)
        self.device.send_next(1000.2)
        self.assertEqual(len(messages), 1)

    def test_quota_rejection_backs_off_reads_and_keeps_only_latest_target(self):
        messages = self.capture_connection()
        with patch.object(y.time, 'monotonic', return_value=1000):
            self.device.queue('set_bright', [55, 'smooth', 80])
            self.device.send_next(1000)
            self.device.process(frame(id=messages[0]['id'], error={'code':-1,'message':'client quota exceeded'}))
        self.assertEqual(self.device.quota_until, 1060)
        self.assertEqual(self.device.error, y.QUOTA_MESSAGE)
        with patch.object(y.time, 'monotonic', return_value=1001):
            for _ in range(6):
                self.device.adjust(5)
        self.assertEqual(len(self.device.pending), 1)
        self.assertEqual(self.device.pending[0][1][0], 85)
        self.device.send_next(1059.9)
        self.assertEqual(len(messages), 1)
        self.device.send_next(1060.01)
        self.assertEqual([m['params'][0] for m in messages], [55, 85])
        with patch.object(y.time, 'monotonic', return_value=1060.02):
            self.device.process(frame(id=messages[-1]['id'], result=['ok']))
        self.assertIsNone(self.device.error)

    def test_quota_old_rejection_preserves_newer_inflight_target_and_power_intent(self):
        messages = self.capture_connection()
        with patch.object(y.time, 'monotonic', return_value=1000):
            self.device.queue('set_bright', [55, 'smooth', 80])
            self.device.send_next(1000)
        with patch.object(y.time, 'monotonic', return_value=1000.02):
            self.device.queue('set_bright', [80, 'smooth', 80])
        self.device.send_next(1000.081)
        with patch.object(y.time, 'monotonic', return_value=1000.1):
            self.device.process(frame(id=messages[0]['id'], error={'message':'client quota exceeded'}))
        self.assertFalse(self.device.pending)
        with patch.object(y.time, 'monotonic', return_value=1000.11):
            self.device.process(frame(id=messages[1]['id'], error={'message':'client quota exceeded'}))
            self.device.queue('toggle', [])
            self.device.queue('toggle', [])
        self.assertEqual(self.device.pending[0][1][0], 80)
        powers = [params[0] for method, params, _ in self.device.pending if method == 'set_power']
        self.assertEqual(powers, ['on'])

    def test_wheel_at_clamp_does_not_send_duplicate_requests(self):
        self.device.props['bright'] = '100'
        for _ in range(50):
            self.device.adjust(5)
        self.assertFalse(self.device.pending)

    def test_error_ack_and_oversized_device_frame(self):
        self.device.inflight[1] = ('set_rgb', [12, 'smooth', 200], 0)
        self.device.process(frame(id=1, error={'code': -1, 'message': 'unsupported'}))
        self.assertEqual(self.device.error, 'unsupported')
        with self.assertRaises(ValueError):
            self.device.process(b'x' * (y.MAX_FRAME + 1))

    def test_runtime_budget_and_quota_survive_service_restart_without_addresses(self):
        budget = Path(self.temp.name) / 'runtime-budget.json'
        with patch.object(y.time, 'monotonic', return_value=1000):
            first = y.Manager(self.manager.state_path, budget_path=budget)
            first.found(record(), start=False)
            lamp = first.devices['0x1234']
            lamp.online = True
            for _ in range(48):
                self.assertTrue(first.allow_send(lamp, 1000))
            lamp.quota_rejected(1, 'set_bright', [60,'smooth',80], 1000)
        self.assertEqual(budget.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('192.168.', budget.read_text())
        with patch.object(y.time, 'monotonic', return_value=1001):
            second = y.Manager(self.manager.state_path, budget_path=budget)
            second.found(record(), start=False)
            recovered = second.devices['0x1234']
            self.assertEqual(len(recovered.sent), 48)
            self.assertEqual(recovered.quota_until, 1060)
            self.assertFalse(second.allow_send(recovered, 1001))
            self.assertEqual(second.status()['devices'][0]['cooldown'], 59)
        with patch.object(y.time, 'monotonic', return_value=1061):
            self.assertTrue(second.allow_send(recovered, 1061))
            third = y.Manager(self.manager.state_path, budget_path=budget)
            third.found(record(), start=False)
            self.assertEqual(list(third.devices['0x1234'].sent), [1061])
            self.assertEqual(third.devices['0x1234'].quota_until, 0)

    def test_cached_known_lamp_resolves_changed_ip_without_quota_spending_probe(self):
        budget = Path(self.temp.name) / 'runtime-budget.json'
        mac = 'aa:bb:cc:dd:ee:ff'
        identity = 'mac:' + mac
        interfaces = [('192.168.0.3', ipaddress.ip_network('192.168.0.0/24'))]
        with patch.object(y.time, 'monotonic', return_value=1000):
            first = y.Manager(self.manager.state_path, budget_path=budget)
            first.found(dict(record(), id=identity, mac=mac), start=False)
            first.devices[identity].quota_until = 1060
            first.persist_budget()
        with patch.object(y.time, 'monotonic', return_value=1001), \
             patch.object(y, 'neighbors', return_value={'192.168.0.44':mac}), \
             patch.object(y, 'probe_lamp') as probe:
            restarted = y.Manager(self.manager.state_path, budget_path=budget)
            restarted.restore_known(interfaces, start=False)
            lamp = restarted.devices[identity]
            self.assertEqual(lamp.address, ('192.168.0.44',55443))
            self.assertTrue(lamp.stale)
            lamp.online = True
            self.assertEqual(y.waybar(restarted.status())['text'], 'light —')
            self.assertIsNone(restarted.tcp_probe('192.168.0.44',1,restarted.stop))
            probe.assert_not_called()
            lamp.inflight[1] = ('get_prop',list(y.PROPERTIES),1001)
            lamp.process(frame(id=1,error={'message':'client quota exceeded'}))
            self.assertTrue(lamp.stale)
            self.assertEqual(lamp.quota_until,1061)
            self.assertIsNone(restarted.tcp_probe('192.168.0.44',1,restarted.stop))
            probe.assert_not_called()
        with patch.object(y.time,'monotonic',return_value=1062):
            lamp.inflight[2] = ('get_prop',list(y.PROPERTIES),1062)
            lamp.process(frame(id=2,result=['on','60','4000','16711680','2','0','100']))
            self.assertFalse(lamp.stale)
            self.assertEqual(y.waybar(restarted.status())['text'],'light 60%')
        data = budget.read_text()
        self.assertNotIn('192.168.',data)
        self.assertIn('"mac": "'+mac+'"',data)

    def test_cached_roster_needs_matching_mac_on_current_private_interface(self):
        budget = Path(self.temp.name) / 'runtime-budget.json'
        mac = 'aa:bb:cc:dd:ee:ff'
        interfaces = [('192.168.0.3', ipaddress.ip_network('192.168.0.0/24'))]
        with patch.object(y.time,'monotonic',return_value=1000):
            first = y.Manager(self.manager.state_path,budget_path=budget)
            first.found(dict(record(),id='mac:'+mac,mac=mac),start=False)
        with patch.object(y.time,'monotonic',return_value=1001), \
             patch.object(y,'neighbors',return_value={'8.8.8.8':mac,'192.168.0.44':'11:22:33:44:55:66'}):
            restarted = y.Manager(self.manager.state_path,budget_path=budget)
            restarted.restore_known(interfaces,start=False)
            self.assertFalse(restarted.devices)
            self.assertFalse(restarted.known_addresses)

    def test_pending_status_distinguishes_desired_from_confirmed(self):
        self.device.inflight[1] = ('set_bright', [55,'smooth',80], 1000)
        self.device.queue('set_bright', [80,'smooth',80])
        status = self.manager.status()['devices'][0]
        self.assertEqual(status['props']['bright'], '50')
        self.assertEqual(status['pending']['bright'], '80')

    def test_tooltip_escapes_device_markup(self):
        self.device.name = '<b>not markup</b>'
        output = y.waybar(self.manager.status())
        self.assertIn('&lt;b&gt;', output['tooltip'])

    def test_hsv_tooltip_uses_hue_and_saturation_instead_of_stale_rgb(self):
        self.device.props.update(color_mode='3', hue='120', sat='100', rgb='16711680')
        self.assertIn('컬러 #00FF00', y.waybar(self.manager.status())['tooltip'])
        self.device.props['color_mode'] = '1'
        self.assertIn('컬러 #FF0000', y.waybar(self.manager.status())['tooltip'])


class GroupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manager = y.Manager(Path(self.temp.name) / 'selection.json')
        for number in range(3):
            item = record((f'192.168.0.{30 + number}', 55443))
            item['id'] = f'lamp-{number}'
            self.manager.found(item, start=False)
            self.manager.devices[item['id']].online = True
        self.lamps = list(self.manager.devices.values())
        self.manager.dispatch({'action': 'select', 'id': 'all'})

    def command(self, method, params):
        return self.manager.dispatch({'action': 'command', 'method': method, 'params': params})

    def test_all_scope_persists_without_discovered_devices(self):
        manager = y.Manager(Path(self.temp.name) / 'empty.json')
        self.assertEqual(manager.dispatch({'action': 'select', 'id': 'all'})['selected'], 'all')
        self.assertEqual(y.Manager(manager.state_path).selected, 'all')
        manager.found(record(), start=False)
        self.assertEqual(manager.selected, 'all')
        self.assertEqual(json.loads(manager.state_path.read_text()), {'id': 'all'})
        self.assertEqual(manager.state_path.stat().st_mode & 0o777, 0o600)

    def test_group_toggle_sets_one_power_target_instead_of_inverting_each_lamp(self):
        self.lamps[1].props['power'] = 'off'
        result = self.command('toggle', [])
        self.assertEqual(result['targets'], [d.id for d in self.lamps])
        self.assertEqual(result['skipped'], [])
        for device in self.lamps:
            self.assertEqual(device.pending[0][:2], ('set_power', ['on', 'smooth', 300]))
            device.pending.clear()
            device.props['power'] = 'on'
        self.command('toggle', [])
        self.assertTrue(all(d.pending[0][1][0] == 'off' for d in self.lamps))

    def test_fanout_reports_offline_unsupported_and_queue_failure(self):
        self.lamps[1].support.remove('set_rgb')
        self.lamps[2].online = False
        result = self.command('set_rgb', [123, 'smooth', 200])
        self.assertEqual(result['targets'], ['lamp-0'])
        self.assertEqual(result['skipped'], [{'id': 'lamp-1', 'reason': 'unsupported'},
                                             {'id': 'lamp-2', 'reason': 'offline'}])
        self.assertFalse(self.lamps[1].pending)
        self.assertFalse(self.lamps[2].pending)
        for _ in range(16):
            self.lamps[1].queue('toggle', [])
        result = self.command('set_power', ['off', 'smooth', 200])
        self.assertEqual(result['targets'], ['lamp-0'])
        self.assertIn('너무 빠릅니다', result['skipped'][0]['reason'])

    def test_group_adjust_preserves_each_level_clamps_and_coalesces(self):
        self.lamps[0].props['bright'] = '99'
        self.lamps[1].props['bright'] = '2'
        self.lamps[2].online = False
        self.manager.dispatch({'action': 'adjust', 'delta': 5})
        self.assertEqual([d.pending[0][1][0] for d in self.lamps[:2]], [100, 7])
        for _ in range(4):
            self.manager.dispatch({'action': 'adjust', 'delta': -5})
        self.assertEqual([d.pending[0][1][0] for d in self.lamps[:2]], [80, 1])
        self.assertEqual([len(d.pending) for d in self.lamps], [1, 1, 0])

    def test_invalid_group_input_never_partially_queues_and_empty_scope_errors(self):
        for action in [{'action': 'command', 'method': 'toggle', 'params': [1]},
                       {'action': 'command', 'method': 'set_bright', 'params': [0, 'smooth', 200]},
                       {'action': 'adjust', 'delta': True}]:
            with self.assertRaises(ValueError):
                self.manager.dispatch(action)
            self.assertTrue(all(not d.pending for d in self.lamps))
        for device in self.lamps:
            device.online = False
        with self.assertRaisesRegex(ValueError, '조절할'):
            self.command('toggle', [])

    def test_group_bar_shows_brightness_range_power_count_and_only_values(self):
        self.assertEqual(y.waybar(self.manager.status())['text'], 'light 50%')
        self.lamps[0].props['bright'] = '20'
        self.lamps[1].props['bright'] = '80'
        self.assertEqual(y.waybar(self.manager.status())['text'], 'light 20–80%')
        self.lamps[1].props['power'] = 'off'
        output = y.waybar(self.manager.status())
        self.assertEqual(output['text'], 'light 2/3')
        self.assertNotIn('클릭', output['tooltip'])
        self.assertNotIn('연결', output['tooltip'])
        self.lamps[2].online = False
        output = y.waybar(self.manager.status())
        self.assertEqual(output['text'], 'light 1/2')
        self.assertEqual(output['class'], 'error')
        self.assertIn('—', output['tooltip'])
        self.lamps[0].props['power'] = 'off'
        self.assertEqual(y.waybar(self.manager.status())['text'], 'light off')
        self.lamps[0].online = self.lamps[1].online = False
        self.assertEqual(y.waybar(self.manager.status())['text'], 'light —')
        self.manager.selected = 'lamp-0'
        self.assertEqual(y.waybar(self.manager.status())['text'], 'light —')


class NetworkTests(unittest.TestCase):
    def test_tcp_connection_notification_command_and_reconnect(self):
        stop = threading.Event()
        ready = threading.Event()
        received = []
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        listener.settimeout(.2)
        self.addCleanup(listener.close)
        connections = []

        def lamp():
            while not stop.is_set():
                try:
                    connection, _ = listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                connections.append(connection)
                connection.settimeout(.2)
                try:
                    data = b''
                    while not stop.is_set():
                        try:
                            data += connection.recv(8192)
                        except socket.timeout:
                            continue
                        if not data:
                            break
                        while b'\n' in data:
                            line, data = data.split(b'\n', 1)
                            request = json.loads(line)
                            received.append(request)
                            if request['method'] == 'get_prop':
                                result = ['on', '50', '4000', '16711680', '2', '0', '100']
                                payload = frame(id=request['id'], result=result)
                            else:
                                payload = frame(method='props', params={'bright': '55'}) + frame(id=request['id'], result=['ok'])
                            connection.sendall(payload[:9])
                            connection.sendall(payload[9:])
                            ready.set()
                except OSError:
                    pass
                finally:
                    connection.close()

        thread = threading.Thread(target=lamp, daemon=True)
        thread.start()
        with tempfile.TemporaryDirectory() as directory:
            manager = y.Manager(Path(directory) / 'selection.json')
            manager.found(record(listener.getsockname()))
            device = manager.devices['0x1234']
            try:
                self.assertTrue(ready.wait(3))
                with manager.lock:
                    device.adjust(5)
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    with manager.lock:
                        if device.props.get('bright') == '55':
                            break
                    time.sleep(.02)
                self.assertEqual(device.props['bright'], '55')
                self.assertIn('set_bright', [item['method'] for item in received])
                ready.clear()
                connections[0].shutdown(socket.SHUT_RDWR)
                deadline = time.monotonic() + 6
                while len(connections) < 2 and time.monotonic() < deadline:
                    time.sleep(.03)
                self.assertGreaterEqual(len(connections), 2)
                self.assertTrue(ready.wait(2))
            finally:
                manager.stop.set()
                stop.set()
                device.thread.join(2)
                thread.join(2)

    def test_wire_wakeup_and_coalesced_final_do_not_wait_for_first_ack(self):
        stop = threading.Event()
        initialized, first, final = threading.Event(), threading.Event(), threading.Event()
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        listener.settimeout(.2)
        observed = []
        def lamp():
            connection = None
            try:
                connection, _ = listener.accept()
                connection.settimeout(.2)
                connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                data = b''
                first_id = None
                while not stop.is_set():
                    try:
                        chunk = connection.recv(8192)
                    except socket.timeout:
                        continue
                    if not chunk:
                        break
                    data += chunk
                    while b'\n' in data:
                        line, data = data.split(b'\n', 1)
                        message = json.loads(line)
                        if message['method'] == 'get_prop':
                            connection.sendall(frame(id=message['id'], result=['on','50','4000','16711680','2','0','100']))
                            initialized.set()
                        else:
                            observed.append((message['params'][0], time.monotonic()))
                            if first_id is None:
                                first_id = message['id']
                                first.set()  # Intentionally withhold ACK until final target arrives.
                            else:
                                connection.sendall(frame(id=message['id'], result=['ok']) + frame(id=first_id, result=['ok']))
                                final.set()
            except OSError:
                pass
            finally:
                if connection:
                    connection.close()
        server = threading.Thread(target=lamp, daemon=True)
        server.start()
        with tempfile.TemporaryDirectory() as directory:
            manager = y.Manager(Path(directory) / 'selection.json')
            manager.found(record(listener.getsockname()))
            device = manager.devices['0x1234']
            try:
                self.assertTrue(initialized.wait(2))
                time.sleep(.02)
                started = time.monotonic()
                with manager.lock:
                    device.adjust(5)
                self.assertTrue(first.wait(.2), 'first wheel step waited for a poll/debounce')
                with manager.lock:
                    for _ in range(5):
                        device.adjust(5)
                updated = time.monotonic()
                self.assertTrue(final.wait(.2), 'final wheel target waited for the first ACK')
                self.assertEqual([value for value, _ in observed], [55,80])
                self.assertLess(observed[0][1] - started, .2)
                self.assertLess(observed[1][1] - updated, .2)
                deadline = time.monotonic() + .5
                while device.props.get('bright') != '80' and time.monotonic() < deadline:
                    time.sleep(.005)
                self.assertEqual(device.props['bright'], '80')
            finally:
                manager.stop.set()
                device.wake()
                stop.set()
                device.thread.join(2)
                listener.close()
                server.join(2)

    def test_unix_rpc_roundtrip_and_invalid_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'lamp.sock'
            server = y.Server(str(path), y.Handler)
            server.manager = y.Manager(Path(directory) / 'selection.json')
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with patch.object(y, 'runtime_path', return_value=path):
                    self.assertEqual(y.request('status')['devices'], [])
                    with self.assertRaisesRegex(RuntimeError, 'unknown|찾지'):
                        y.request('bogus')
                with socket.socket(socket.AF_UNIX) as connection:
                    connection.connect(str(path))
                    connection.sendall(b'[]\n')
                    response = json.loads(connection.recv(4096))
                    self.assertFalse(response['ok'])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(2)


if __name__ == '__main__':
    unittest.main()

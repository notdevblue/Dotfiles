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
        self.assertFalse(self.manager.allow_send(self.device, now + .5))
        self.device.sent = deque([now] * 48)
        self.assertFalse(self.manager.allow_send(self.device, now + 2))
        self.device.sent.clear()
        self.manager.sent = deque([now] * 120)
        self.assertFalse(self.manager.allow_send(self.device, now + 2))
        self.assertTrue(self.manager.allow_send(self.device, now + 61))

    def test_error_ack_and_oversized_device_frame(self):
        self.device.inflight[1] = ('set_rgb', [12, 'smooth', 200], 0)
        self.device.process(frame(id=1, error={'code': -1, 'message': 'unsupported'}))
        self.assertEqual(self.device.error, 'unsupported')
        with self.assertRaises(ValueError):
            self.device.process(b'x' * (y.MAX_FRAME + 1))

    def test_tooltip_escapes_device_markup(self):
        self.device.name = '<b>not markup</b>'
        output = y.waybar(self.manager.status())
        self.assertIn('&lt;b&gt;', output['tooltip'])

    def test_hsv_tooltip_uses_hue_and_saturation_instead_of_stale_rgb(self):
        self.device.props.update(color_mode='3', hue='120', sat='100', rgb='16711680')
        self.assertIn('컬러 #00FF00', y.waybar(self.manager.status())['tooltip'])
        self.device.props['color_mode'] = '1'
        self.assertIn('컬러 #FF0000', y.waybar(self.manager.status())['tooltip'])


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

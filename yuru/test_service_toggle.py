"""Service catalog and toggle behavior, with no live systemctl or VPN calls."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    'service_toggle', ROOT / 'templates/waybar/scripts/service-toggle.py')
toggle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(toggle)


def completed(code=0, out='', err=''):
    class Result:
        returncode = code
        stdout = out
        stderr = err
    return Result()


class CatalogTests(unittest.TestCase):
    def catalog(self, extra=None):
        data = json.loads((ROOT / 'templates/waybar/services.json').read_text())
        if extra:
            data['services'].append(extra)
        return data

    def test_installed_catalog_is_three_known_services(self):
        data = self.catalog()
        self.assertEqual([item['id'] for item in data['services']], ['forge', 'chat', 'ppwork'])
        by_id = {item['id']: item for item in data['services']}
        self.assertEqual(by_id['forge']['app'], 'stable-diffusion.service')
        self.assertEqual(by_id['forge']['upstream'], '100.68.74.109:7861')
        self.assertIn('stable-diffusion.service', by_id['forge']['stop'])
        self.assertEqual(by_id['chat']['app'], 'electric.service')
        self.assertEqual(by_id['chat']['upstream'], '100.68.74.109:3000')
        self.assertNotIn('stable-diffusion.service', by_id['chat']['stop'])
        toggle.load_catalog(ROOT / 'templates/waybar/services.json')

    def test_another_service_becomes_another_button(self):
        data = self.catalog({
            'id': 'notes',
            'kind': 'command',
            'status': ['notesctl', 'status'],
            'on': ['notesctl', 'on'],
            'off': ['notesctl', 'off'],
        })
        config = {'group/service-drawer': {'modules': ['group/service-handle']}}
        toggle.apply_catalog(config, data)
        self.assertEqual(config['group/service-drawer']['modules'], [
            'group/service-handle', 'custom/forge', 'custom/chat', 'custom/ppwork', 'custom/notes'])
        self.assertIn('notes', config['custom/notes']['on-click'])
        self.assertEqual(config['custom/forge']['interval'], 30)
        self.assertEqual(config['custom/notes']['interval'], 30)
        self.assertFalse(config['custom/notes']['exec-on-event'])
        self.assertNotIn('tooltip', config['custom/notes'])
        self.assertEqual(config['custom/notes']['signal'], data['signal'])

    def test_rejects_duplicate_unknown_and_unsafe_entries(self):
        path = Path(tempfile.mkdtemp()) / 'services.json'
        base = self.catalog()
        base['services'].append(dict(base['services'][0]))
        path.write_text(json.dumps(base))
        with self.assertRaises(toggle.CatalogError):
            toggle.load_catalog(path)
        base = self.catalog()
        base['services'][0]['kind'] = 'widget'
        path.write_text(json.dumps(base))
        with self.assertRaises(toggle.CatalogError):
            toggle.load_catalog(path)
        base = self.catalog()
        base['services'][0]['id'] = 'forge;rm'
        path.write_text(json.dumps(base))
        with self.assertRaises(toggle.CatalogError):
            toggle.load_catalog(path)
        base = self.catalog()
        base['services'][0]['stop'] = ['ywh-forge.socket', 'ywh-forge.service']
        path.write_text(json.dumps(base))
        with self.assertRaises(toggle.CatalogError):
            toggle.load_catalog(path)
        base = self.catalog()
        base['services'][0]['upstream'] = 'forge.local:7861'
        path.write_text(json.dumps(base))
        with self.assertRaises(toggle.CatalogError):
            toggle.load_catalog(path)


class ToggleTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / 'templates/waybar/services.json').read_text())
        self.services = {item['id']: item for item in self.catalog['services']}
        self.calls = []
        self.probes = []
        self.states = {}
        self.upstream = 'closed'
        self.active = False

        def fake_run(argv):
            self.calls.append(list(argv))
            if argv[:3] == ['systemctl', '--user', 'is-active']:
                state = self.states.get(argv[3], 'inactive')
                if state == 'missing':
                    return completed(4, 'inactive\n')
                return completed(0 if state == 'active' else 3, state + '\n')
            if argv[:2] == ['ppwork', 'status']:
                return completed(0, 'on\n' if self.active else 'off\n')
            if argv[0] == 'pkill':
                return completed(0)
            return completed(0)

        def fake_tcp(upstream):
            self.probes.append(upstream)
            return self.upstream

        runner = patch.object(toggle, 'run', side_effect=fake_run)
        runner.start()
        self.addCleanup(runner.stop)
        probe = patch.object(toggle, 'tcp_status', side_effect=fake_tcp)
        probe.start()
        self.addCleanup(probe.stop)

    def starts(self):
        return [call for call in self.calls if call[:3] == ['systemctl', '--user', 'start']]

    def stops(self):
        return [call for call in self.calls if len(call) > 2 and call[2] == 'stop']

    def test_socket_off_starts_the_app_before_the_socket(self):
        toggle.toggle(self.services['forge'], self.catalog['signal'])
        self.assertEqual(self.starts(), [
            ['systemctl', '--user', 'start', 'stable-diffusion.service'],
            ['systemctl', '--user', 'start', 'ywh-forge.socket'],
        ])
        self.assertEqual(self.stops(), [])
        self.assertEqual(self.calls[-1][0], 'pkill')

    def test_plain_socket_still_starts_only_its_unit(self):
        service = {'id': 'notes', 'kind': 'socket', 'unit': 'notes.socket', 'stop': ['notes.socket']}
        toggle.toggle(service, self.catalog['signal'])
        self.assertEqual(self.starts(), [['systemctl', '--user', 'start', 'notes.socket']])

    def test_ready_socket_stops_the_app_without_disable(self):
        self.states['ywh-webui.socket'] = 'active'
        self.states['electric.service'] = 'active'
        self.upstream = 'open'
        toggle.toggle(self.services['chat'], self.catalog['signal'])
        self.assertEqual(self.stops(), [[
            'systemctl', '--user', 'stop', 'ywh-webui.socket', 'ywh-webui.service', 'electric.service']])
        self.assertNotIn('disable', self.stops()[0])
        self.assertNotIn('stable-diffusion.service', self.stops()[0])

    def test_proxy_without_the_app_is_an_error_and_click_repairs(self):
        self.states['ywh-forge.socket'] = 'active'
        found = toggle.inspect(self.services['forge'])
        body = toggle.payload(self.services['forge'], ready=found['ready'], off=found['off'], lines=found['lines'])
        self.assertEqual(body['class'], ['service', 'error'])
        self.assertEqual(body['tooltip'], '\n'.join([
            '문제: 앱 stable-diffusion.service 꺼짐',
            '소켓 ywh-forge.socket: 켜짐',
            '앱 stable-diffusion.service: 꺼짐',
            '업스트림 100.68.74.109:7861: 연결 거부',
            'http://forge.local',
            'http://192.168.0.3:7861',
        ]))
        self.calls.clear()
        toggle.toggle(self.services['forge'], self.catalog['signal'])
        self.assertEqual(self.starts(), [
            ['systemctl', '--user', 'start', 'stable-diffusion.service'],
            ['systemctl', '--user', 'start', 'ywh-forge.socket'],
        ])
        self.assertEqual(self.stops(), [])

    def test_app_up_before_the_port_listens_stays_an_error(self):
        self.states['ywh-forge.socket'] = 'active'
        self.states['stable-diffusion.service'] = 'active'
        found = toggle.inspect(self.services['forge'])
        body = toggle.payload(self.services['forge'], ready=found['ready'], off=found['off'], lines=found['lines'])
        self.assertEqual(body['class'], ['service', 'error'])
        self.assertIn('문제: 100.68.74.109:7861 아직 연결 안 됨', body['tooltip'])
        self.assertIn('업스트림 100.68.74.109:7861: 아직 연결 안 됨', body['tooltip'])

    def test_socket_down_while_the_app_is_listening_names_the_socket(self):
        self.states['stable-diffusion.service'] = 'active'
        self.upstream = 'open'
        found = toggle.inspect(self.services['forge'])
        body = toggle.payload(self.services['forge'], ready=found['ready'], off=found['off'], lines=found['lines'])
        self.assertEqual(body['class'], ['service', 'error'])
        self.assertIn('문제: 소켓 ywh-forge.socket 꺼짐', body['tooltip'])
        self.assertIn('앱 stable-diffusion.service: 켜짐', body['tooltip'])
        self.assertIn('업스트림 100.68.74.109:7861: 연결됨', body['tooltip'])

    def test_ready_tooltip_lists_the_checks_that_passed(self):
        self.states['ywh-forge.socket'] = 'active'
        self.states['stable-diffusion.service'] = 'active'
        self.upstream = 'open'
        found = toggle.inspect(self.services['forge'])
        body = toggle.payload(self.services['forge'], ready=found['ready'], off=found['off'], lines=found['lines'])
        self.assertEqual(body['class'], ['service', 'on'])
        self.assertEqual(body['tooltip'], '\n'.join([
            '켜짐',
            '소켓 ywh-forge.socket: 켜짐',
            '앱 stable-diffusion.service: 켜짐',
            '업스트림 100.68.74.109:7861: 연결됨',
            'http://forge.local',
            'http://192.168.0.3:7861',
        ]))

    def test_fully_off_tooltip_stays_quiet(self):
        found = toggle.inspect(self.services['forge'])
        body = toggle.payload(self.services['forge'], ready=found['ready'], off=found['off'], lines=found['lines'])
        self.assertEqual(body['class'], ['service'])
        self.assertEqual(body['tooltip'], '꺼짐\nhttp://forge.local\nhttp://192.168.0.3:7861')

    def test_missing_app_unit_is_a_check_failure(self):
        self.states['stable-diffusion.service'] = 'missing'
        with self.assertRaises(RuntimeError) as caught:
            toggle.inspect(self.services['forge'])
        self.assertIn('유닛이 없음', str(caught.exception))

    def test_command_toggle_uses_the_catalog_off_command(self):
        self.active = True
        toggle.toggle(self.services['ppwork'], self.catalog['signal'])
        self.assertEqual(self.calls[1], ['ppwork', 'off'])

    def test_failed_check_keeps_the_name_and_marks_error(self):
        body = toggle.payload(self.services['forge'], error='missing')
        self.assertEqual(body['text'], 'forge')
        self.assertEqual(body['class'], ['service', 'error'])
        self.assertEqual(body['tooltip'],
                         '확인 실패: missing\nhttp://forge.local\nhttp://192.168.0.3:7861')

    def test_tooltip_lists_state_then_where_it_is_reached(self):
        self.assertEqual(toggle.payload(self.services['ppwork'], active=False)['tooltip'],
                         '꺼짐\n회사 VPN')
        self.assertEqual(toggle.payload(self.services['chat'], active=True)['tooltip'].splitlines()[1],
                         'http://chat.local')

    def test_tooltip_escapes_markup(self):
        service = {'id': 'notes', 'detail': ['a&b']}
        self.assertEqual(toggle.tooltip_text(service, active=True), '켜짐\na&amp;b')

    def test_status_json_uses_one_shared_class(self):
        self.assertEqual(toggle.payload(self.services['ppwork'], active=True)['class'], ['service', 'on'])
        self.assertEqual(toggle.payload(self.services['ppwork'], active=False)['class'], ['service'])


class ListenTableTests(unittest.TestCase):
    def test_proc_net_tcp_matches_the_address_and_a_wildcard(self):
        text = """  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode
   0: 6D4A4464:1EB5 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 1 1 0000000000000000 100 0 0 10 0
   1: 0100007F:0BB8 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 2 1 0000000000000000 100 0 0 10 0
   2: 00000000:0050 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 3 1 0000000000000000 100 0 0 10 0
   3: 6D4A4464:0BB8 0100007F:1234 01 00000000:00000000 00:00000000 00000000     0        0 4 1 0000000000000000 100 0 0 10 0
"""
        self.assertTrue(toggle.proc_listening(text, '100.68.74.109', 7861))
        self.assertFalse(toggle.proc_listening(text, '100.68.74.109', 3000))
        self.assertTrue(toggle.proc_listening(text, '127.0.0.1', 3000))
        self.assertTrue(toggle.proc_listening(text, '192.168.0.3', 80))
        self.assertFalse(toggle.proc_listening(text, '10.1.2.3', 3000))


if __name__ == '__main__':
    unittest.main()

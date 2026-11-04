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


class ToggleTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / 'templates/waybar/services.json').read_text())
        self.services = {item['id']: item for item in self.catalog['services']}
        self.calls = []

        def fake_run(argv):
            self.calls.append(list(argv))
            if argv[:3] == ['systemctl', '--user', 'is-active']:
                return completed(0 if self.active else 3)
            if argv[:2] == ['ppwork', 'status']:
                return completed(0, 'on\n' if self.active else 'off\n')
            if argv[0] == 'pkill':
                return completed(0)
            return completed(0)

        self.active = False
        runner = patch.object(toggle, 'run', side_effect=fake_run)
        runner.start()
        self.addCleanup(runner.stop)

    def test_socket_off_starts_only_the_unit(self):
        toggle.toggle(self.services['forge'], self.catalog['signal'])
        self.assertEqual(self.calls[1], ['systemctl', '--user', 'start', 'ywh-forge.socket'])
        self.assertEqual(self.calls[2][0], 'pkill')

    def test_socket_on_stops_the_socket_and_service_without_disable(self):
        self.active = True
        toggle.toggle(self.services['chat'], self.catalog['signal'])
        self.assertEqual(self.calls[1], [
            'systemctl', '--user', 'stop', 'ywh-webui.socket', 'ywh-webui.service'])
        self.assertNotIn('disable', self.calls[1])

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
        forge = self.services['forge']
        on = toggle.payload(forge, active=True)
        off = toggle.payload(forge, active=False)
        self.assertEqual(on['tooltip'], '켜짐\nhttp://forge.local\nhttp://192.168.0.3:7861')
        self.assertEqual(off['tooltip'], '꺼짐\nhttp://forge.local\nhttp://192.168.0.3:7861')
        self.assertEqual(toggle.payload(self.services['chat'], active=True)['tooltip'].splitlines()[1],
                         'http://chat.local')
        self.assertEqual(toggle.payload(self.services['ppwork'], active=False)['tooltip'],
                         '꺼짐\n회사 VPN')

    def test_tooltip_escapes_markup(self):
        service = {'id': 'notes', 'detail': ['a&b']}
        self.assertEqual(toggle.tooltip_text(service, active=True), '켜짐\na&amp;b')

    def test_status_json_uses_one_shared_class(self):
        self.active = True
        self.assertEqual(toggle.payload(self.services['forge'], active=True)['class'], ['service', 'on'])
        self.assertEqual(toggle.payload(self.services['forge'], active=False)['class'], ['service'])


if __name__ == '__main__':
    unittest.main()

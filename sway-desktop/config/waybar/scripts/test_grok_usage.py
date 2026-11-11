"""Exercise quota and ACP refresh without real credentials or network."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import urllib.error

spec = importlib.util.spec_from_file_location('grok_usage', Path(__file__).with_name('grok-usage.py'))
grok = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grok)


class AuthRefreshTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.auth = self.home / 'auth.json'
        self.old = {'auth_mode': 'oidc', 'key': 'expired-test-token',
                    'expires_at': '2000-01-01T00:00:00Z'}
        self.auth.write_text(json.dumps({'https://auth.x.ai::test': self.old}))
        self.cli = self.home / '.local/bin/grok'
        self.cli.parent.mkdir(parents=True)
        for name, value in [('AUTH', self.auth), ('REFRESH_TIMEOUT', 1),
                            ('REFRESH_EXIT_TIMEOUT', 0.1)]:
            override = patch.object(grok, name, value)
            override.start()
            self.addCleanup(override.stop)
        home = patch.object(grok.Path, 'home', return_value=self.home)
        home.start()
        self.addCleanup(home.stop)

    def agent(self, action):
        self.cli.write_text('''#!/usr/bin/python3
import json, os, pathlib, select, sys, time
home = pathlib.Path(__file__).parents[2]
(home / 'pid').write_text(str(os.getpid()))
request = json.loads(sys.stdin.readline())
assert request['method'] == 'initialize'
assert sys.argv[1:] == ['agent', '--no-leader', 'stdio']
# Model async OIDC refresh: receiving EOF during this wait cancels it.
if select.select([sys.stdin], [], [], 0.08)[0]:
    assert sys.stdin.read() == ''
    sys.exit(0)
''' + action)
        self.cli.chmod(0o700)

    def assert_reaped(self):
        pid = int((self.home / 'pid').read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_delayed_refresh_keeps_input_open_and_retries_with_new_token(self):
        self.agent('''
auth = {'auth_mode':'oidc', 'key':'renewed-test-token', 'expires_at':'2099-01-01T00:00:00Z'}
(home / 'auth.json').write_text(json.dumps({'https://auth.x.ai::test':auth}))
print(json.dumps({'jsonrpc':'2.0', 'method':'notification'}), flush=True)
response = json.dumps({'jsonrpc':'2.0', 'id':1, 'result':{}}) + '\\n'
sys.stdout.write(response[:10]); sys.stdout.flush()
time.sleep(0.02)
sys.stdout.write(response[10:]); sys.stdout.flush()
assert sys.stdin.read() == ''
''')
        config = {'creditUsagePercent': 25, 'currentPeriod': {
            'type': 'USAGE_PERIOD_TYPE_WEEKLY', 'end': '2099-01-01T00:00:00Z'}}
        with patch.object(grok, 'request_billing', return_value={'config': config}) as billing:
            result = grok.fetch_quota()
        billing.assert_called_once_with('renewed-test-token')
        self.assertEqual(result['remaining'], 75)
        self.assert_reaped()

    def test_early_zero_exit_is_not_success(self):
        self.agent('sys.exit(0)\n')
        with self.assertRaises(grok.Unavailable):
            grok.refresh_auth()
        self.assert_reaped()

    def test_initialize_error_is_not_success(self):
        self.agent("print(json.dumps({'id':1, 'error':{'code':-1}}), flush=True)\nsys.stdin.read()\n")
        with self.assertRaises(grok.Unavailable):
            grok.refresh_auth()
        self.assert_reaped()

    def test_success_response_with_expired_auth_is_rejected(self):
        self.agent("print(json.dumps({'id':1, 'result':{}}), flush=True)\nsys.stdin.read()\n")
        with self.assertRaises(grok.Unavailable):
            grok.refresh_auth()
        self.assert_reaped()

    def test_partial_line_timeout_kills_and_reaps_unresponsive_agent(self):
        self.agent("sys.stdout.write('{'); sys.stdout.flush()\ntime.sleep(60)\n")
        start = time.monotonic()
        with patch.object(grok, 'REFRESH_TIMEOUT', 0.2), self.assertRaises(grok.Unavailable):
            grok.refresh_auth()
        self.assertLess(time.monotonic() - start, 2)
        self.assert_reaped()

    def test_401_refresh_retries_once(self):
        valid = dict(self.old, key='revoked-test-token', expires_at='2099-01-01T00:00:00Z')
        renewed = dict(valid, key='renewed-test-token')
        error = urllib.error.HTTPError(grok.BILLING_URL, 401, 'Unauthorized', {}, None)
        self.addCleanup(error.close)
        with patch.object(grok, 'credential', return_value=valid), \
             patch.object(grok, 'refresh_auth', return_value=renewed) as refresh, \
             patch.object(grok, 'request_billing', side_effect=[error, error]) as billing:
            with self.assertRaises(grok.Unavailable):
                grok.fetch_quota()
        refresh.assert_called_once_with()
        self.assertEqual([call.args[0] for call in billing.call_args_list],
                         ['revoked-test-token', 'renewed-test-token'])


class QuotaFallbackTests(unittest.TestCase):
    def setUp(self):
        self.config = {'currentPeriod': {'type': 'USAGE_PERIOD_TYPE_WEEKLY',
                                        'end': '2099-11-07T02:24:13Z'}}
        auth = {'key': 'test-token', 'expires_at': '2099-11-07T02:24:13Z'}
        credential = patch.object(grok, 'credential', return_value=auth)
        credential.start()
        self.addCleanup(credential.stop)

    def fetch(self, config, fallback=23):
        with patch.object(grok, 'request_billing', return_value={'config': config}), \
             patch.object(grok, 'codexbar_percent', return_value=fallback) as supplement:
            return grok.fetch_quota(), supplement.call_count

    def test_missing_percentage_uses_collector_and_preserves_proxy_reset(self):
        result, calls = self.fetch(self.config)
        self.assertEqual(result['remaining'], 77)
        self.assertEqual(result['resets_at'], grok.timestamp(self.config['currentPeriod']['end']))
        self.assertEqual(calls, 1)
        self.assertNotIn('creditUsagePercent', self.config)

    def test_published_zero_does_not_invoke_fallback(self):
        result, calls = self.fetch(dict(self.config, creditUsagePercent=0))
        self.assertEqual(result['remaining'], 100)
        self.assertEqual(calls, 0)

    def test_fallback_failure_does_not_invent_full_quota(self):
        with patch.object(grok, 'request_billing', return_value={'config': self.config}), \
             patch.object(grok, 'codexbar_percent', side_effect=grok.Unavailable('unavailable')):
            with self.assertRaises(grok.Unavailable):
                grok.fetch_quota()

    def test_invalid_published_percentage_is_rejected(self):
        for value in (None, True, -1, 101, float('nan')):
            with self.subTest(value=value), self.assertRaises(grok.Unavailable):
                self.fetch(dict(self.config, creditUsagePercent=value))

    def test_unknown_or_expired_period_is_still_rejected_after_fallback(self):
        for period in ({}, {'type': 'USAGE_PERIOD_TYPE_WEEKLY', 'end': '2000-01-01T00:00:00Z'}):
            with self.subTest(period=period), self.assertRaises(grok.Unavailable):
                self.fetch({'currentPeriod': period})


if __name__ == '__main__':
    unittest.main()

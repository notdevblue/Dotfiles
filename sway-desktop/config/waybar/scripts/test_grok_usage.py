"""Exercise the missing-percentage fallback without credentials or network."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('grok_usage', Path(__file__).with_name('grok-usage.py'))
grok = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grok)


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

"""Validate untrusted quota payloads and process cleanup without a network/login."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location('yuru_usage', Path(__file__).parent / 'templates/monitor/usage.py')
usage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usage)


class UsageTests(unittest.TestCase):
    def payload(self, percent=11):
        return [{'provider': 'codex', 'rateWindowLabels': {'secondary': 'Weekly'}, 'usage': {
            'primary': None, 'secondary': {'usedPercent': percent, 'windowMinutes': 10080,
                                         'resetsAt': '2026-11-07T01:00:00Z'},
            'updatedAt': '2026-10-31T07:00:00Z', 'accountEmail': 'private@example.test'}}]

    def test_missing_primary_does_not_invent_a_short_term_window(self):
        result = usage.normalize(self.payload(), 'codex')
        self.assertEqual(len(result['windows']), 1)
        self.assertEqual(result['windows'][0]['label'], 'weekly')
        self.assertEqual(result['windows'][0]['remaining'], 89)
        self.assertNotIn('private', str(result))

    def test_zero_and_missing_usage_remain_distinct(self):
        self.assertEqual(usage.normalize(self.payload(0), 'codex')['windows'][0]['remaining'], 100)
        self.assertEqual(usage.normalize(self.payload(None), 'codex')['windows'], [])

    def test_bad_percentages_are_rejected(self):
        for value in [-1, 101, float('nan'), float('inf')]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                usage.normalize(self.payload(value), 'codex')

    def test_other_provider_or_duplicate_accounts_are_not_substituted(self):
        for payload in [self.payload(), self.payload() * 2, {'usage': {}}]:
            with self.assertRaises(ValueError):
                usage.normalize(payload, 'grok' if len(payload) == 1 else 'codex')

    def test_reported_errors_do_not_become_empty_successes(self):
        payload = self.payload()
        payload[0]['error'] = {'message': 'private provider error'}
        with self.assertRaises(ValueError):
            usage.normalize(payload, 'codex')

    def test_unknown_reset_does_not_become_reset_now(self):
        self.assertEqual(usage.reset_text(None, now=100), 'reset unavailable')
        self.assertEqual(usage.reset_text(99, now=100), 'reset due; refresh to confirm')
        self.assertEqual(usage.reset_text(3700, now=100), 'resets in 1h 0m')
        self.assertIsNone(usage.timestamp('2026-11-07T01:00:00'))

    def test_timeout_kills_owned_process_group_and_reaps_child(self):
        process = MagicMock(pid=12345)
        process.communicate.side_effect = [subprocess.TimeoutExpired('codexbar', 40), ('', '')]
        with patch.object(usage.shutil, 'which', return_value='/fake/codexbar'), \
             patch.object(usage.subprocess, 'Popen', return_value=process), \
             patch.object(usage.os, 'killpg') as kill:
            fetcher = usage.Fetcher()
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                fetcher.fetch('codex')
            kill.assert_called_once()
            self.assertEqual(process.communicate.call_count, 2)
            self.assertFalse(fetcher.processes)


if __name__ == '__main__':
    unittest.main()

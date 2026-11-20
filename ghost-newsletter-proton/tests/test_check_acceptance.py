"""Local synthetic tests for the acceptance helper. No network and no mail."""
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import re
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'check_acceptance.py'


def load_helper():
    spec = importlib.util.spec_from_file_location('check_acceptance', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ca = load_helper()


def event(recipient, subject, kind, **extra):
    item = {'recipient': recipient, 'event': kind,
            'message': {'headers': {'subject': subject}}}
    item.update(extra)
    return item


def page(items, paging=None):
    return {'items': items, 'paging': {} if paging is None else paging}


class FakeClock:
    def __init__(self, start=1_000.0, wall=1_700_000_000):
        self.value = start
        self.wall = wall
        self.sleeps = []

    def monotonic(self):
        return self.value

    def time(self):
        return self.wall

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.value += seconds


class RecordingFetcher:
    def __init__(self, pages, *, status=b'200'):
        self.pages = list(pages)
        self.status = status
        self.urls = []
        self.commands = []

    def __call__(self, url, target, remaining):
        self.urls.append(url)
        Path(target).write_text(json.dumps(self.pages.pop(0) if self.pages else page([])),
                                encoding='utf-8')

    def runner(self, args, **kwargs):
        self.commands.append(list(args))
        if args[0] == 'curl':
            raise AssertionError('tests must not invoke real curl')
        raise AssertionError(f'unexpected command {args[0]}')


class GuardedRunner:
    def __call__(self, args, **kwargs):
        raise AssertionError(f'real subprocess invoked: {args[:3]}')


class AcceptanceHelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.base = 'https://mg.example.com/v3/example.com/events'
        self.to = 'allowed@example.test'
        self.subject = 'this-test'

    def write_send(self, body, status=b'200'):
        (self.root / 'send-status.private').write_bytes(status)
        (self.root / 'send-response.private.json').write_text(
            body if isinstance(body, str) else json.dumps(body), encoding='utf-8')

    def poll(self, pages, **kwargs):
        clock = kwargs.pop('clock', FakeClock())
        fetcher = pages if callable(pages) else RecordingFetcher(pages)
        with mock.patch.object(ca.subprocess, 'run', GuardedRunner()):
            code = ca.poll(
                self.base, self.to, self.subject, '1700000000',
                directory=self.root, fetch_page=fetcher,
                monotonic=clock.monotonic, now=clock.time, sleep=clock.sleep,
                time_limit=kwargs.pop('time_limit', 30),
                max_pages=kwargs.pop('max_pages', 20),
            )
        return code, fetcher, clock

    def test_queued_success_writes_id_once(self):
        self.write_send({'id': 'message-id', 'message': 'Queued'})
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            self.assertEqual(ca.queued(self.root), 0)
        self.assertEqual(out.getvalue(), '{"queued":1}\n')
        self.assertEqual((self.root / 'queued-id.private').read_text(), 'message-id')

    def test_queued_accepts_non_literal_batch_id(self):
        batch_id = 'batch-nr-1.example.test'
        self.write_send({'id': batch_id, 'message': 'Queued. Thank you.'})
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            self.assertEqual(ca.queued(self.root), 0)
        self.assertEqual(out.getvalue(), '{"queued":1}\n')
        self.assertEqual((self.root / 'queued-id.private').read_text(), batch_id)
        self.assertNotEqual(batch_id, 'message-id')


    def test_queued_non_200_does_not_write_id(self):
        self.write_send({'id': 'message-id'}, status=b'204')
        with self.assertRaises(ca.Invalid):
            ca.queued(self.root)
        self.assertFalse((self.root / 'queued-id.private').exists())

    def test_queued_redirect_with_id_is_rejected(self):
        self.write_send({'id': 'message-id'}, status=b'302')
        with self.assertRaises(ca.Invalid):
            ca.queued(self.root)
        self.assertFalse((self.root / 'queued-id.private').exists())

    def test_queued_missing_id_does_not_write_evidence(self):
        self.write_send({'message': 'Unexpected'})
        with self.assertRaises(ca.Invalid):
            ca.queued(self.root)
        self.assertFalse((self.root / 'queued-id.private').exists())

    def test_queued_refuses_to_overwrite_existing_id(self):
        self.write_send({'id': 'message-id'})
        (self.root / 'queued-id.private').write_text('already')
        with self.assertRaises(OSError):
            ca.queued(self.root)
        self.assertEqual((self.root / 'queued-id.private').read_text(), 'already')

    def test_cli_queued_in_temp_directory(self):
        self.write_send({'id': 'message-id'})
        result = subprocess.run(
            [sys.executable, str(SCRIPT), 'queued'], cwd=self.root,
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {'queued': 1})

    def test_cli_usage_exit_code(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)], cwd=self.root,
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn('Usage:', result.stderr)

    def test_poll_success_exactly_one_accepted(self):
        pages = [page([event(self.to, self.subject, 'accepted')])]
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            code, fetcher, _ = self.poll(pages)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue()),
                         {'matched': 1, 'accepted': 1, 'failed': 0, 'unknown': 0})
        self.assertEqual(len(fetcher.urls), 1)
        self.assertTrue(fetcher.urls[0].startswith(self.base + '?'))

    def test_poll_matches_unique_subject_when_stored_ids_differ(self):
        item = event(self.to, self.subject, 'accepted')
        item['message']['headers']['message-id'] = 'AbCdEfGhIjKlMnOpqrs'
        item['id'] = 'batch-nr-1.example.test'
        pages = [page([item])]
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            code, _, _ = self.poll(pages)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())['accepted'], 1)
        self.assertNotEqual(item['id'], item['message']['headers']['message-id'])
        self.assertEqual(len(item['message']['headers']['message-id']), 19)


    def test_poll_failed_event_exits_one(self):
        pages = [page([event(self.to, self.subject, 'failed')])]
        with mock.patch('sys.stdout', new=io.StringIO()):
            code, _, _ = self.poll(pages)
        self.assertEqual(code, 1)

    def test_poll_unknown_event_name_exits_one(self):
        pages = [page([event(self.to, self.subject, 'delivered')])]
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            code, _, _ = self.poll(pages)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out.getvalue())['unknown'], 1)

    def test_unrelated_events_are_not_handoff(self):
        pages = [page([
            event('other@example.test', self.subject, 'accepted'),
            event(self.to, 'other-test', 'accepted'),
            event(self.to, self.subject, 'failed'),
        ])]
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            code, _, _ = self.poll(pages)
        self.assertEqual(code, 1)
        counts = json.loads(out.getvalue())
        self.assertEqual(counts, {'matched': 1, 'accepted': 0, 'failed': 1, 'unknown': 0})
        self.assertNotIn('@', out.getvalue())
        saved = json.loads(next(self.root.glob('poll-*/matched-events.private.json')).read_text())
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]['event'], 'failed')

    def test_zero_matches_at_deadline_exit_two_and_do_not_post(self):
        clock = FakeClock()
        fetcher = RecordingFetcher([page([]), page([])])

        def expire_after_first(*_args, **_kwargs):
            clock.value += 100
            return 0

        clock.sleep = expire_after_first
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            with mock.patch.object(ca.subprocess, 'run', GuardedRunner()):
                code = ca.poll(
                    self.base, self.to, self.subject, '1700000000',
                    directory=self.root, fetch_page=fetcher,
                    monotonic=clock.monotonic, now=clock.time, sleep=clock.sleep,
                    time_limit=5,
                )
        self.assertEqual(code, 2)
        self.assertIn('Pending: no correlated handoff.', out.getvalue())
        self.assertTrue(all(url.startswith('https://') and '/events' in url for url in fetcher.urls))
        self.assertFalse(any('POST' in url for url in fetcher.urls))

    def test_duplicate_accepted_exits_one(self):
        pages = [page([
            event(self.to, self.subject, 'accepted'),
            event(self.to, self.subject, 'accepted'),
        ])]
        with mock.patch('sys.stdout', new=io.StringIO()) as out:
            code, _, _ = self.poll(pages)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out.getvalue())['accepted'], 2)

    def test_query_cursor_pagination(self):
        first = page(
            [event('other@example.test', self.subject, 'accepted')],
            {'next': self.base + '?page=2&to=allowed@example.test&begin=1700000000&end=1700000000&limit=300'},
        )
        second = page([event(self.to, self.subject, 'accepted')])
        with mock.patch('sys.stdout', new=io.StringIO()):
            code, fetcher, _ = self.poll([first, second])
        self.assertEqual(code, 0)
        self.assertEqual(len(fetcher.urls), 2)
        self.assertIn('page=2', fetcher.urls[1])

    def test_path_cursor_pagination(self):
        first = page(
            [],
            {'next': self.base + '/MQ==?to=allowed@example.test&begin=1700000000&end=1700000000&limit=300'},
        )
        second = page([event(self.to, self.subject, 'accepted')])
        with mock.patch('sys.stdout', new=io.StringIO()):
            code, fetcher, _ = self.poll([first, second])
        self.assertEqual(code, 0)
        self.assertTrue(fetcher.urls[1].startswith(self.base + '/MQ==?'))

    def test_repeated_cursor_is_invalid(self):
        loop = self.base + '?cursor=abc&to=allowed@example.test&begin=1700000000&end=1700000000&limit=300'
        pages = [page([], {'next': loop}), page([], {'next': loop})]
        with mock.patch('sys.stdout', new=io.StringIO()):
            with self.assertRaises(ca.Invalid) as raised:
                self.poll(pages)
        self.assertIn('repeated', str(raised.exception).lower())

    def test_changed_filter_in_next_link_is_invalid(self):
        bad = page([], {'next': self.base + '?page=2&to=other@example.test'})
        with mock.patch('sys.stdout', new=io.StringIO()):
            with self.assertRaises(ca.Invalid):
                self.poll([bad])

    def test_path_cursor_rejects_slash(self):
        with self.assertRaises(ca.Invalid):
            ca.page_cursor(self.base + '/ab/cd', self.base, {'to': self.to})

    def test_first_page_link_may_omit_cursor(self):
        payload = page(
            [event(self.to, self.subject, 'accepted')],
            {'first': self.base + '?to=allowed@example.test&begin=1700000000&end=1700000000&limit=300'},
        )
        path = self.root / 'events.private.json'
        path.write_text(json.dumps(payload), encoding='utf-8')
        scope = {'to': self.to, 'begin': '1700000000', 'end': '1700000000', 'limit': '300'}
        matched, cursor = ca.read_page(path, self.base, scope, self.subject)
        self.assertEqual(len(matched), 1)
        self.assertIsNone(cursor)

    def test_page_limit_reached(self):
        nxt = self.base + '?page=2&to=allowed@example.test&begin=1700000000&end=1700000000&limit=300'
        fetcher = RecordingFetcher([page([], {'next': nxt}), page([], {'next': self.base + '?page=3&to=allowed@example.test&begin=1700000000&end=1700000000&limit=300'})])
        with mock.patch('sys.stdout', new=io.StringIO()):
            with self.assertRaises(ca.Invalid) as raised:
                self.poll(fetcher, max_pages=1)
        self.assertIn('page limit', str(raised.exception).lower())

    def test_missing_subject_field_is_invalid(self):
        payload = page([{
            'recipient': self.to,
            'event': 'accepted',
            'message': {'headers': {}},
        }])
        path = self.root / 'events.private.json'
        path.write_text(json.dumps(payload), encoding='utf-8')
        with self.assertRaises(ca.Invalid) as raised:
            ca.read_page(path, self.base, {'to': self.to}, self.subject)
        self.assertIn('subject', str(raised.exception).lower())

    def test_malformed_json_is_invalid(self):
        path = self.root / 'events.private.json'
        path.write_text('{', encoding='utf-8')
        with self.assertRaises((ca.Invalid, ValueError)):
            ca.read_page(path, self.base, {'to': self.to}, self.subject)

    def test_duplicate_json_keys_are_invalid(self):
        path = self.root / 'events.private.json'
        path.write_text('{"items": [], "items": [], "paging": {}}', encoding='utf-8')
        with self.assertRaises(ca.Invalid):
            ca.read_page(path, self.base, {'to': self.to}, self.subject)

    def test_non_finite_json_constant_is_invalid(self):
        path = self.root / 'events.private.json'
        path.write_text('{"items": [NaN], "paging": {}}', encoding='utf-8')
        with self.assertRaises(ca.Invalid):
            ca.load(path)

    def test_http_redirect_status_is_invalid(self):
        def runner(args, **kwargs):
            if args[0] != 'curl':
                raise AssertionError('unexpected command')
            output = Path(args[args.index('--output') + 1])
            output.write_text(json.dumps(page([event(self.to, self.subject, 'accepted')])),
                              encoding='utf-8')
            return SimpleNamespace(returncode=0, stdout=b'302')

        with self.assertRaises(ca.Invalid) as raised:
            ca.fetch(self.base + '?limit=300', self.root / 'page.json', 10, runner=runner)
        self.assertIn('redirect', str(raised.exception).lower())

    def test_fetch_timeout_is_invalid(self):
        def runner(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd='curl', timeout=1)

        with self.assertRaises(ca.Invalid) as raised:
            ca.fetch(self.base, self.root / 'page.json', 1, runner=runner)
        self.assertIn('timed out', str(raised.exception).lower())

    def test_fetch_curl_exit_28_is_timeout(self):
        def runner(*_args, **_kwargs):
            return SimpleNamespace(returncode=28, stdout=b'')

        with self.assertRaises(ca.Invalid) as raised:
            ca.fetch(self.base, self.root / 'page.json', 5, runner=runner)
        self.assertIn('timed out', str(raised.exception).lower())

    def test_unsafe_urls_are_rejected(self):
        cases = [
            'http://mg.example.com/v3/example.com/events',
            'https://api:secret@mg.example.com/v3/example.com/events',
            'https://mg.example.com/v3/example.com/events#frag',
            'https://mg.example.com/v3/example.com/events path',
        ]
        for url in cases:
            with self.subTest(url=url):
                with self.assertRaises(ca.Invalid):
                    ca.endpoint(url)

    def test_poll_rejects_non_https_base(self):
        with self.assertRaises(ca.Invalid):
            ca.poll('http://mg.example.com/v3/example.com/events',
                    self.to, self.subject, '1700000000',
                    directory=self.root, fetch_page=RecordingFetcher([]),
                    time_limit=1)

    def test_pagination_http_link_is_rejected(self):
        with self.assertRaises(ca.Invalid):
            ca.page_cursor('http://mg.example.com/v3/example.com/events?page=2',
                           self.base, {'to': self.to})

    def test_curl_command_is_get_only_and_https_only(self):
        args = ca.curl_command(self.base + '?limit=300', self.root / 'out.json', 12)
        self.assertEqual(args[0], 'curl')
        self.assertIn('--proto', args)
        self.assertIn('=https', args)
        self.assertIn('--max-redirs', args)
        self.assertEqual(args[args.index('--max-redirs') + 1], '0')
        self.assertNotIn('-X', args)
        self.assertNotIn('POST', args)
        self.assertNotIn('--location', args)
        self.assertNotIn('-L', args)

    def test_fetch_default_path_cannot_call_real_curl(self):
        with mock.patch.object(ca.subprocess, 'run', GuardedRunner()):
            with self.assertRaises(AssertionError) as raised:
                ca.fetch(self.base, self.root / 'out.json', 5)
        self.assertIn('real subprocess', str(raised.exception))

    def test_poll_exit_codes(self):
        self.assertEqual(ca.poll_exit_code({'accepted': 1, 'failed': 0, 'unknown': 0}), 0)
        self.assertEqual(ca.poll_exit_code({'accepted': 0, 'failed': 1, 'unknown': 0}), 1)
        self.assertEqual(ca.poll_exit_code({'accepted': 0, 'failed': 0, 'unknown': 1}), 1)
        self.assertEqual(ca.poll_exit_code({'accepted': 2, 'failed': 0, 'unknown': 0}), 1)
        self.assertIsNone(ca.poll_exit_code({'accepted': 0, 'failed': 0, 'unknown': 0}))

    def test_main_poll_invalid_url_is_exit_one(self):
        with mock.patch.object(ca.subprocess, 'run', GuardedRunner()):
            with mock.patch('sys.stderr', new=io.StringIO()) as err:
                code = ca.main(['poll', 'http://example.test/events', 'r', 's', '1'])
        self.assertEqual(code, 1)
        self.assertIn('Acceptance check incomplete.', err.getvalue())

    def test_cli_queued_missing_files_exit_one(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), 'queued'], cwd=self.root,
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn('Acceptance check incomplete.', result.stderr)

    def test_query_cursor_filters_are_preserved_on_first_request(self):
        fetcher = RecordingFetcher([page([event(self.to, self.subject, 'accepted')])])
        clock = FakeClock()
        with mock.patch('sys.stdout', new=io.StringIO()):
            with mock.patch.object(ca.subprocess, 'run', GuardedRunner()):
                ca.poll(self.base, self.to, self.subject, '1700000000',
                        directory=self.root, fetch_page=fetcher,
                        monotonic=clock.monotonic, now=clock.time, sleep=clock.sleep,
                        time_limit=5)
        query = parse_qs(urlsplit(fetcher.urls[0]).query, keep_blank_values=True)
        self.assertEqual(query['to'], [self.to])
        self.assertEqual(query['begin'], ['1700000000'])
        self.assertEqual(query['limit'], ['300'])
        self.assertNotIn('page', query)
        self.assertNotIn('cursor', query)


CURRENT_DOCS = (
    ROOT / 'SKILL.md',
    ROOT / 'references' / 'address-policy.md',
    ROOT / 'references' / 'checklist.md',
    ROOT / 'references' / 'deployment.md',
    ROOT / 'references' / 'operations.md',
    ROOT / 'references' / 'smtp-capture-template.md',
    ROOT / 'references' / 'upstream.md',
    ROOT / 'tests' / 'scenarios.md',
)
CHANGELOG = ROOT / 'CHANGELOG-zh.md'
FIX = 'e31299823886f4db9d026054632907924eb02d49'
MERGE = '391256f764979101c4c23b4a410a7de4d3183115'
TREE = '779b7f9a59d9474942bb78739901695396f9b81a'
FAIL_DIGEST = (
    'ghcr.io/eznix86/mailgun-proxy-for-ghost@sha256:'
    'd3fbcd4f209ec27dbce81f8ff013ae8d09b833bbe5ac72715706b39fc575e33c'
)
BRIDGE_DIGEST = (
    'shenxn/protonmail-bridge@sha256:'
    '3717b4441130675dc9131196de9f9c5287d2ea21b138d83b0486429e1737638a'
)
UPSTREAM_REV = 'fb35a74000fe70e7d49f46cae3c895674571ea20'
PROXY_FORK = 'https://github.com/YE4IM/mailgun-proxy-for-ghost'
BRIDGE_UPSTREAM = 'https://github.com/shenxn/protonmail-bridge-docker'
BRIDGE_FORK_HISTORICAL = 'https://github.com/YE4IM/protonmail-bridge-docker'
HISTORICAL_UNMERGED = (
    'historically unmerged',
    'historically unmerged on 2026-11-19',
)


def _read(path):
    return path.read_text(encoding='utf-8')


def _changelog_sections():
    text = _read(CHANGELOG)
    v6_marker = '# ghost-newsletter-proton v6 改动说明'
    v5_marker = '# ghost-newsletter-proton v5 改动说明'
    v4_marker = '# ghost-newsletter-proton v4 改动说明'
    if not text.startswith(v6_marker):
        raise AssertionError('v6 changelog section is missing at the top')
    if v5_marker not in text:
        raise AssertionError('v5 historical changelog section is missing')
    if v4_marker not in text:
        raise AssertionError('v4 historical changelog section is missing')
    before_v5, rest = text.split(v5_marker, 1)
    v5_part, v4_part = rest.split(v4_marker, 1)
    return before_v5, v5_marker + v5_part, v4_marker + v4_part


class SkillPackPolicyTests(unittest.TestCase):
    """Offline regressions for merged-PR status and source/image address policy."""

    def test_current_docs_record_pr_merged(self):
        needed = {
            ROOT / 'SKILL.md',
            ROOT / 'references' / 'address-policy.md',
            ROOT / 'references' / 'deployment.md',
            ROOT / 'references' / 'upstream.md',
            ROOT / 'references' / 'checklist.md',
            ROOT / 'tests' / 'scenarios.md',
        }
        for path in needed:
            text = _read(path)
            self.assertIn(MERGE, text, path.name)
            self.assertIn('merged', text.lower(), path.name)
            self.assertIn('2026-11-20', text, path.name)
            self.assertIn('Asia/Shanghai', text, path.name)

    def test_current_docs_do_not_state_pr_still_unmerged(self):
        forbidden = (
            'unmerged as of 2026-11-19',
            'pull request is unmerged',
            'PR #1], unmerged',
            'PR #1, unmerged',
            '尚未合并',
        )
        for path in CURRENT_DOCS:
            text = _read(path)
            lowered = text.lower()
            for phrase in forbidden:
                self.assertNotIn(phrase, text if any(ord(c) > 127 for c in phrase) else lowered,
                                 f'{path}: stale current-status phrase {phrase!r}')
            # Bare "unmerged" is allowed only as clearly historical wording.
            for idx in range(len(lowered)):
                if not lowered.startswith('unmerged', idx):
                    continue
                window = lowered[max(0, idx - 40):idx + 40]
                self.assertTrue(
                    any(hist in window for hist in HISTORICAL_UNMERGED),
                    f'{path} uses unmerged without a historical qualifier: {window!r}',
                )

    def test_verified_commit_is_distinct_from_merge(self):
        skill = _read(ROOT / 'SKILL.md')
        upstream = _read(ROOT / 'references' / 'upstream.md')
        policy = _read(ROOT / 'references' / 'address-policy.md')
        deployment = _read(ROOT / 'references' / 'deployment.md')
        for text in (skill, upstream, policy, deployment):
            self.assertIn(FIX, text)
            self.assertIn(MERGE, text)
            self.assertIn(TREE, text)
        self.assertIn(f'build of `{FIX}`', skill)
        self.assertIn('The merge commit was not separately', skill)
        self.assertIn('the isolated preview and capture', deployment.lower())
        self.assertNotIn(f'build of `{MERGE}` passed', skill.lower())
        self.assertNotIn(f'build of {MERGE} passed', skill.lower())
        self.assertNotIn('merge commit passed native preview', skill.lower())
        archive = (
            'https://github.com/YE4IM/mailgun-proxy-for-ghost/archive/'
            f'{FIX}.tar.gz'
        )
        self.assertIn(archive, deployment)
        self.assertNotIn(
            f'https://github.com/YE4IM/mailgun-proxy-for-ghost/archive/{MERGE}.tar.gz',
            deployment,
        )

    def test_default_source_entries_follow_maintenance_policy(self):
        skill = _read(ROOT / 'SKILL.md')
        policy = _read(ROOT / 'references' / 'address-policy.md')
        deployment = _read(ROOT / 'references' / 'deployment.md')
        checklist = _read(ROOT / 'references' / 'checklist.md')
        upstream = _read(ROOT / 'references' / 'upstream.md')
        for text in (skill, policy, checklist, upstream):
            self.assertIn(PROXY_FORK, text)
            self.assertIn(BRIDGE_UPSTREAM, text)
        self.assertIn(BRIDGE_UPSTREAM, deployment)
        self.assertIn('Message-Id-fixed proxy', skill)
        current = '\n'.join(_read(path) for path in CURRENT_DOCS)
        self.assertNotIn('git clone https://github.com/eznix86/', current)
        self.assertNotIn('git clone https://github.com/shenxn/', current)
        self.assertNotIn(
            'https://github.com/eznix86/mailgun-proxy-for-ghost/archive/',
            current,
        )

    def test_current_docs_do_not_default_bridge_to_ye4im_fork(self):
        for path in CURRENT_DOCS:
            text = _read(path)
            self.assertNotIn('YE4IM/protonmail-bridge-docker', text, path.name)
            self.assertNotIn('YE4IM Bridge fork', text, path.name)
        v6, v5, _v4 = _changelog_sections()
        self.assertIn(BRIDGE_UPSTREAM, v6)
        self.assertIn('恢复', v6)
        self.assertIn('YE4IM/protonmail-bridge-docker', v5)

    def test_default_proxy_image_is_local_verified_tag(self):
        deployment = _read(ROOT / 'references' / 'deployment.md')
        self.assertIn(
            'PROXY_IMAGE=mailgun-proxy-for-ghost:ghost-message-id-e312998',
            deployment,
        )
        self.assertNotIn(
            'PROXY_IMAGE=ghcr.io/eznix86/mailgun-proxy-for-ghost',
            deployment,
        )
        skill = _read(ROOT / 'SKILL.md')
        upstream = _read(ROOT / 'references' / 'upstream.md')
        self.assertIn(FAIL_DIGEST, skill)
        self.assertIn(FAIL_DIGEST, upstream)
        self.assertIn('known native-preview failure', skill.lower() + ' failed native preview')
        self.assertIn(FAIL_DIGEST, skill)

    def test_does_not_invent_unpublished_ye4im_images(self):
        files = list(CURRENT_DOCS) + [CHANGELOG]
        for path in files:
            text = _read(path)
            lowered = text.lower()
            invented = re.compile(
                r'ghcr\.io/ye4im/|docker\.io/ye4im/|'
                r'ye4im/protonmail-bridge(?!-docker)|'
                r'ye4im/mailgun-proxy-for-ghost@',
                re.I,
            )
            for match in invented.finditer(text):
                window = lowered[max(0, match.start() - 160):match.end() + 220]
                denied = any(token in window for token in (
                    'do not invent',
                    'not invent',
                    'none as of',
                    'no ye4im',
                    'not published',
                    'would publish',
                    '不把',
                    '不杜撰',
                    '不发明',
                ))
                self.assertTrue(
                    denied,
                    f'{path} mentions {match.group(0)!r} without a publication denial: {window!r}',
                )

    def test_retains_upstream_evidence_and_bridge_publisher_image(self):
        upstream = _read(ROOT / 'references' / 'upstream.md')
        policy = _read(ROOT / 'references' / 'address-policy.md')
        deployment = _read(ROOT / 'references' / 'deployment.md')
        self.assertIn(BRIDGE_DIGEST, upstream)
        self.assertIn(BRIDGE_DIGEST, policy)
        self.assertIn(f'BRIDGE_IMAGE={BRIDGE_DIGEST.split("@")[0]}@sha256:<resolved-compatible-digest>', deployment)
        self.assertIn(f'https://github.com/eznix86/mailgun-proxy-for-ghost/blob/{UPSTREAM_REV}/', upstream)
        self.assertIn('AGPL-3.0', _read(ROOT / 'SKILL.md'))
        self.assertIn('GPL-3.0', _read(ROOT / 'SKILL.md'))
        self.assertIn('https://docs.ghost.org/faq/mailgun-newsletters', upstream)
        self.assertIn('https://proton.me/support/email-sending-limits', upstream)

    def test_does_not_claim_production_ready(self):
        skill = ' '.join(_read(ROOT / 'SKILL.md').split())
        self.assertIn('Do not describe production newsletter delivery as fully repaired.', skill)
        self.assertIn('Isolated capture is not real Proton receipt.', skill)
        v6, _v5, _v4 = _changelog_sections()
        self.assertIn('不能宣称生产 newsletter 路径已经修通', v6)

    def test_changelog_keeps_v4_unmerged_history_and_v5_merged_status(self):
        v6, v5, v4 = _changelog_sections()
        self.assertIn('v6', v6[:80].lower())
        self.assertIn(MERGE, v5)
        self.assertIn('已于 2026-11-20 09:43（Asia/Shanghai）合并', v5)
        self.assertIn('尚未合并', v4)
        self.assertIn('未合并的', v4)
        self.assertIn(FIX, v5)
        self.assertIn(TREE, v5)
        self.assertIn('历史保留', v5)
        self.assertIn(BRIDGE_UPSTREAM, v6)
        self.assertIn('YE4IM/protonmail-bridge-docker', v5)
        self.assertIn('（历史）', v5.splitlines()[0])


if __name__ == '__main__':
    unittest.main()

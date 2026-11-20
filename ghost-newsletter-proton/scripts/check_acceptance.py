"""Run in the private acceptance directory. The poll command only performs GETs."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.parse import parse_qsl, urlencode, urlsplit


class Invalid(ValueError):
    pass


def require(condition, reason=None):
    if not condition:
        raise Invalid(reason or 'Invalid request or response format.')


def object_fields(pairs):
    obj = dict(pairs)
    require(len(obj) == len(pairs), 'Duplicate JSON object keys.')
    return obj


def load(path):
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=object_fields,
                      parse_constant=reject_constant)


def reject_constant(_):
    raise Invalid('Non-finite JSON number is not allowed.')


def text(value, reason=None):
    require(isinstance(value, str) and value.strip(), reason)
    return value


def field(obj, name, reason=None):
    require(isinstance(obj, dict) and name in obj, reason or f'Missing required field {name}.')
    return obj[name]


def queued(directory=None):
    root = Path(directory) if directory is not None else Path('.')
    status = (root / 'send-status.private').read_bytes()
    require(status == b'200', 'Message endpoint did not return HTTP 200.')
    queued_id = text(field(load(root / 'send-response.private.json'), 'id'),
                     'Response id is missing or empty.').encode('utf-8')
    with (root / 'queued-id.private').open('xb') as out:
        out.write(queued_id)
    print('{"queued":1}')
    return 0


def endpoint(url):
    text(url, 'URL is missing or empty.')
    require(all(ord(c) > 32 and ord(c) != 127 for c in url) and '\\' not in url,
            'URL contains whitespace, control characters, or backslashes.')
    parts = urlsplit(url)
    require(parts.scheme == 'https' and parts.hostname and parts.username is None
            and parts.password is None and '#' not in url,
            'URL must be HTTPS with no credentials or fragment.')
    return parts.hostname.lower(), parts.port if parts.port is not None else 443, parts.path


def page_cursor(link, base, scope, *, allow_first_page=False):
    link_host, link_port, link_path = endpoint(link)
    base_host, base_port, base_path = endpoint(base)
    require((link_host, link_port) == (base_host, base_port),
            'Pagination link host or port differs from the events origin.')
    path_cursor = None
    if link_path != base_path:
        require(link_path.startswith(base_path + '/'),
                'Pagination path is not under the events endpoint.')
        path_cursor = link_path[len(base_path) + 1:]
        require(re.fullmatch(r'[A-Za-z0-9_+-]+={0,2}', path_cursor),
                'Pagination path cursor is not a single token.')
    query = object_fields(parse_qsl(urlsplit(link).query, strict_parsing=True,
                                    keep_blank_values=True, max_num_fields=12))
    for name, value in scope.items():
        if name in query:
            require(query.pop(name) == value, 'Pagination link changed a request filter.')
    if path_cursor is not None:
        require(not query, 'Pagination path cursor cannot be mixed with extra query fields.')
        return 'path', path_cursor
    if allow_first_page and not query:
        return None
    require(len(query) == 1, 'Pagination query must contain exactly one cursor parameter.')
    key, value = next(iter(query.items()))
    require(key in ('page', 'cursor') and text(value),
            'Pagination query cursor is missing or uses an unsupported parameter.')
    return key, value


def read_page(path, base, scope, subject):
    page = load(path)
    items, paging = field(page, 'items'), field(page, 'paging')
    require(isinstance(items, list) and isinstance(paging, dict),
            'Event page must contain an items list and a paging object.')
    next_cursor = None
    try:
        for name, link in paging.items():
            require(name in ('next', 'previous', 'first', 'last'),
                    'Unexpected pagination link name.')
            if link is not None:
                cursor = page_cursor(link, base, scope, allow_first_page=name == 'first')
                if name == 'next':
                    next_cursor = cursor
    except ValueError:
        raise Invalid('Invalid pagination link or scope.') from None
    matched = []
    for item in items:
        require(isinstance(item, dict), 'Event item must be an object.')
        recipient = text(field(item, 'recipient'), 'Event item is missing recipient.')
        text(field(item, 'event'), 'Event item is missing event.')
        headers = field(field(item, 'message'), 'headers', 'Event item is missing message.headers.')
        event_subject = text(field(headers, 'subject'), 'Event item is missing subject.')
        if recipient == scope['to'] and event_subject == subject:
            matched.append(item)
    return matched, next_cursor


def classify_matches(matched):
    accepted = sum(e['event'] == 'accepted' for e in matched)
    failed = sum(e['event'] == 'failed' for e in matched)
    unknown = len(matched) - accepted - failed
    return {
        'matched': len(matched),
        'accepted': accepted,
        'failed': failed,
        'unknown': unknown,
    }


def poll_exit_code(counts):
    if counts['failed'] or counts['unknown'] or counts['accepted'] > 1:
        return 1
    if counts['accepted'] == 1:
        return 0
    return None


CURL_TLS_EXIT_CODES = (35, 51, 58, 59, 60, 77, 82, 83, 90, 91, 98)


def curl_command(url, target, remaining, netrc='./proxy-test.netrc'):
    return ['curl', '--disable', '--silent', '--globoff', '--proto', '=https',
            '--max-redirs', '0', '--fail-with-body',
            '--connect-timeout', '5', '--max-time', str(min(20, remaining)),
            '--netrc-file', netrc, '--output', str(target),
            '--write-out', '%{http_code}', '--url', url]


def fetch(url, target, remaining, *, runner=None):
    if runner is None:
        runner = subprocess.run
    args = curl_command(url, target, remaining)
    try:
        result = runner(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                        timeout=remaining)
    except subprocess.TimeoutExpired:
        raise Invalid('HTTPS request timed out.') from None
    if result.returncode == 28:
        raise Invalid('HTTPS request timed out.')
    if result.returncode in CURL_TLS_EXIT_CODES:
        raise Invalid('HTTPS TLS connection or certificate verification failed.')
    status = result.stdout
    if len(status) == 3 and status.isdigit() and b'100' <= status <= b'599' and status != b'200':
        code = status.decode('ascii')
        if code.startswith('3'):
            raise Invalid(f'Event endpoint returned HTTP redirect {code}.')
        raise Invalid(f'Unexpected event endpoint HTTP status {code}.')
    require(result.returncode == 0 and status == b'200', 'HTTPS transport failed.')


def walk(base, scope, subject, directory, sweep, deadline, *, fetch_page=fetch,
         monotonic=time.monotonic, max_pages=20):
    cursor = None
    seen = set()
    matched = []
    for page in range(1, max_pages + 1):
        query = dict(scope)
        url = base
        if cursor:
            key, value = cursor
            if key == 'path':
                url += '/' + value
            else:
                query[key] = value
        target = directory / f'events-{sweep}-{page}.private.json'
        remaining = deadline - monotonic()
        require(remaining > 0, 'Polling time limit reached before pagination finished.')
        fetch_page(url + '?' + urlencode(query), target, remaining)
        batch, cursor = read_page(target, base, scope, subject)
        matched.extend(batch)
        if cursor is None:
            return matched
        require(cursor not in seen, 'Pagination cursor repeated.')
        seen.add(cursor)
    raise Invalid('Pagination page limit reached before the walk finished.')


def poll(base, recipient, subject, begin, *, directory=None, fetch_page=fetch,
         monotonic=time.monotonic, now=time.time, sleep=time.sleep, time_limit=300,
         max_pages=20):
    endpoint(base)
    require('?' not in base and urlsplit(base).path.endswith('/events'),
            'Events URL must be an HTTPS path ending in /events with no query string.')
    text(recipient, 'Recipient is missing or empty.')
    text(subject, 'Subject is missing or empty.')
    require(begin.isascii() and begin.isdigit() and int(begin) <= now(),
            'Begin timestamp is invalid or in the future.')
    root = Path(directory) if directory is not None else Path('.')
    work = Path(tempfile.mkdtemp(prefix='poll-', dir=str(root)))
    deadline = monotonic() + time_limit
    sweep = 0
    while monotonic() < deadline:
        sweep += 1
        scope = {'to': recipient, 'begin': begin, 'end': str(int(now())), 'limit': '300'}
        matched = walk(base, scope, subject, work, sweep, deadline,
                       fetch_page=fetch_page, monotonic=monotonic, max_pages=max_pages)
        counts = classify_matches(matched)
        pending_path = work / 'matched-events.tmp'
        pending_path.write_text(json.dumps(matched), encoding='utf-8')
        pending_path.replace(work / 'matched-events.private.json')
        print(json.dumps(counts), flush=True)
        code = poll_exit_code(counts)
        if code is not None:
            return code
        sleep(max(0, min(5, deadline - monotonic())))
    print('Pending: no correlated handoff.')
    return 2


def main(args):
    os.umask(0o077)
    try:
        if args == ['queued']:
            return queued()
        if len(args) == 5 and args[0] == 'poll':
            return poll(*args[1:])
        print('Usage: check_acceptance.py queued | poll HTTPS_EVENTS_URL RECIPIENT SUBJECT BEGIN',
              file=sys.stderr)
    except Invalid as exc:
        reason = str(exc) or 'Invalid request or response format.'
    except (ValueError, RecursionError):
        reason = 'Invalid request or response format.'
    except OSError:
        reason = 'Could not access private evidence or launch curl.'
    else:
        return 1
    print(f'Acceptance check incomplete. {reason} Inspect private evidence and reconcile.',
          file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

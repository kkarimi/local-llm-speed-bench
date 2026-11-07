"""Measure a running model and turn saved runs into an offline leaderboard."""
import hashlib
import html
import json
import math
import os
from pathlib import Path
import random
import statistics
import time
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.parse import urlsplit


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def prompt(case, index, seed):
    rng = random.Random(f'{seed}/{case}/{index}')
    prefix = f'Benchmark {rng.getrandbits(96):024x}. '
    if case == 'long':
        prefix += 'A reliable computer system records events, checks inputs, measures latency, and restores service after errors. ' * 120
    elif case == '8k':
        words = 'red blue green black white tree road sky sea stone cloud hill rain sun moon'.split()
        prefix += ' '.join(rng.choices(words, k=8110)) + '. '
    return prefix + 'Explain in detail how a computer executes a program, covering processors, memory and storage. Continue for at least 800 words.'


def engine_decode_rate(usage, timings):
    for value in (usage.get('completion_tokens_per_sec'), timings.get('predicted_per_second')):
        if type(value) in (int, float) and math.isfinite(value) and value > 0:
            return value
    return None


def sample(args, case, index):
    message = prompt(case, index, args.seed)
    body = dict(model=args.model, temperature=0, stream=True, max_tokens=args.tokens,
                stream_options={'include_usage': True},
                messages=[{'role': 'user', 'content': message}])
    headers = {'Content-Type': 'application/json'}
    headers.update(auth_headers())
    req = Request(args.url.rstrip('/') + '/chat/completions', json.dumps(body).encode(), headers)
    start = time.perf_counter()
    first = last = None
    usage, timings = {}, {}
    finished = False
    with build_opener(RejectRedirects()).open(req, timeout=240) as response:
        for line in response:
            if not line.startswith(b'data:'):
                continue
            data = line[5:].strip()
            if data == b'[DONE]':
                finished = True
                break
            event = json.loads(data)
            if event.get('error'):
                raise ValueError('Server reported a streaming error')
            usage.update(event.get('usage') or {})
            timings.update(event.get('timings') or {})
            for choice in event.get('choices', []):
                delta = choice.get('delta', {})
                if any(delta.get(k) for k in ('content','reasoning_content','reasoning')):
                    last = time.perf_counter()
                    if first is None:
                        first = last
    n = usage.get('completion_tokens', 0)
    if not finished or first is None or n <= 0:
        raise ValueError('Incomplete stream or missing completion-token count')
    count = usage.get('prompt_tokens')
    if case == '8k' and not 8064 <= (count or 0) <= 8320:
        raise ValueError(f'8K case requires 8192 ±128 input tokens. The server reported {count}.')
    return dict(case=case, prompt_sha256=hashlib.sha256(message.encode()).hexdigest(), input_tokens=count, output_tokens=n, first=first-start,
                total=time.perf_counter()-start, decode=(n-1)/(last-first) if last>first and n>1 else None,
                engine_decode=engine_decode_rate(usage, timings),
                prefill=usage.get('prompt_tokens_per_sec') or timings.get('prompt_per_second'))


def validate_url(base):
    url = urlsplit(base)
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('Use an HTTP(S) base URL without embedded credentials or query parameters')


def discover(base):
    validate_url(base)
    request = Request(base.rstrip('/') + '/models', headers=auth_headers())
    with build_opener(RejectRedirects()).open(request, timeout=15) as response:
        catalog = json.load(response)
    if not isinstance(catalog, dict) or not isinstance(catalog.get('data'), list):
        raise ValueError('Expected a model catalogue with a data array')
    return list(dict.fromkeys(item['id'] for item in catalog['data']
                              if isinstance(item, dict) and isinstance(item.get('id'), str) and item['id'].strip()))


def auth_headers():
    key = os.environ.get('LAB_API_KEY')
    return {'Authorization': 'Bearer ' + key} if key else {}


def measure(args, progress=None):
    validate_url(args.url)
    if args.out.exists():
        raise ValueError('Output already exists. Choose a fresh filename.')
    if args.samples < 1 or args.tokens < 1:
        raise ValueError('Samples and output tokens must be positive')
    cases = args.cases or (['short', 'long', '8k'] if args.include_8k else ['short', 'long'])
    if len(set(cases)) != len(cases):
        raise ValueError('Choose each workload only once')
    if progress:
        progress('Warming up')
    sample(args, 'warmup', 0)
    rows = []
    for case in cases:
        for i in range(args.samples):
            if progress:
                progress(f'{case} · sample {i + 1}/{args.samples}')
            rows.append(sample(args, case, i))
    run = dict(version=1, model=args.model, runtime=args.runtime, seed=args.seed,
               max_tokens=args.tokens, samples=rows)
    data = json.dumps(run, indent=2, allow_nan=False)
    with args.out.open('x') as f:
        f.write(data)


def report(args):
    rows = []
    seen = set()
    protocol = None
    case_prompts = {}
    for path in args.runs:
        run = json.loads(path.read_text())
        if run['version'] != 1 or not run['samples']:
            raise ValueError(f'Unsupported or empty run: {path}')
        identity = run['model'], run['runtime']
        if identity in seen:
            raise ValueError('Each model and runtime pair must have a distinct label')
        seen.add(identity)
        settings = run['seed'], run['max_tokens']
        if protocol is not None and settings != protocol:
            raise ValueError('Compare runs with the same seed and output-token limit')
        protocol = settings
        for case in sorted({r['case'] for r in run['samples']}):
            group = [r for r in run['samples'] if r['case'] == case]
            fingerprints = tuple(r.get('prompt_sha256') for r in group)
            if fingerprints != case_prompts.setdefault(case, fingerprints):
                raise ValueError(f'Cannot compare {case} runs with different prompt samples. Repeat both with matching settings.')
            row = dict(name=html.escape(identity[0]), runtime=html.escape(identity[1]) + f' · n={len(group)}', case=case)
            for key in ('first', 'total', 'decode', 'engine_decode', 'prefill'):
                values = [r.get(key) for r in group]
                row[key] = statistics.median(values) if all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in values) else None
            rows.append(row)
    template = Path(__file__).with_name('leaderboard.html').read_text()
    page = template.replace('__ROWS__', json.dumps(rows,allow_nan=False).replace('<', r'\u003c'))
    args.out.write_text(page.replace('__MACHINE__',html.escape(args.machine)))

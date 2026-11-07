"""Drive both installed wizard presets with a real terminal and a local HTTP fixture."""
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_lab import Fixture, ThreadingHTTPServer


def session(launcher, directory, url, custom):
    master, slave = pty.openpty()
    proc = subprocess.Popen([launcher], stdin=slave, stdout=slave, stderr=slave, cwd=directory)
    os.close(slave)
    pending = b''

    def answer(question, keys=b'\r'):
        nonlocal pending
        deadline = time.monotonic() + 30
        while question not in pending:
            if not select.select([master], [], [], max(0, deadline - time.monotonic()))[0]:
                raise TimeoutError(f'Waiting for {question!r}: {pending[-500:]!r}')
            pending += os.read(master, 8192)
        pending = pending.split(question, 1)[1]
        os.write(master, keys)

    try:
        answer(b'OpenAI-compatible endpoint', url.encode() + b'\r')
        answer(b'Benchmark plan', b'j\r' if custom else b'\r')
        if custom:
            answer(b'Chat models', b' c')
            answer(b'Prompt lengths', b' c')
            answer(b'Measured requests', b'1\r')
            answer(b'Maximum output', b'32\r')
        answer(b'Runtime label')
        answer(b'Start benchmark?')
        answer(b'Report (', b'')
        assert proc.wait(timeout=10) == 0
    finally:
        os.close(master)
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    folder, = (Path(directory) / 'bench-runs').iterdir()
    runs = [json.loads(path.read_text()) for path in sorted(folder.glob('*.json'))]
    assert [r['model'] for r in runs] == (['other'] if custom else ['fixture', 'other'])
    assert all(len(r['samples']) == (2 if custom else 9) for r in runs)
    assert len({r['seed'] for r in runs}) == 1
    assert (folder / 'league.html').is_file()


with ThreadingHTTPServer(('127.0.0.1', 0), Fixture) as server:
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        for custom in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                session(sys.argv[1], directory, f'http://127.0.0.1:{server.server_port}/v1', custom)
    finally:
        server.shutdown()

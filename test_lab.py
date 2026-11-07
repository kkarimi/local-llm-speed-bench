import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest


class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/v1/models':
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"data":[{"id":"fixture"},{"id":"other"},{"id":"fixture"}]}')

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.end_headers()
        for word in ['hello', 'world']:
            event = {'choices':[{'delta':{'content':word}}]}
            self.wfile.write(b'data: '+json.dumps(event).encode()+b'\n\n')
        count = 8192 if len(request['messages'][0]['content']) > 20000 else 70
        usage = {'completion_tokens':4,'prompt_tokens':count,'prompt_tokens_per_sec':200}
        metrics = {'usage': usage}
        if count == 8192:
            metrics['timings'] = {'predicted_per_second': 123.5}
        else:
            usage['completion_tokens_per_sec'] = 111.5
        self.wfile.write(b'data: '+json.dumps(metrics).encode()+b'\n\ndata: [DONE]\n\n')

    def log_message(self, *_):
        pass


class Workflow(unittest.TestCase):
    def test_discovery_and_custom_workload(self):
        cli = [sys.executable, str(Path(__file__).with_name('lab.py').resolve())]
        with tempfile.TemporaryDirectory() as tmp, ThreadingHTTPServer(('127.0.0.1', 0), Fixture) as server:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            url = f'http://127.0.0.1:{server.server_port}/v1'
            try:
                catalog = subprocess.check_output(cli + ['models', '--url', url])
                self.assertEqual(json.loads(catalog), ['fixture', 'other'])
                out = Path(tmp) / 'custom.json'
                subprocess.run(cli + ['bench', '--url', url, '--model', 'other', '--runtime', 'test',
                                      '--cases', 'long', '--samples', '1', '--out', str(out)], check=True, capture_output=True)
                self.assertEqual([r['case'] for r in json.loads(out.read_text())['samples']], ['long'])
            finally:
                server.shutdown()

    def test_standalone_report(self):
        cli = [sys.executable, str(Path(__file__).with_name('lab.py').resolve())]
        with tempfile.TemporaryDirectory() as tmp, ThreadingHTTPServer(('127.0.0.1',0), Fixture) as server:
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                subprocess.run(cli+['bench','--url',f'http://127.0.0.1:{server.server_port}/v1',
                               '--model','fixture','--runtime','<custom>','--samples','1',
                               '--include-8k','--out','run.json'],cwd=tmp,check=True,capture_output=True)
            finally:
                server.shutdown()
            rows=json.loads((Path(tmp)/'run.json').read_text())['samples']
            self.assertEqual([r['case'] for r in rows],['short','long','8k'])
            self.assertEqual([r['engine_decode'] for r in rows], [111.5, 111.5, 123.5])
            self.assertTrue(all(r['output_tokens']==4 for r in rows))
            subprocess.run(cli+['report','run.json'],cwd=tmp,check=True,capture_output=True)
            page=(Path(tmp)/'league.html').read_text()
            self.assertIn('&lt;custom&gt;',page)
            self.assertNotIn('__ROWS__',page)
            other = json.loads((Path(tmp)/'run.json').read_text())
            other['runtime'] = 'second runtime'
            second = Path(tmp)/'second.json'
            self.assertEqual(len(other['samples'][0]['prompt_sha256']), 64)
            for sample in other['samples']:
                del sample['engine_decode']  # Previously saved v1 runs.
            second.write_text(json.dumps(other))
            compare = cli + ['report','run.json','second.json']
            subprocess.run(compare,cwd=tmp,check=True,capture_output=True)
            page = (Path(tmp)/'league.html').read_text()
            data = json.loads(page.split('const rows=',1)[1].split(';\n',1)[0])
            native = [r['engine_decode'] for r in data if r['case']=='8k']
            self.assertEqual(native, [123.5, None])
            other['samples'][0]['prompt_sha256'] = '0' * 64
            second.write_text(json.dumps(other))
            mismatch = subprocess.run(compare,cwd=tmp,text=True,capture_output=True)
            self.assertNotEqual(mismatch.returncode, 0)
            self.assertIn('different prompt samples', mismatch.stderr)

"""HTTP regression tests; no browser, remote data, or third-party test runner."""
import http.client
import json
from pathlib import Path
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import app


class QuietHandler(app.Handler):
    def log_request(self, *args):
        pass


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, body=b'{}', headers=None, method='POST', path='/api/cluster'):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_invalid_dataset_types_are_client_errors(self):
        for value in ([], {}, 42, True, None):
            with self.subTest(value=value):
                status, payload = self.request(json.dumps({'dataset': value}).encode())
                self.assertEqual(status, 400)
                self.assertIn('dataset', payload['error'])

    def test_malformed_json_and_non_object(self):
        for body in (b'{', b'[]', b'null', b'"text"', b'\xff'):
            with self.subTest(body=body):
                status, payload = self.request(body)
                self.assertEqual(status, 400)
                self.assertIn('error', payload)

    def test_invalid_lengths_do_not_wait_for_body(self):
        for length in ('-1', 'abc', '1.5', '9' * 4500):
            with self.subTest(length=length[:20]):
                status, payload = self.request(b'', {'Content-Length': length})
                self.assertIn(status, (400, 413))
                self.assertIn('error', payload)

    def test_oversized_body_rejected_before_reading(self):
        status, _ = self.request(b'', {'Content-Length': str(app.MAX_REQUEST_BYTES + 1)})
        self.assertEqual(status, 413)

    def test_transfer_encoding_rejected(self):
        status, _ = self.request(b'', {'Transfer-Encoding': 'chunked'})
        self.assertEqual(status, 400)

    def test_unknown_route(self):
        status, _ = self.request(path='/api/missing')
        self.assertEqual(status, 404)

    def test_robust_api_returns_certificate_and_stability(self):
        status, datasets = self.request(method='GET', path='/api/datasets')
        d = next(d for d in datasets if d['id'] == 'blobs')
        body = {'dataset': d['id'], 'eps': d['eps']['default'], 'minPts': d['minPts']['default']}
        _, clusters = self.request(json.dumps(body).encode())
        target = clusters['clusters'][0]['id']
        body.update(point=[10,10], target=target, rho=body['eps']*.2)
        status, result = self.request(json.dumps(body).encode(), path='/api/robust')
        self.assertEqual(status, 200)
        self.assertEqual(result['status'], 'ok')
        self.assertGreaterEqual(result['certified_radius']+1e-10, body['rho'])
        self.assertEqual(result['stability']['total'], 9)
        self.assertIsNotNone(result['baseline'])
        for rho in [-1, body['eps'], True, None]:
            body['rho'] = rho
            status, _ = self.request(json.dumps(body).encode(), path='/api/robust')
            self.assertEqual(status, 400)

    def test_robust_page_served_without_external_assets(self):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request('GET','/robust.html')
            response = connection.getresponse(); html = response.read().decode()
            self.assertEqual(response.status, 200)
            self.assertIn('Parameter stability', html)
            self.assertNotIn('src="https://', html)
        finally:
            connection.close()

    def test_valid_cluster_still_works(self):
        status, datasets = self.request(method='GET', path='/api/datasets')
        self.assertEqual(status, 200)
        dataset = next(d for d in datasets if d['kind'] == 'plane')
        status, payload = self.request(json.dumps({
            'dataset': dataset['id'], 'eps': dataset['eps']['default'],
            'minPts': dataset['minPts']['default'],
        }).encode())
        self.assertEqual(status, 200)
        self.assertEqual(len(payload['labels']), dataset['count'])
        self.assertEqual(sum(payload['counts'][k] for k in ('core', 'border', 'noise')), dataset['count'])


if __name__ == '__main__':
    unittest.main()

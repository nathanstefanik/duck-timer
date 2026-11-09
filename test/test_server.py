import json
import socket
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server


def valid_payload(**over):
    fields = {"h": 0, "m": 5, "s": 0}
    fields.update(over)
    return json.dumps(fields).encode()


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        with server.changed:
            server.timers.clear()
            server.rate_limits.clear()

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path) as resp:
                return resp.status, resp.read(), resp.headers.get("Content-Type")
        except urllib.error.HTTPError as e:
            body, ctype = e.read(), e.headers.get("Content-Type")
            e.close()
            return e.code, body, ctype

    def post(self, path, body=None):
        req = urllib.request.Request(
            self.base + path, data=body if body is not None else b"", method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            e.read()
            e.close()
            return e.code, {}

    def make_timer(self, **over):
        status, data = self.post("/api/new", valid_payload(**over))
        self.assertEqual(status, 200)
        return data["code"]

    def test_create_and_get_state(self):
        code = self.make_timer(title="test race")
        self.assertTrue(code)
        status, body, _ = self.get(f"/api/t/{code}")
        state = json.loads(body)
        self.assertEqual(status, 200)
        self.assertIsNone(state["started_at"])
        self.assertIsNone(state["seed"])
        # server shuffles names, so compare order-insensitively
        self.assertEqual(
            sorted(state["names"]), sorted(f"duck {i + 1}" for i in range(6)))
        self.assertEqual(state["duration_s"], 300)
        self.assertEqual(state["dist"], "normal")

    def test_create_bad_requests(self):
        for body in (
            valid_payload(h=100),                       # field out of range
            valid_payload(names=["solo"]),              # fewer than 2 names
            valid_payload(names="abcde"),               # names not a list
            valid_payload(dist="cauchy"),               # unknown dist
            b"{not json",                               # invalid JSON
        ):
            status, _ = self.post("/api/new", body)
            self.assertEqual(status, 400, body)

    def test_body_too_large(self):
        status, _ = self.post("/api/new", b"x" * 4097)
        self.assertEqual(status, 413)

    def test_start_twice_then_reset(self):
        code = self.make_timer()
        _, first = self.post(f"/api/t/{code}/start")
        self.assertIsNotNone(first["started_at"])
        self.assertIsNotNone(first["seed"])
        _, second = self.post(f"/api/t/{code}/start")
        self.assertEqual(second["started_at"], first["started_at"])
        self.assertEqual(second["seed"], first["seed"])
        _, reset = self.post(f"/api/t/{code}/reset")
        self.assertIsNone(reset["started_at"])
        self.assertIsNone(reset["seed"])

    def test_static_files(self):
        status, body, ctype = self.get("/static/race.js")
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "text/javascript")
        self.assertIn(b"simulateRace", body)
        for path in ("/static/../server.py", "/static/nope", "/t/no-such-timer"):
            status, _, _ = self.get(path)
            self.assertEqual(status, 404, path)

    def test_sse_first_event(self):
        code = self.make_timer()
        with socket.create_connection(("127.0.0.1", self.port), timeout=5) as sock:
            sock.sendall(
                f"GET /api/t/{code}/stream HTTP/1.0\r\nHost: x\r\n\r\n".encode())
            sock.settimeout(5)
            data = b""
            while b"\n\n" not in data:
                chunk = sock.recv(4096)
                self.assertTrue(chunk, "connection closed before first event")
                data += chunk
        self.assertIn(b"data: ", data)
        payload = json.loads(data.split(b"data: ", 1)[1].split(b"\n\n", 1)[0])
        self.assertEqual(
            sorted(payload["names"]), sorted(f"duck {i + 1}" for i in range(6)))
        self.assertIsNone(payload["started_at"])

    def test_rate_limit(self):
        for _ in range(10):
            status, _ = self.post("/api/new", valid_payload())
            self.assertEqual(status, 200)
        status, data = self.post("/api/new", valid_payload())
        self.assertEqual(status, 429)


if __name__ == "__main__":
    unittest.main()

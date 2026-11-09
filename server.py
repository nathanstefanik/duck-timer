import json
import random
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from words import new_code

STATIC = Path(__file__).parent / "static"
EXPIRY_S = 24 * 3600
MAX_BODY_BYTES = 4096
RATE_WINDOW_S = 60

CONTENT_TYPES = {".html": "text/html", ".css": "text/css", ".js": "text/javascript"}
FILES = {
    p.name: p.read_bytes()
    for p in STATIC.iterdir()
    if p.is_file() and not p.name.startswith(".")
}

# in-memory by design: a restart drops live timers, an acceptable trade-off
# for a toy shared among friends for at most a day
timers = {}
rate_limits = {}
changed = threading.Condition()  # guards every access to timers and rate_limits


def collect_garbage(now):
    """Drop expired timers and stale rate-limit IPs. Caller holds `changed`."""
    dead = [
        code for code, t in timers.items()
        if (t["started_at"] or t["created_at"]) + t["duration_s"] + EXPIRY_S < now
    ]
    for code in dead:
        del timers[code]
    for ip in [ip for ip, hits in rate_limits.items()
               if not hits or now - hits[-1] >= RATE_WINDOW_S]:
        del rate_limits[ip]
    if dead:
        changed.notify_all()  # wake SSE loops so they notice the deletion


def state(code):
    t = timers[code]
    return {
        "title": t["title"],
        "duration_s": t["duration_s"],
        "started_at": t["started_at"],
        "seed": t["seed"],
        "names": t["names"],
        "dist": t["dist"],
        "look_seed": t["look_seed"],
        "server_now": time.time(),
    }


def check_rate_limit(ip, max_reqs=10, window=RATE_WINDOW_S):
    now = time.time()
    hits = rate_limits.setdefault(ip, [])
    hits[:] = [t for t in hits if now - t < window]
    if len(hits) >= max_reqs:
        return False
    hits.append(now)
    return True


CSP = ("default-src 'self'; style-src 'self'; script-src 'self'; "
       "img-src 'self' data:; connect-src 'self'")


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        self.wfile.write(data)

    def reply_file(self, name):
        ctype = CONTENT_TYPES.get(Path(name).suffix, "application/octet-stream")
        self.reply(200, FILES[name], ctype)

    def client_ip(self):
        return self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()

    def read_body(self):
        """Return the request body, or None after replying with an error."""
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            n = -1
        if n < 0:
            self.reply(400, {"error": "bad Content-Length"})
        elif n > MAX_BODY_BYTES:
            self.reply(413, {"error": "body too large"})
        else:
            return self.rfile.read(n)
        return None

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            self.reply_file("index.html")
        elif path.startswith("/api/t/") and path.endswith("/stream"):
            self.stream_sse(path[len("/api/t/"):-len("/stream")])
        elif path.startswith("/api/t/"):
            code = path[len("/api/t/"):]
            with changed:
                payload = state(code) if code in timers else None
            if payload is None:
                self.reply(404, {"error": "no such timer"})
            else:
                self.reply(200, payload)
        elif path.startswith("/t/"):
            with changed:
                exists = path[len("/t/"):] in timers
            if exists:
                self.reply_file("timer.html")
            else:
                self.reply(404, b"no such timer\n", "text/plain")
        elif path.startswith("/static/"):
            name = path[len("/static/"):]
            if name in FILES:
                self.reply_file(name)
            else:
                self.reply(404, b"not found\n", "text/plain")
        else:
            self.reply(404, b"not found\n", "text/plain")

    def do_POST(self):
        path = self.path.split("?")[0]
        body = self.read_body()
        if body is None:
            return
        if path == "/api/new":
            self.create_timer(body)
        elif path.startswith("/api/t/") and path.endswith("/start"):
            self.act(path[len("/api/t/"):-len("/start")], "start")
        elif path.startswith("/api/t/") and path.endswith("/reset"):
            self.act(path[len("/api/t/"):-len("/reset")], "reset")
        else:
            self.reply(404, {"error": "not found"})

    def create_timer(self, body):
        with changed:
            result = self._create(body)
        self.reply(*result)

    def _create(self, body):
        """Validate and insert a timer. Caller holds `changed`; returns
        (status, payload) for the caller to reply with."""
        if not check_rate_limit(self.client_ip()):
            return 429, {"error": "too many timers, try again later"}
        try:
            fields = json.loads(body)
            h, m, s = (int(fields[k]) for k in ("h", "m", "s"))
        except (ValueError, KeyError, TypeError):
            return 400, {"error": "h, m, s must be integers"}
        duration_s = h * 3600 + m * 60 + s
        if not all(0 <= v <= 99 for v in (h, m, s)) or duration_s < 1:
            return 400, {"error": "each field 0-99, total at least 1 second"}
        title = str(fields.get("title") or "").strip()[:40]
        names_in = fields.get("names") or []
        if not isinstance(names_in, list):
            return 400, {"error": "names must be a list"}
        names = [str(n).strip()[:20] for n in names_in]
        names = [n for n in names if n] or [f"duck {i + 1}" for i in range(6)]
        if not 2 <= len(names) <= 12:
            return 400, {"error": "2 to 12 racer names"}
        dist = fields.get("dist", "normal")
        if dist not in ("normal", "uniform", "exponential"):
            return 400, {"error": "dist must be normal, uniform, or exponential"}
        collect_garbage(time.time())
        code = new_code()
        while code in timers:
            code = new_code()
        random.SystemRandom().shuffle(names)
        timers[code] = {
            "title": title,
            "duration_s": duration_s,
            "started_at": None,
            "seed": None,
            "names": names,
            "dist": dist,
            "look_seed": secrets.randbits(32),
            "created_at": time.time(),
            "version": 0,
        }
        changed.notify_all()
        return 200, {"code": code}

    def act(self, code, action):
        with changed:
            t = timers.get(code)
            if t is None:
                result = 404, {"error": "no such timer"}
            else:
                if action == "start" and t["started_at"] is None:
                    t["started_at"] = time.time()
                    t["seed"] = secrets.randbits(32)
                elif action == "reset":
                    t["started_at"] = None
                    t["seed"] = None
                t["version"] += 1
                changed.notify_all()
                result = 200, state(code)
        self.reply(*result)

    def stream_sse(self, code):
        with changed:
            exists = code in timers
        if not exists:
            return self.reply(404, {"error": "no such timer"})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        seen = None
        while True:
            with changed:
                # first pass sends immediately; afterwards on any version
                # bump, or every 15 s as a heartbeat and clock resync
                changed.wait_for(
                    lambda: timers.get(code, {}).get("version") != seen, timeout=15)
                if code not in timers:
                    return
                seen = timers[code]["version"]
                data = json.dumps(state(code))
            try:
                self.wfile.write(f"data: {data}\n\n".encode())
                self.wfile.flush()
            except OSError:
                return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()

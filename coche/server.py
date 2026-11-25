"""The HTTP server: API, web app, login, calendar feed. Python standard library only."""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import hmac
import html
import ipaddress
import os
import re
import json
import logging
import mimetypes
import secrets
import threading
import time
import urllib.parse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__, ics
from .api import API, dumps
from .config import Config
from .reminders import Notifier, Scheduler
from .store import Store

log = logging.getLogger("coche")
REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
STATIC = Path(__file__).parent / "static"
MAX_BODY = 8 * 1024 * 1024
SESSION_DAYS = 90


def asset_version() -> str:
    """Hash of the static files: browsers re-download them exactly when they change."""
    h = hashlib.sha1(__version__.encode())
    for f in sorted(STATIC.glob("*")):
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()[:10]


class App:
    def __init__(self, config: Config, store: Store | None = None):
        self.c = config
        self.assets = asset_version()
        tz = None
        if config.tz:
            try:
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(config.tz)
            except Exception:                 # Windows without the tzdata package, typo...
                log.warning("Unknown time zone %r (on Windows: pip install tzdata); using the system zone", config.tz)
        self.store = store or Store(config.db_path, tz=tz)
        if config.lang and not self.store.q1("SELECT 1 FROM settings WHERE key='lang'"):
            us = config.lang.lower() in ("en-us", "us")
            self.store.set_settings({"lang": "en" if us else config.lang[:2].lower(),
                                     "date_order": "MDY" if us else "DMY",
                                     "time_format": "12h" if us else "24h"})
        self.api = API(self.store, self)
        self.store.requests_purge(days=30)
        self.request_lock = threading.Lock()     # one X-Request-Id at a time: a replay waits for the original
        self.notifier = Notifier(config)
        self.scheduler = Scheduler(self.store, self.notifier)
        # the password is part of the signing key: changing it logs every session out
        self.secret = hashlib.sha256((self.store.secret("session_key") + "\0" + (config.password or "")).encode()).digest()
        self.failures: dict[str, list[float]] = {}
        self.lock = threading.Lock()

    @property
    def protected(self) -> bool:
        return bool(self.c.password)

    def info(self):
        return {"version": __version__, "title": self.c.title, "base": self.c.base_path,
                "protected": self.protected, "notifications": self.notifier.channels,
                "calendar_url": f"{self.c.base_path}/calendar.ics?key={self.store.secret('ics_key')}"}

    # -- sessions: "expiry.signature" signed with a per-database secret
    def make_session(self) -> str:
        exp = str(int(time.time()) + SESSION_DAYS * 86400)
        return exp + "." + hmac.new(self.secret, exp.encode(), hashlib.sha256).hexdigest()

    def check_session(self, value: str) -> bool:
        try:
            exp, sig = value.split(".", 1)
            good = hmac.new(self.secret, exp.encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(sig, good) and int(exp) > time.time()
        except (ValueError, AttributeError):
            return False

    def check_token(self, tok: str) -> bool:
        if any(hmac.compare_digest(tok, t.strip()) for t in self.c.tokens):
            return True
        return self.store.check_token(tok)

    def rate_limited(self, ip: str) -> bool:
        with self.lock:
            now = time.time()
            hits = [t for t in self.failures.get(ip, []) if now - t < 300]
            self.failures[ip] = hits
            return len(hits) >= 8

    def fail(self, ip):
        with self.lock:
            if len(self.failures) > 5000:          # keep memory bounded under a spray of addresses
                now = time.time()
                self.failures = {k: v for k, v in self.failures.items() if v and now - v[-1] < 300}
            self.failures.setdefault(ip, []).append(time.time())

    def host_allowed(self, host: str) -> bool:
        """Without a password, only answer to IP addresses, localhost and COCHE_ALLOWED_HOSTS: a malicious web
        page can point its own domain name at this address (DNS rebinding) and would otherwise read the tasks."""
        if self.protected:
            return True
        name = (host or "").strip().lower()
        if name.startswith("["):
            name = name[1:].split("]")[0]
        elif name.count(":") == 1:
            name = name.rsplit(":", 1)[0]
        if not name or name == "localhost" or name.endswith(".localhost") or name in self.c.allowed_hosts:
            return True
        try:
            ipaddress.ip_address(name)
            return True
        except ValueError:
            return False


class Handler(BaseHTTPRequestHandler):
    server_version = "Coche"
    protocol_version = "HTTP/1.1"
    app: App = None

    def log_message(self, fmt, *args):
        log.info("%s %s", self.client_ip(), fmt % args)

    # ------------------------------------------------------------------ helpers
    def client_ip(self):
        if self.app.c.trust_proxy and self.headers.get("X-Forwarded-For"):
            return self.headers["X-Forwarded-For"].split(",")[0].strip()
        return self.client_address[0]

    def send(self, status, body=b"", ctype="application/json; charset=utf-8", headers=None, cache="no-store"):
        if isinstance(body, str):
            body = body.encode()
        gz = (len(body) > 1400 and "gzip" in (self.headers.get("Accept-Encoding") or "")
              and ctype.split(";")[0] in ("application/json", "text/html", "text/css", "application/javascript",
                                          "text/javascript", "image/svg+xml", "text/calendar"))
        if gz:
            body = gzip.compress(body, 6)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Content-Security-Policy", "frame-ancestors 'self'; object-src 'none'; base-uri 'self'")
        if gz:
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json(self, status, obj, headers=None):
        if status >= 400 and (self.headers.get("Content-Length") or "0").strip() != "0" and not getattr(self, "_body_read", False):
            self.close_connection = True
            headers = {**(headers or {}), "Connection": "close"}
        if obj is None:
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            return
        self.send(status, dumps(obj), headers=headers)

    def cookie(self, name):
        c = cookies.SimpleCookie()
        try:
            c.load(self.headers.get("Cookie") or "")
        except cookies.CookieError:
            return None
        return c[name].value if name in c else None

    def read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n < 0 or n > MAX_BODY:
            raise ValueError("bad Content-Length")
        raw = self.rfile.read(n) if n else b""
        self._body_read = True
        if not raw:
            return {}
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        if ctype == "application/x-www-form-urlencoded":
            return {k: v[-1] for k, v in urllib.parse.parse_qs(raw.decode()).items()}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("JSON object expected")
        return data

    def auth(self):
        """-> 'open' | 'session' | 'token' | None."""
        if not self.app.protected and not self.app.c.tokens:
            return "open"
        h = self.headers.get("Authorization") or ""
        if h.lower().startswith("bearer ") and self.app.check_token(h[7:].strip()):
            return "token"
        if self.app.check_session(self.cookie("coche_session") or ""):
            return "session"
        if not self.app.protected:
            return "open"          # tokens only restrict when a password is set
        return None

    # ------------------------------------------------------------------ routing
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_DELETE(self):
        self.dispatch("DELETE")

    def do_PUT(self):
        self.dispatch("POST")

    def dispatch(self, method):
        try:
            self._dispatch(method)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            log.exception("error on %s %s", method, self.path)
            try:
                self.json(500, {"error": f"internal error ({type(e).__name__})"})
            except Exception:
                pass

    def _dispatch(self, method):
        url = urllib.parse.urlsplit(self.path)
        base = self.app.c.base_path
        path = url.path
        if base:
            if path == base:
                return self.send(301, b"", headers={"Location": base + "/"})
            if not path.startswith(base + "/"):
                return self.json(404, {"error": "not found"})
            path = path[len(base):]
        query = {k: v[-1] for k, v in urllib.parse.parse_qs(url.query).items()}

        if path == "/healthz":
            return self.json(200, {"ok": True, "version": __version__})
        if not self.app.host_allowed(self.headers.get("Host", "")):
            log.warning("refused Host %r: add it to COCHE_ALLOWED_HOSTS or set COCHE_PASSWORD", self.headers.get("Host"))
            return self.json(421, {"error": "unknown host name: add it to COCHE_ALLOWED_HOSTS (or set COCHE_PASSWORD)"})
        if path.startswith("/static/") or path in ("/sw.js", "/manifest.webmanifest", "/favicon.svg"):
            return self.static(path)
        if path == "/login":
            return self.page("login.html")
        if path == "/api/coche/login" and method == "POST":
            return self.login()
        if path == "/api/coche/logout" and method == "POST":
            return self.json(200, {"ok": True}, headers={"Set-Cookie": self.session_cookie("", 0)})
        if path == "/calendar.ics":
            key = query.get("key") or ""
            if not (self.auth() or hmac.compare_digest(key.encode(), self.app.store.secret("ics_key").encode())):
                return self.json(401, {"error": "invalid key"})
            return self.send(200, ics.build(self.app.store, self.app.c.title),
                             ctype="text/calendar; charset=utf-8", cache="no-cache")

        who = self.auth()
        if path.startswith("/api/"):
            if not who:
                return self.json(401, {"error": "unauthorized"})
            body = {}
            if method in ("POST", "DELETE") and who in ("session", "open"):
                # browser-reachable (cookie or no password): refuse what another web site can make the browser
                # send (CSRF). Forms can't send JSON, and browsers mark cross-site requests with Origin/Sec-Fetch-Site.
                ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if ctype in ("application/x-www-form-urlencoded", "multipart/form-data", "text/plain"):
                    return self.json(415, {"error": "JSON required"})
                origin = self.headers.get("Origin")
                if origin and urllib.parse.urlsplit(origin).netloc != self.headers.get("Host"):
                    return self.json(403, {"error": "cross-site request refused"})
                if self.headers.get("Sec-Fetch-Site") == "cross-site":
                    return self.json(403, {"error": "cross-site request refused"})
            if method in ("POST", "DELETE"):
                try:
                    body = self.read_body()
                except (ValueError, UnicodeDecodeError) as e:
                    return self.json(400, {"error": f"invalid body ({e})"})
            rid = self.headers.get("X-Request-Id") or ""
            if method == "POST" and REQUEST_ID.fullmatch(rid):
                # Idempotent replay (offline queues): same id = same answer, the action runs once (ids kept 30 days).
                with self.app.request_lock:
                    seen = self.app.store.request_get(rid)
                    if seen:
                        return self.json(*seen)
                    status, out = self.app.api.handle(method, path, query, body)
                    if status < 400 and not path.startswith(("/api/coche/tokens", "/api/coche/login")):
                        self.app.store.request_put(rid, status, out)   # never keep a secret (new token) in the table
                return self.json(status, out)
            status, out = self.app.api.handle(method, path, query, body)
            return self.json(status, out)

        if method != "GET":
            return self.json(405, {"error": "method not allowed"})
        if not who:
            return self.send(302, b"", headers={"Location": f"{base}/login"})
        return self.page("index.html")

    # ------------------------------------------------------------------ pages
    def page(self, name):
        c = self.app.c
        raw = (STATIC / name).read_text(encoding="utf-8")
        boot = {"base": c.base_path, "sw": c.service_worker, "protected": self.app.protected,
                "version": __version__, "title": c.title}
        raw = (raw.replace("{{BASE}}", html.escape(c.base_path))
                  .replace("{{TITLE}}", html.escape(c.title))
                  .replace("{{VERSION}}", self.app.assets)
                  .replace("{{BOOT}}", json.dumps(boot).replace("<", "\\u003c"))
                  .replace("<!--EXTRA_HEAD-->", c.extra_head)
                  .replace("<!--EXTRA_BODY-->", c.extra_body))
        self.send(200, raw, ctype="text/html; charset=utf-8", cache="no-cache")

    def static(self, path):
        c = self.app.c
        if path == "/manifest.webmanifest":
            m = {"name": c.title, "short_name": c.title, "start_url": f"{c.base_path}/today",
                 "scope": f"{c.base_path}/", "display": "standalone", "background_color": "#1f1f1f",
                 "theme_color": "#1f1f1f",
                 "icons": [{"src": f"{c.base_path}/static/icon.svg", "sizes": "any", "type": "image/svg+xml",
                            "purpose": "any maskable"}],
                 "shortcuts": [{"name": "Today", "url": f"{c.base_path}/today"},
                               {"name": "Add a task", "url": f"{c.base_path}/today?add=1"}]}
            return self.send(200, json.dumps(m), ctype="application/manifest+json", cache="no-cache")
        if path == "/sw.js" and not c.service_worker:
            return self.json(404, {"error": "service worker disabled"})   # a 404 also unregisters an old one
        name = {"/sw.js": "sw.js", "/favicon.svg": "icon.svg"}.get(path, path[len("/static/"):])
        f = (STATIC / name).resolve()
        if not str(f).startswith(str(STATIC.resolve())) or not f.is_file():
            return self.json(404, {"error": "not found"})
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
            ctype += "; charset=utf-8"
        body = f.read_bytes()
        if name == "sw.js":
            body = body.replace(b"{{BASE}}", c.base_path.encode()).replace(b"{{VERSION}}", self.app.assets.encode())
            return self.send(200, body, ctype=ctype, cache="no-cache",
                             headers={"Service-Worker-Allowed": f"{c.base_path}/"})
        cache = "public, max-age=31536000, immutable" if "v=" in (urllib.parse.urlsplit(self.path).query) else "no-cache"
        self.send(200, body, ctype=ctype, cache=cache)

    def session_cookie(self, value, max_age):
        c = self.app.c
        parts = [f"coche_session={value}", f"Path={c.base_path or '/'}", f"Max-Age={max_age}", "HttpOnly",
                 "SameSite=Strict"]
        if c.secure_cookie:
            parts.append("Secure")
        return "; ".join(parts)

    def login(self):
        ip = self.client_ip()
        if self.app.rate_limited(ip):
            return self.json(429, {"error": "too many attempts, wait 5 minutes"})
        try:
            body = self.read_body()
        except ValueError:
            return self.json(400, {"error": "invalid body"})
        if not self.app.protected:
            return self.json(200, {"ok": True})
        if not hmac.compare_digest(str(body.get("password") or "").encode(), self.app.c.password.encode()):
            self.app.fail(ip)
            time.sleep(0.6)
            return self.json(401, {"error": "wrong password"})
        return self.json(200, {"ok": True},
                         headers={"Set-Cookie": self.session_cookie(self.app.make_session(), SESSION_DAYS * 86400)})


def serve(config: Config):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if config.password == "change-me":
        raise SystemExit("COCHE_PASSWORD is still 'change-me' (from .env.example): pick your own password in .env.")
    os.umask(0o077)                     # the database and its WAL files: owner only
    app = App(config)
    for f in Path(config.data_dir).glob("coche.db*"):
        f.chmod(0o600)
    app.scheduler.start()
    handler = type("BoundHandler", (Handler,), {"app": app})
    httpd = ThreadingHTTPServer((config.host, config.port), handler)
    httpd.daemon_threads = True
    mode = "password" if app.protected else "open (no login - keep it on a trusted network)"
    if not app.protected and config.host not in ("127.0.0.1", "localhost", "::1"):
        log.warning("No COCHE_PASSWORD is set and Coche listens on %s: anyone who can reach this port can read "
                    "and change your tasks. Set COCHE_PASSWORD unless the network is trusted.", config.host)
    log.info("Coche %s on http://%s:%s%s/  data=%s  auth=%s", __version__, config.host, config.port,
             config.base_path, config.data_dir, mode)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def make_server(config: Config, store: Store | None = None, port: int = 0):
    """Test helper: a server on a random port, returns (httpd, app)."""
    app = App(config, store)
    handler = type("BoundHandler", (Handler,), {"app": app})
    httpd = ThreadingHTTPServer((config.host, port), handler)
    httpd.daemon_threads = True
    return httpd, app

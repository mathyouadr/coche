"""Configuration, read from environment variables (and an optional ``.env`` file).

Every setting has a sensible default: ``python -m coche`` just works.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_env_file(path: Path):
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip().removeprefix("export ").strip()
        os.environ.setdefault(k, v.strip().strip('"').strip("'"))


def _bool(v, default=False):
    if v is None or v == "":
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on", "oui")


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 8043
    data_dir: Path = field(default_factory=lambda: Path.home() / ".local/share/coche")
    base_path: str = ""                 # e.g. "/tasks" when served behind a reverse proxy sub-path
    password: str = ""                  # web login; empty = no login (trusted network only)
    tokens: list[str] = field(default_factory=list)   # extra API tokens from the environment
    tz: str = ""                        # IANA zone, e.g. "Europe/Paris"; empty = system zone
    lang: str = ""                      # default UI language for a new database ("en" / "fr")
    title: str = "Coche"
    extra_head: str = ""                # HTML injected in <head> (theme, analytics...)
    extra_body: str = ""                # HTML injected before </body>
    service_worker: bool = True
    secure_cookie: bool = False         # set when served over HTTPS
    trust_proxy: bool = False           # read X-Forwarded-For for logs / rate limit
    allowed_hosts: tuple = ()           # extra host names accepted without a password (anti DNS rebinding)
    notify_command: str = ""            # shell command, gets the reminder JSON on stdin
    ntfy_url: str = ""                  # e.g. https://ntfy.sh/my-secret-topic
    webhook_url: str = ""               # POST every task event (Todoist webhook names)
    webhook_secret: str = ""            # HMAC-SHA256 of the body in X-Coche-Hmac-SHA256

    @property
    def db_path(self) -> Path:
        return self.data_dir / "coche.db"

    @classmethod
    def from_env(cls, env_file: str | None = None) -> "Config":
        _load_env_file(Path(env_file or os.environ.get("COCHE_ENV_FILE", ".env")))
        e = os.environ.get

        def read(name):
            v = e("COCHE_" + name, "")
            if v.startswith("@"):                     # COCHE_EXTRA_HEAD=@/path/to/file.html
                p = Path(v[1:]).expanduser()
                return p.read_text(encoding="utf-8") if p.is_file() else ""
            return v

        base = "/" + e("COCHE_BASE_PATH", "").strip("/") if e("COCHE_BASE_PATH", "").strip("/") else ""
        return cls(
            host=e("COCHE_HOST", "127.0.0.1"), port=int(e("COCHE_PORT", "8043")),
            data_dir=Path(e("COCHE_DATA_DIR", "") or Path.home() / ".local/share/coche").expanduser(),
            base_path=base, password=e("COCHE_PASSWORD", ""),
            tokens=[t for t in e("COCHE_TOKENS", "").split(",") if t.strip()],
            tz=e("COCHE_TZ", "") or e("TZ", ""), lang=e("COCHE_LANG", ""), title=e("COCHE_TITLE", "Coche"),
            extra_head=read("EXTRA_HEAD"), extra_body=read("EXTRA_BODY"),
            service_worker=_bool(e("COCHE_SERVICE_WORKER"), True), secure_cookie=_bool(e("COCHE_SECURE_COOKIE")),
            trust_proxy=_bool(e("COCHE_TRUST_PROXY")), notify_command=e("COCHE_NOTIFY_COMMAND", ""),
            ntfy_url=e("COCHE_NTFY_URL", ""), webhook_url=e("COCHE_WEBHOOK_URL", ""),
            webhook_secret=e("COCHE_WEBHOOK_SECRET", ""),
            allowed_hosts=tuple(h.strip().lower() for h in e("COCHE_ALLOWED_HOSTS", "").split(",") if h.strip()),
        )

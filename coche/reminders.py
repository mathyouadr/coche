"""Reminders and outgoing events.

Three ways to get a reminder out, all optional and combinable:

* ``COCHE_NTFY_URL``        POST to an ntfy topic (phone push in 2 minutes, free)
* ``COCHE_NOTIFY_COMMAND``  run a command, the reminder JSON arrives on stdin
* ``COCHE_WEBHOOK_URL``     every task event is POSTed there (plus ``reminder:fired``)

The scheduler thread checks every 30 seconds.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import queue
import shlex
import subprocess
import threading
import time
import urllib.request

log = logging.getLogger("coche")


class Notifier:
    def __init__(self, config):
        self.c = config
        self.q: queue.Queue = queue.Queue(maxsize=1000)
        self.last_error = None
        threading.Thread(target=self._worker, daemon=True, name="coche-events").start()

    @property
    def channels(self):
        return [n for n, v in (("ntfy", self.c.ntfy_url), ("command", self.c.notify_command),
                               ("webhook", self.c.webhook_url)) if v]

    # -- reminders
    def reminder(self, payload: dict):
        sent = False
        if self.c.ntfy_url:
            try:
                req = urllib.request.Request(self.c.ntfy_url, data=payload["body"].encode() or b" ", method="POST",
                                             headers={"Title": _ascii_header(payload["title"]), "Tags": "bell",
                                                      "Priority": "high" if payload.get("priority", 1) >= 3 else "default"})
                if payload.get("url"):
                    req.add_header("Click", payload["url"])
                urllib.request.urlopen(req, timeout=10).read()
                sent = True
            except Exception as e:
                self.last_error = f"ntfy: {type(e).__name__}"
                log.warning("ntfy failed: %s", e)
        if self.c.notify_command:
            try:
                p = subprocess.run(shlex.split(self.c.notify_command), input=json.dumps(payload, ensure_ascii=False),
                                   text=True, capture_output=True, timeout=30)
                if p.returncode == 0:
                    sent = True
                else:
                    self.last_error = f"command exited with {p.returncode}"
                    log.warning("notify command failed (%s): %s", p.returncode, p.stderr[-300:])
            except Exception as e:
                self.last_error = f"command: {type(e).__name__}"
                log.warning("notify command failed: %s", e)
        self.event("reminder:fired", payload)
        return sent or bool(self.c.webhook_url)

    def test(self):
        if not self.channels:
            return {"ok": False, "error": "no notification channel configured", "channels": []}
        ok = self.reminder({"title": "Coche", "body": "Test notification ✓", "key": "coche-test",
                            "task_id": None, "priority": 1})
        return {"ok": ok, "channels": self.channels, "error": None if ok else self.last_error}

    # -- webhooks (Todoist-compatible event names: item:added, item:completed...)
    def event(self, name, data):
        if not self.c.webhook_url:
            return
        try:
            self.q.put_nowait((name, data))
        except queue.Full:
            pass

    def _worker(self):
        while True:
            name, data = self.q.get()
            body = json.dumps({"event_name": name, "event_data": data, "user_id": "local",
                               "triggered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "version": "10"},
                              ensure_ascii=False).encode()
            headers = {"Content-Type": "application/json", "User-Agent": "Coche-Webhook"}
            if self.c.webhook_secret:
                headers["X-Coche-Hmac-SHA256"] = hmac.new(self.c.webhook_secret.encode(), body,
                                                          hashlib.sha256).hexdigest()
            for attempt in range(3):
                try:
                    urllib.request.urlopen(urllib.request.Request(self.c.webhook_url, data=body, headers=headers),
                                           timeout=10).read()
                    break
                except Exception as e:
                    log.warning("webhook %s failed (%s)", name, e)
                    time.sleep(2 ** attempt)


def _ascii_header(s: str) -> str:
    """HTTP headers are latin-1: ntfy accepts RFC 2047 for anything else."""
    try:
        s.encode("latin-1")
        return s
    except UnicodeEncodeError:
        import base64
        return "=?UTF-8?B?" + base64.b64encode(s.encode()).decode() + "?="


def describe(task: dict, lang: str = "en") -> str:
    due = task.get("due") or {}
    d = due.get("date") or ""
    parts = []
    if "T" in d:
        parts.append(d[11:16])
    if due.get("is_recurring"):
        parts.append(due.get("string") or "")
    if task.get("description"):
        parts.append(task["description"].splitlines()[0][:120])
    return " · ".join(p for p in parts if p) or ("Rappel" if lang == "fr" else "Reminder")


class Scheduler:
    def __init__(self, store, notifier, base_url=""):
        self.s, self.n, self.base_url = store, notifier, base_url
        self.stop = threading.Event()
        self.last_purge = 0

    def start(self):
        threading.Thread(target=self.loop, daemon=True, name="coche-reminders").start()
        self.s.listeners.append(lambda ev, t: self.n.event(ev, t))

    def tick(self):
        lang = self.s.settings().get("lang", "en")
        lang = "en" if lang == "auto" else lang
        for rem, task, key in self.s.due_reminders():
            payload = {"title": task["content"], "body": describe(task, lang), "key": "coche-" + task["id"],
                       "task_id": task["id"], "priority": task["priority"], "due": task.get("due"),
                       "url": f"{self.base_url}/task/{task['id']}" if self.base_url else None}
            self.s.mark_sent(rem, key)           # mark first: never notify twice, even if a channel hangs
            self.n.reminder(payload)
        if time.time() - self.last_purge > 86400:
            self.last_purge = time.time()
            self.s.purge(30)

    def loop(self):
        while not self.stop.wait(30):
            try:
                self.tick()
            except Exception as e:
                log.exception("reminder tick failed: %s", e)

"""SQLite storage + the Todoist-shaped objects the API returns.

One connection, one lock: Coche is a personal app, writes are tiny and SQLite
in WAL mode is far faster than anything a single person can click.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import secrets
import sqlite3
import threading
from pathlib import Path

from . import dates
from .dates import Rule

ALPHABET = "23456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
COLORS = ["berry_red", "red", "orange", "yellow", "olive_green", "lime_green", "green", "mint_green", "teal",
          "sky_blue", "light_blue", "blue", "grape", "violet", "lavender", "magenta", "salmon", "charcoal",
          "grey", "taupe"]
DEFAULT_SETTINGS = {
    "lang": "auto", "theme": "auto", "accent": "#e44332", "daily_goal": 5, "weekly_goal": 25,
    "start_of_week": 0, "date_order": "DMY", "time_format": "24h", "sound": True,
    "auto_reminder": None,          # minutes before a *timed* task (None = no automatic reminder)
    "reminder_time": "09:00",       # when a reminder fires for a task with a date but no time
    "days_off": [5, 6],             # streaks don't break on these days
    "show_completed": False,
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, color TEXT DEFAULT 'charcoal', parent_id TEXT,
  child_order INTEGER DEFAULT 0, is_favorite INTEGER DEFAULT 0, is_archived INTEGER DEFAULT 0,
  is_inbox_project INTEGER DEFAULT 0, view_style TEXT DEFAULT 'list', is_collapsed INTEGER DEFAULT 0,
  description TEXT DEFAULT '', added_at TEXT, updated_at TEXT, is_deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS sections (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL, section_order INTEGER DEFAULT 0,
  is_collapsed INTEGER DEFAULT 0, is_archived INTEGER DEFAULT 0, added_at TEXT, updated_at TEXT,
  is_deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS labels (
  id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE, color TEXT DEFAULT 'charcoal',
  item_order INTEGER DEFAULT 0, is_favorite INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, section_id TEXT, parent_id TEXT, content TEXT NOT NULL,
  description TEXT DEFAULT '', priority INTEGER DEFAULT 1, labels TEXT DEFAULT '[]', child_order INTEGER DEFAULT 0,
  due_date TEXT, due_time TEXT, due_string TEXT, due_lang TEXT, rule TEXT, deadline TEXT, duration INTEGER,
  checked INTEGER DEFAULT 0, is_collapsed INTEGER DEFAULT 0, added_at TEXT, updated_at TEXT, completed_at TEXT,
  is_deleted INTEGER DEFAULT 0, deleted_at TEXT);
CREATE INDEX IF NOT EXISTS tasks_project ON tasks(project_id, checked, is_deleted);
CREATE INDEX IF NOT EXISTS tasks_due ON tasks(due_date) WHERE checked = 0 AND is_deleted = 0;
CREATE TABLE IF NOT EXISTS comments (
  id TEXT PRIMARY KEY, item_id TEXT, project_id TEXT, content TEXT NOT NULL, posted_at TEXT,
  is_deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS reminders (
  id TEXT PRIMARY KEY, item_id TEXT NOT NULL, minute_offset INTEGER, at_time TEXT, at TEXT,
  sent_key TEXT, is_auto INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS filters (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, query TEXT NOT NULL, color TEXT DEFAULT 'charcoal',
  item_order INTEGER DEFAULT 0, is_favorite INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS activity (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, event_type TEXT NOT NULL, object_id TEXT,
  project_id TEXT, content TEXT, extra TEXT);
CREATE INDEX IF NOT EXISTS activity_at ON activity(at);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS tokens (id TEXT PRIMARY KEY, name TEXT, hash TEXT UNIQUE, added_at TEXT, last_used_at TEXT);
"""


class NotFound(LookupError):
    pass


class Invalid(ValueError):
    pass


def new_id(n: int = 16) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(n))


def iso(x: dt.datetime) -> str:
    return x.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def utcnow() -> str:
    return iso(dt.datetime.now(dt.timezone.utc))


def hash_token(tok: str) -> str:
    return hashlib.sha256(tok.encode()).hexdigest()


class Store:
    def __init__(self, path: str | Path, tz=None, clock=None):
        self.path = str(path)
        self.tz = tz                      # zoneinfo.ZoneInfo or None (= system local)
        self.clock = clock                # injectable "now" for tests
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.listeners = []               # callables(event_type, task_dict) - webhooks, reminders
        with self.lock:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA foreign_keys=OFF")
            self.db.executescript(SCHEMA)
            if not self.db.execute("SELECT 1 FROM projects WHERE is_inbox_project=1 AND is_deleted=0").fetchone():
                self.db.execute("INSERT INTO projects(id,name,color,is_inbox_project,child_order,added_at,updated_at)"
                                " VALUES(?,?,?,?,?,?,?)", (new_id(), "Inbox", "charcoal", 1, -1, utcnow(), utcnow()))

    # ------------------------------------------------------------------ time
    def now(self) -> dt.datetime:
        if self.clock:
            return self.clock()
        n = dt.datetime.now(self.tz) if self.tz else dt.datetime.now().astimezone()
        return n.replace(tzinfo=None)

    def today(self) -> dt.date:
        return self.now().date()

    # ------------------------------------------------------------------ low level
    def q(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    def q1(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args).fetchone()

    def x(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args)

    def tx(self):
        store = self

        class _Tx:
            def __enter__(self_):
                store.lock.acquire()
                store.db.execute("BEGIN IMMEDIATE")

            def __exit__(self_, et, ev, tb):
                try:
                    store.db.execute("ROLLBACK" if et else "COMMIT")
                finally:
                    store.lock.release()
        return _Tx()

    def emit(self, event, obj):
        for fn in list(self.listeners):
            try:
                fn(event, obj)
            except Exception:
                pass

    # ------------------------------------------------------------------ settings
    def settings(self) -> dict:
        s = dict(DEFAULT_SETTINGS)
        for r in self.q("SELECT key, value FROM settings"):
            try:
                s[r["key"]] = json.loads(r["value"])
            except ValueError:
                pass
        return s

    def set_settings(self, changes: dict) -> dict:
        for k, v in changes.items():
            if k not in DEFAULT_SETTINGS and not k.startswith("x_"):
                raise Invalid(f"unknown setting {k!r}")
            self.x("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", (k, json.dumps(v)))
        return self.settings()

    def secret(self, key: str) -> str:
        """Server-side secret value, created on first use (never returned by settings())."""
        r = self.q1("SELECT value FROM settings WHERE key=?", ("_" + key,))
        if r:
            return json.loads(r["value"])
        v = secrets.token_urlsafe(24)
        self.x("INSERT INTO settings(key, value) VALUES(?,?)", ("_" + key, json.dumps(v)))
        return v

    def settings_public(self) -> dict:
        return {k: v for k, v in self.settings().items() if not k.startswith("_")}

    # ------------------------------------------------------------------ projects
    def inbox_id(self) -> str:
        return self.q1("SELECT id FROM projects WHERE is_inbox_project=1 AND is_deleted=0")["id"]

    def project_out(self, r) -> dict:
        return {"id": r["id"], "name": r["name"], "color": r["color"], "parent_id": r["parent_id"],
                "child_order": r["child_order"], "is_favorite": bool(r["is_favorite"]),
                "is_archived": bool(r["is_archived"]), "is_inbox_project": bool(r["is_inbox_project"]),
                "inbox_project": bool(r["is_inbox_project"]), "view_style": r["view_style"],
                "is_collapsed": bool(r["is_collapsed"]), "description": r["description"] or "",
                "is_shared": False, "can_assign_tasks": False, "is_deleted": False,
                "created_at": r["added_at"], "updated_at": r["updated_at"]}

    def projects(self, archived=False):
        rows = self.q("SELECT * FROM projects WHERE is_deleted=0 AND is_archived=? ORDER BY is_inbox_project DESC,"
                      " child_order, added_at", (1 if archived else 0,))
        return [self.project_out(r) for r in rows]

    def project(self, pid):
        r = self.q1("SELECT * FROM projects WHERE id=? AND is_deleted=0", (pid,))
        if not r:
            raise NotFound("project")
        return self.project_out(r)

    def add_project(self, d: dict):
        name = _text(d.get("name"), 120)
        if not name:
            raise Invalid("name is required")
        if d.get("parent_id"):
            self.project(d["parent_id"])
        pid = new_id()
        order = d.get("child_order", d.get("order"))
        if order is None:
            order = (self.q1("SELECT MAX(child_order) m FROM projects")["m"] or 0) + 1
        self.x("INSERT INTO projects(id,name,color,parent_id,child_order,is_favorite,view_style,description,added_at,"
               "updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
               (pid, name, _color(d.get("color")), d.get("parent_id"), int(order), int(bool(d.get("is_favorite"))),
                d.get("view_style") if d.get("view_style") in ("list", "board", "calendar") else "list",
                _text(d.get("description"), 4000), utcnow(), utcnow()))
        return self.project(pid)

    def update_project(self, pid, d: dict):
        p = self.project(pid)
        sets = {}
        if "name" in d:
            if not _text(d["name"], 120):
                raise Invalid("name is required")
            if p["is_inbox_project"]:
                raise Invalid("the Inbox can't be renamed")
            sets["name"] = _text(d["name"], 120)
        if "color" in d:
            sets["color"] = _color(d["color"])
        if "is_favorite" in d:
            sets["is_favorite"] = int(bool(d["is_favorite"]))
        if "view_style" in d and d["view_style"] in ("list", "board", "calendar"):
            sets["view_style"] = d["view_style"]
        if "is_collapsed" in d:
            sets["is_collapsed"] = int(bool(d["is_collapsed"]))
        if "description" in d:
            sets["description"] = _text(d["description"], 4000)
        if "child_order" in d:
            sets["child_order"] = int(d["child_order"])
        if "parent_id" in d and not p["is_inbox_project"]:
            if d["parent_id"] == pid:
                raise Invalid("a project can't be its own parent")
            sets["parent_id"] = d["parent_id"] or None
        self._update("projects", pid, sets)
        return self.project(pid)

    def archive_project(self, pid, archived=True):
        p = self.project(pid) if archived else self.project_any(pid)
        if p["is_inbox_project"]:
            raise Invalid("the Inbox can't be archived")
        self._update("projects", pid, {"is_archived": int(archived)})
        return self.project_any(pid)

    def project_any(self, pid):
        r = self.q1("SELECT * FROM projects WHERE id=? AND is_deleted=0", (pid,))
        if not r:
            raise NotFound("project")
        return self.project_out(r)

    def delete_project(self, pid):
        p = self.project_any(pid)
        if p["is_inbox_project"]:
            raise Invalid("the Inbox can't be deleted")
        with self.tx():
            ids = [pid]
            i = 0
            while i < len(ids):
                ids += [r["id"] for r in self.db.execute("SELECT id FROM projects WHERE parent_id=? AND is_deleted=0",
                                                         (ids[i],))]
                i += 1
            for x in ids:
                self.db.execute("UPDATE projects SET is_deleted=1 WHERE id=?", (x,))
                self.db.execute("UPDATE sections SET is_deleted=1 WHERE project_id=?", (x,))
                self.db.execute("UPDATE tasks SET is_deleted=1, deleted_at=? WHERE project_id=?", (utcnow(), x))

    # ------------------------------------------------------------------ sections
    def section_out(self, r):
        return {"id": r["id"], "project_id": r["project_id"], "name": r["name"], "section_order": _num(r["section_order"]),
                "order": _num(r["section_order"]), "is_collapsed": bool(r["is_collapsed"]),
                "is_archived": bool(r["is_archived"]), "is_deleted": False, "added_at": r["added_at"],
                "updated_at": r["updated_at"]}

    def sections(self, project_id=None):
        if project_id:
            rows = self.q("SELECT * FROM sections WHERE is_deleted=0 AND project_id=? ORDER BY section_order",
                          (project_id,))
        else:
            rows = self.q("SELECT * FROM sections WHERE is_deleted=0 ORDER BY project_id, section_order")
        return [self.section_out(r) for r in rows]

    def section(self, sid):
        r = self.q1("SELECT * FROM sections WHERE id=? AND is_deleted=0", (sid,))
        if not r:
            raise NotFound("section")
        return self.section_out(r)

    def add_section(self, d):
        name = _text(d.get("name"), 120)
        if not name:
            raise Invalid("name is required")
        pid = d.get("project_id") or self.inbox_id()
        self.project(pid)
        order = d.get("order", d.get("section_order"))
        if order is None:
            order = (self.q1("SELECT MAX(section_order) m FROM sections WHERE project_id=?", (pid,))["m"] or 0) + 1
        sid = new_id()
        self.x("INSERT INTO sections(id,project_id,name,section_order,added_at,updated_at) VALUES(?,?,?,?,?,?)",
               (sid, pid, name, float(order), utcnow(), utcnow()))
        self._renumber_sections(pid)
        return self.section(sid)

    def _renumber_sections(self, pid):
        rows = self.q("SELECT id FROM sections WHERE project_id=? AND is_deleted=0 ORDER BY section_order, added_at", (pid,))
        for i, r in enumerate(rows):
            self.x("UPDATE sections SET section_order=? WHERE id=?", (i + 1, r["id"]))

    def update_section(self, sid, d):
        self.section(sid)
        sets = {}
        if "name" in d:
            if not _text(d["name"], 120):
                raise Invalid("name is required")
            sets["name"] = _text(d["name"], 120)
        for k in ("is_collapsed", "is_archived"):
            if k in d:
                sets[k] = int(bool(d[k]))
        if "section_order" in d or "order" in d:
            sets["section_order"] = int(d.get("section_order", d.get("order")))
        if "project_id" in d:
            self.project(d["project_id"])
            sets["project_id"] = d["project_id"]
            self.x("UPDATE tasks SET project_id=? WHERE section_id=?", (d["project_id"], sid))
        self._update("sections", sid, sets)
        return self.section(sid)

    def delete_section(self, sid):
        self.section(sid)
        with self.tx():
            self.db.execute("UPDATE sections SET is_deleted=1 WHERE id=?", (sid,))
            self.db.execute("UPDATE tasks SET is_deleted=1, deleted_at=? WHERE section_id=?", (utcnow(), sid))

    # ------------------------------------------------------------------ labels
    def label_out(self, r):
        return {"id": r["id"], "name": r["name"], "color": r["color"], "order": r["item_order"],
                "item_order": r["item_order"], "is_favorite": bool(r["is_favorite"])}

    def labels(self):
        return [self.label_out(r) for r in self.q("SELECT * FROM labels ORDER BY item_order, name COLLATE NOCASE")]

    def label(self, lid):
        r = self.q1("SELECT * FROM labels WHERE id=?", (lid,))
        if not r:
            raise NotFound("label")
        return self.label_out(r)

    def ensure_labels(self, names):
        out = []
        for n in names or []:
            n = _text(n, 60).lstrip("@").replace(" ", "_")
            if not n:
                continue
            r = self.q1("SELECT name FROM labels WHERE name=? COLLATE NOCASE", (n,))
            if r:
                n = r["name"]
            else:
                order = (self.q1("SELECT MAX(item_order) m FROM labels")["m"] or 0) + 1
                self.x("INSERT INTO labels(id,name,item_order) VALUES(?,?,?)", (new_id(), n, order))
            if n not in out:
                out.append(n)
        return out

    def add_label(self, d):
        name = _text(d.get("name"), 60).lstrip("@").replace(" ", "_")
        if not name:
            raise Invalid("name is required")
        if self.q1("SELECT 1 FROM labels WHERE name=? COLLATE NOCASE", (name,)):
            raise Invalid("this label already exists")
        lid = new_id()
        order = (self.q1("SELECT MAX(item_order) m FROM labels")["m"] or 0) + 1
        self.x("INSERT INTO labels(id,name,color,item_order,is_favorite) VALUES(?,?,?,?,?)",
               (lid, name, _color(d.get("color")), int(d.get("order", order)), int(bool(d.get("is_favorite")))))
        return self.label(lid)

    def update_label(self, lid, d):
        old = self.label(lid)
        sets = {}
        if "name" in d:
            new = _text(d["name"], 60).lstrip("@").replace(" ", "_")
            if not new:
                raise Invalid("name is required")
            sets["name"] = new
        if "color" in d:
            sets["color"] = _color(d["color"])
        if "is_favorite" in d:
            sets["is_favorite"] = int(bool(d["is_favorite"]))
        if "order" in d or "item_order" in d:
            sets["item_order"] = int(d.get("order", d.get("item_order")))
        with self.tx():
            if sets:
                self.db.execute(f"UPDATE labels SET {', '.join(k + '=?' for k in sets)} WHERE id=?",
                                (*sets.values(), lid))
            if "name" in sets and sets["name"] != old["name"]:
                self._relabel(old["name"], sets["name"])
        return self.label(lid)

    def delete_label(self, lid):
        old = self.label(lid)
        with self.tx():
            self.db.execute("DELETE FROM labels WHERE id=?", (lid,))
            self._relabel(old["name"], None)

    def _relabel(self, old, new):
        for r in self.db.execute("SELECT id, labels FROM tasks WHERE labels LIKE ?", (f"%{old}%",)).fetchall():
            ls = json.loads(r["labels"] or "[]")
            if any(l.lower() == old.lower() for l in ls):
                ls = [(new if l.lower() == old.lower() else l) for l in ls if new or l.lower() != old.lower()]
                self.db.execute("UPDATE tasks SET labels=? WHERE id=?", (json.dumps(ls, ensure_ascii=False), r["id"]))

    # ------------------------------------------------------------------ tasks: output
    def due_out(self, r):
        if not r["due_date"]:
            return None
        date = r["due_date"] + (f"T{r['due_time']}:00" if r["due_time"] else "")
        rule = Rule.from_dict(json.loads(r["rule"])) if r["rule"] else None
        lang = r["due_lang"] or "en"
        string = r["due_string"] or ""
        if not string:
            string = dates.rule_to_text(rule, lang) if rule else r["due_date"]
        return {"date": date, "string": string, "lang": lang, "is_recurring": rule is not None, "timezone": None}

    def task_out(self, r, counts=None):
        counts = counts or {}
        return {
            "id": r["id"], "user_id": "local", "project_id": r["project_id"], "section_id": r["section_id"],
            "parent_id": r["parent_id"], "content": r["content"], "description": r["description"] or "",
            "priority": r["priority"], "labels": json.loads(r["labels"] or "[]"), "child_order": _num(r["child_order"]),
            "day_order": -1, "checked": bool(r["checked"]), "is_deleted": bool(r["is_deleted"]),
            "is_collapsed": bool(r["is_collapsed"]), "added_at": r["added_at"], "updated_at": r["updated_at"],
            "completed_at": r["completed_at"], "added_by_uid": "local", "assigned_by_uid": None,
            "responsible_uid": None, "due": self.due_out(r),
            "deadline": {"date": r["deadline"], "lang": r["due_lang"] or "en"} if r["deadline"] else None,
            "duration": {"amount": r["duration"], "unit": "minute"} if r["duration"] else None,
            "note_count": counts.get(("c", r["id"]), 0),
            "rule": json.loads(r["rule"]) if r["rule"] else None,
        }

    def _counts(self):
        c = {}
        for r in self.q("SELECT item_id, COUNT(*) n FROM comments WHERE is_deleted=0 GROUP BY item_id"):
            c[("c", r["item_id"])] = r["n"]
        return c

    def tasks(self, where="checked=0", args=(), order="child_order, added_at"):
        rows = self.q(f"SELECT * FROM tasks WHERE is_deleted=0 AND {where} ORDER BY {order}", args)
        counts = self._counts()
        return [self.task_out(r, counts) for r in rows]

    def task_row(self, tid, deleted=False):
        r = self.q1("SELECT * FROM tasks WHERE id=?" + ("" if deleted else " AND is_deleted=0"), (tid,))
        if not r:
            raise NotFound("task")
        return r

    def task(self, tid):
        return self.task_out(self.task_row(tid), self._counts())

    # ------------------------------------------------------------------ tasks: due helpers
    def _apply_due(self, sets: dict, d: dict, lang: str):
        """Read Todoist due fields (due_string / due_date / due_datetime) into column values."""
        order = self.settings().get("date_order", "DMY")
        if d.get("due_string") not in (None, ""):
            ds = str(d["due_string"])
            due = dates.parse_due(ds, self.today(), self.now(), order)
            if due is None:
                raise Invalid(f"date not understood: {ds!r}")
            if due.clear:
                sets.update(due_date=None, due_time=None, due_string=None, rule=None)
            else:
                sets.update(due_date=due.date.isoformat(), due_time=due.time, due_string=ds[:120],
                            due_lang=d.get("due_lang") or lang,
                            rule=json.dumps(due.rule.to_dict()) if due.rule else None)
                if due.duration and "duration" not in d:
                    sets["duration"] = due.duration
        elif d.get("due_datetime"):
            x = dt.datetime.fromisoformat(str(d["due_datetime"]).replace("Z", "+00:00"))
            if x.tzinfo:
                x = x.astimezone(self.tz) if self.tz else x.astimezone()
            sets.update(due_date=x.date().isoformat(), due_time=x.strftime("%H:%M"), due_string=None, rule=None)
        elif d.get("due_date"):
            dd = dt.date.fromisoformat(str(d["due_date"])[:10])
            sets.update(due_date=dd.isoformat(), due_string=None)
            if "T" in str(d["due_date"]):
                sets["due_time"] = str(d["due_date"])[11:16]
            elif "due_time" in d:
                sets["due_time"] = _hm(d.get("due_time"))
            else:
                sets["due_time"] = None
            # keep the recurrence when a recurring task is simply moved to another day
        elif "due_string" in d or "due_date" in d or d.get("due") is None and "due" in d:
            sets.update(due_date=None, due_time=None, due_string=None, rule=None)
        if "due_time" in d and "due_time" not in sets and not d.get("due_string") and not d.get("due_datetime"):
            sets["due_time"] = _hm(d.get("due_time"))
        if "deadline_date" in d:
            sets["deadline"] = dt.date.fromisoformat(d["deadline_date"]).isoformat() if d["deadline_date"] else None
        if "duration" in d:
            v = d.get("duration")
            if isinstance(v, dict):
                v = v.get("amount") if v.get("unit", "minute") == "minute" else (v.get("amount") or 0) * 1440
            sets["duration"] = int(v) if v else None
        if "rule" in d:
            sets["rule"] = json.dumps(d["rule"]) if d["rule"] else None

    # ------------------------------------------------------------------ tasks: write
    def add_task(self, d: dict, *, log=True):
        content = _text(d.get("content"), 1000)
        if not content:
            raise Invalid("content is required")
        lang = d.get("due_lang") or self.settings().get("lang", "en")
        lang = "en" if lang == "auto" else lang
        parent = None
        if d.get("parent_id"):
            parent = self.task_row(d["parent_id"])
        section = self.section(d["section_id"]) if d.get("section_id") else None
        pid = d.get("project_id") or (section["project_id"] if section else None) or (
            parent["project_id"] if parent else None) or self.inbox_id()
        self.project(pid)
        if section and section["project_id"] != pid:
            raise Invalid("section is not in this project")
        sid = section["id"] if section else (parent["section_id"] if parent and not d.get("project_id") else None)
        sets = {}
        self._apply_due(sets, d, lang)
        try:
            prio = min(4, max(1, int(d.get("priority") or 1)))
        except (TypeError, ValueError):
            raise Invalid("priority must be 1..4")
        tid = d.get("_id") or new_id()
        labels = self.ensure_labels(d.get("labels") or [])
        order = d.get("child_order", d.get("order"))
        if order is None:
            order = (self.q1("SELECT MAX(child_order) m FROM tasks WHERE project_id=? AND IFNULL(section_id,'')=?"
                             " AND IFNULL(parent_id,'')=?", (pid, sid or "", d.get("parent_id") or ""))["m"] or 0) + 1
        now = d.get("_added_at") or utcnow()
        cols = dict(id=tid, project_id=pid, section_id=sid, parent_id=d.get("parent_id"), content=content,
                    description=_text(d.get("description"), 16000, keep_lines=True), priority=prio,
                    labels=json.dumps(labels, ensure_ascii=False), child_order=float(order), added_at=now,
                    updated_at=now, **{"due_lang": lang, **sets})
        self.x(f"INSERT INTO tasks({','.join(cols)}) VALUES({','.join('?' * len(cols))})", tuple(cols.values()))
        for rem in d.get("reminders") or []:
            self.add_reminder(tid, rem)
        t = self.task(tid)
        if log:
            self.log("added", t)
        self.emit("item:added", t)
        return t

    def update_task(self, tid, d: dict):
        r = self.task_row(tid)
        sets = {}
        if "content" in d:
            if not _text(d["content"], 1000):
                raise Invalid("content is required")
            sets["content"] = _text(d["content"], 1000)
        if "description" in d:
            sets["description"] = _text(d["description"], 16000, keep_lines=True)
        if "priority" in d:
            try:
                sets["priority"] = min(4, max(1, int(d["priority"])))
            except (TypeError, ValueError):
                raise Invalid("priority must be 1..4")
        if "labels" in d:
            sets["labels"] = json.dumps(self.ensure_labels(d["labels"] or []), ensure_ascii=False)
        if "is_collapsed" in d:
            sets["is_collapsed"] = int(bool(d["is_collapsed"]))
        if "child_order" in d:
            sets["child_order"] = int(d["child_order"])
        self._apply_due(sets, d, d.get("due_lang") or r["due_lang"] or self.settings().get("lang", "en"))
        if not sets:
            return self.task(tid)
        self._update("tasks", tid, sets)
        t = self.task(tid)
        if sets.keys() & {"due_date", "due_time"}:
            self.x("UPDATE reminders SET sent_key=NULL WHERE item_id=?", (tid,))
        self.log("updated", t, {"fields": sorted(sets)})
        self.emit("item:updated", t)
        return t

    def move_task(self, tid, d: dict):
        r = self.task_row(tid)
        pid, sid, parent = r["project_id"], r["section_id"], r["parent_id"]
        if d.get("parent_id"):
            p = self.task_row(d["parent_id"])
            if p["id"] == tid or tid in self._ancestors(p["id"]):
                raise Invalid("a task can't be moved inside itself")
            pid, sid, parent = p["project_id"], p["section_id"], p["id"]
        elif d.get("section_id"):
            s = self.section(d["section_id"])
            pid, sid, parent = s["project_id"], s["id"], None
        elif d.get("project_id"):
            self.project(d["project_id"])
            pid, sid, parent = d["project_id"], None, None
        elif "section_id" in d or "parent_id" in d:
            sid = None if "section_id" in d else sid
            parent = None
        else:
            raise Invalid("project_id, section_id or parent_id is required")
        with self.tx():
            self.db.execute("UPDATE tasks SET project_id=?, section_id=?, parent_id=?, updated_at=? WHERE id=?",
                            (pid, sid, parent, utcnow(), tid))
            for c in self._descendants(tid):
                self.db.execute("UPDATE tasks SET project_id=?, section_id=? WHERE id=?", (pid, sid, c))
        t = self.task(tid)
        self.emit("item:updated", t)
        return t

    def _descendants(self, tid):
        out, todo = [], [tid]
        while todo:
            cur = todo.pop()
            for r in self.db.execute("SELECT id FROM tasks WHERE parent_id=? AND is_deleted=0", (cur,)).fetchall():
                out.append(r["id"])
                todo.append(r["id"])
        return out

    def _ancestors(self, tid):
        out, cur = [], tid
        for _ in range(50):
            r = self.q1("SELECT parent_id FROM tasks WHERE id=?", (cur,))
            if not r or not r["parent_id"]:
                break
            cur = r["parent_id"]
            out.append(cur)
        return out

    def close_task(self, tid):
        """Complete a task. A recurring task moves to its next date instead."""
        r = self.task_row(tid)
        today = self.today()
        rule = Rule.from_dict(json.loads(r["rule"])) if r["rule"] else None
        if rule and r["due_date"] and not r["checked"]:
            cur = dt.date.fromisoformat(r["due_date"])
            nxt = dates.advance(rule, cur, today)
            self._update("tasks", tid, {"due_date": nxt.isoformat()})
            self.x("UPDATE reminders SET sent_key=NULL WHERE item_id=?", (tid,))
            t = self.task(tid)
            self.log("completed", t, {"recurring": True, "previous_date": r["due_date"], "next_date": nxt.isoformat()})
            self.emit("item:completed", t)
            return {"task": t, "recurring": True, "previous_date": r["due_date"]}
        if r["checked"]:
            return {"task": self.task(tid), "recurring": False}
        stamp = utcnow()
        with self.tx():
            ids = [tid] + self._descendants(tid)
            for x in ids:
                self.db.execute("UPDATE tasks SET checked=1, completed_at=?, updated_at=? WHERE id=? AND checked=0",
                                (stamp, stamp, x))
        t = self.task(tid)
        self.log("completed", t, {"subtasks": len(ids) - 1})
        self.emit("item:completed", t)
        return {"task": t, "recurring": False, "closed": ids}

    def reopen_task(self, tid, previous_date=None):
        r = self.task_row(tid)
        if not r["checked"]:
            if previous_date and r["rule"]:            # undo a recurring completion
                dt.date.fromisoformat(previous_date)
                self._update("tasks", tid, {"due_date": previous_date})
                last = self.q1("SELECT id FROM activity WHERE object_id=? AND event_type='completed' ORDER BY id DESC"
                               " LIMIT 1", (tid,))
                if last:
                    self.x("DELETE FROM activity WHERE id=?", (last["id"],))
            return self.task(tid)
        with self.tx():
            for x in [tid] + self._ancestors(tid):
                self.db.execute("UPDATE tasks SET checked=0, completed_at=NULL, updated_at=? WHERE id=?",
                                (utcnow(), x))
        t = self.task(tid)
        self.log("uncompleted", t)
        self.emit("item:uncompleted", t)
        return t

    def delete_task(self, tid):
        self.task_row(tid)
        stamp = utcnow()
        t = self.task(tid)
        with self.tx():
            for x in [tid] + self._descendants(tid):
                self.db.execute("UPDATE tasks SET is_deleted=1, deleted_at=? WHERE id=?", (stamp, x))
        self.log("deleted", t)
        self.emit("item:deleted", t)

    def restore_task(self, tid):
        r = self.task_row(tid, deleted=True)
        if not r["is_deleted"]:
            return self.task(tid)
        with self.tx():
            self.db.execute("UPDATE tasks SET is_deleted=0, deleted_at=NULL WHERE deleted_at=? AND (id=? OR id IN"
                            " (SELECT id FROM tasks WHERE deleted_at=?))", (r["deleted_at"], tid, r["deleted_at"]))
        t = self.task(tid)
        self.emit("item:added", t)
        return t

    def reorder(self, ids, project_id=None, section_id=None, parent_id=None, set_container=False):
        """Set child_order from a list of ids (drag & drop); optionally move them into a container."""
        with self.tx():
            for i, tid in enumerate(ids):
                if set_container:
                    pid = project_id
                    if not pid:
                        row = self.db.execute("SELECT project_id FROM tasks WHERE id=?", (tid,)).fetchone()
                        pid = row["project_id"] if row else None
                    self.db.execute("UPDATE tasks SET child_order=?, project_id=?, section_id=?, parent_id=?,"
                                    " updated_at=? WHERE id=?", (i + 1, pid, section_id, parent_id, utcnow(), tid))
                    for c in self._descendants(tid):
                        self.db.execute("UPDATE tasks SET project_id=?, section_id=? WHERE id=?", (pid, section_id, c))
                else:
                    self.db.execute("UPDATE tasks SET child_order=? WHERE id=?", (i + 1, tid))
        return [self.task(t) for t in ids]

    def reorder_objects(self, table, ids):
        col = {"projects": "child_order", "sections": "section_order", "labels": "item_order",
               "filters": "item_order"}[table]
        with self.tx():
            for i, oid in enumerate(ids):
                self.db.execute(f"UPDATE {table} SET {col}=? WHERE id=?", (i + 1, oid))

    def purge(self, days=30):
        cut = iso(dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days))
        self.x("DELETE FROM tasks WHERE is_deleted=1 AND deleted_at < ?", (cut,))

    # ------------------------------------------------------------------ comments
    def comment_out(self, r):
        return {"id": r["id"], "task_id": r["item_id"], "item_id": r["item_id"], "project_id": r["project_id"],
                "content": r["content"], "posted_at": r["posted_at"], "posted_uid": "local",
                "file_attachment": None, "is_deleted": False}

    def comments(self, task_id=None, project_id=None):
        if task_id:
            rows = self.q("SELECT * FROM comments WHERE is_deleted=0 AND item_id=? ORDER BY posted_at", (task_id,))
        else:
            rows = self.q("SELECT * FROM comments WHERE is_deleted=0 AND project_id=? AND item_id IS NULL"
                          " ORDER BY posted_at", (project_id,))
        return [self.comment_out(r) for r in rows]

    def add_comment(self, d):
        content = _text(d.get("content"), 16000, keep_lines=True)
        if not content:
            raise Invalid("content is required")
        tid = d.get("task_id") or d.get("item_id")
        pid = d.get("project_id")
        if tid:
            pid = self.task_row(tid)["project_id"]
        elif pid:
            self.project(pid)
        else:
            raise Invalid("task_id or project_id is required")
        cid = new_id()
        self.x("INSERT INTO comments(id,item_id,project_id,content,posted_at) VALUES(?,?,?,?,?)",
               (cid, tid, pid, content, d.get("_posted_at") or utcnow()))
        return self.comment_out(self.q1("SELECT * FROM comments WHERE id=?", (cid,)))

    def update_comment(self, cid, d):
        if not self.q1("SELECT 1 FROM comments WHERE id=? AND is_deleted=0", (cid,)):
            raise NotFound("comment")
        self.x("UPDATE comments SET content=? WHERE id=?", (_text(d.get("content"), 16000, keep_lines=True), cid))
        return self.comment_out(self.q1("SELECT * FROM comments WHERE id=?", (cid,)))

    def delete_comment(self, cid):
        if not self.q1("SELECT 1 FROM comments WHERE id=? AND is_deleted=0", (cid,)):
            raise NotFound("comment")
        self.x("UPDATE comments SET is_deleted=1 WHERE id=?", (cid,))

    # ------------------------------------------------------------------ reminders
    def reminder_out(self, r):
        return {"id": r["id"], "item_id": r["item_id"], "task_id": r["item_id"],
                "type": "absolute" if (r["at"] or r["at_time"]) else "auto_off" if r["minute_offset"] == -1 else "relative",
                "minute_offset": r["minute_offset"], "time": r["at_time"], "at": r["at"], "is_auto": bool(r["is_auto"])}

    def reminders(self, task_id=None):
        if task_id:
            rows = self.q("SELECT * FROM reminders WHERE item_id=?", (task_id,))
        else:
            rows = self.q("SELECT * FROM reminders")
        return [self.reminder_out(r) for r in rows]

    def add_reminder(self, tid, d):
        self.task_row(tid)
        rid = new_id()
        mins = d.get("minutes_before", d.get("minute_offset"))
        at_time = _hm(d.get("time")) if d.get("time") else None
        at = None
        if d.get("at") or (d.get("due") or {}).get("date"):
            raw = str(d.get("at") or d["due"]["date"])
            at = dt.datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None).isoformat(timespec="minutes")
        if mins is None and not at_time and not at:
            mins = 0
        if mins is not None and (int(mins) < -1 or int(mins) > 60 * 24 * 60):
            raise Invalid("minutes_before must be between 0 and 86400")
        dup = self.q1("SELECT * FROM reminders WHERE item_id=? AND IFNULL(minute_offset,-99)=? AND IFNULL(at_time,'')=?"
                      " AND IFNULL(at,'')=?", (tid, int(mins) if mins is not None else -99, at_time or "", at or ""))
        if dup:
            return self.reminder_out(dup)
        self.x("INSERT INTO reminders(id,item_id,minute_offset,at_time,at,is_auto) VALUES(?,?,?,?,?,?)",
               (rid, tid, int(mins) if mins is not None else None, at_time, at, int(bool(d.get("is_auto")))))
        return self.reminder_out(self.q1("SELECT * FROM reminders WHERE id=?", (rid,)))

    def delete_reminder(self, rid):
        if not self.q1("SELECT 1 FROM reminders WHERE id=?", (rid,)):
            raise NotFound("reminder")
        self.x("DELETE FROM reminders WHERE id=?", (rid,))

    def due_reminders(self):
        """[(reminder_row, task_dict, fire_key)] that should fire now. Pure read."""
        now = self.now()
        s = self.settings()
        default_hm = s.get("reminder_time") or "09:00"
        out = []
        rows = self.q("SELECT r.*, t.due_date, t.due_time FROM reminders r JOIN tasks t ON t.id = r.item_id"
                      " WHERE t.checked=0 AND t.is_deleted=0")
        auto = s.get("auto_reminder")
        candidates = [(dict(r), r["at"], r["at_time"], r["minute_offset"]) for r in rows if r["minute_offset"] != -1]
        if auto is not None:
            # additive: a task keeps its automatic reminder next to the ones added by hand, unless it was
            # switched off for this task (a row with minute_offset -1) or one already fires at that minute
            for r in self.q("SELECT id, due_date, due_time FROM tasks WHERE checked=0 AND is_deleted=0 AND due_time"
                            " IS NOT NULL AND id NOT IN (SELECT item_id FROM reminders WHERE minute_offset=-1"
                            " OR (minute_offset=? AND at IS NULL AND at_time IS NULL))", (int(auto),)):
                fake = {"id": "auto-" + r["id"], "item_id": r["id"], "due_date": r["due_date"],
                        "due_time": r["due_time"], "sent_key": self._auto_sent(r["id"])}
                candidates.append((fake, None, None, int(auto)))
        for r, at, at_time, mins in candidates:
            if at:
                fire = dt.datetime.fromisoformat(at)
            elif not r["due_date"]:
                continue
            else:
                day = dt.date.fromisoformat(r["due_date"])
                hm = at_time or r["due_time"] or default_hm
                fire = dt.datetime.combine(day, dt.time.fromisoformat(hm))
                if not at_time and mins:
                    fire -= dt.timedelta(minutes=mins)
            key = fire.isoformat(timespec="minutes")
            if fire <= now < fire + dt.timedelta(hours=6) and r.get("sent_key") != key:
                out.append((r, self.task(r["item_id"]), key))
        return out

    def _auto_sent(self, tid):
        r = self.q1("SELECT value FROM settings WHERE key=?", ("_auto_sent_" + tid,))
        return json.loads(r["value"]) if r else None

    def mark_sent(self, reminder, key):
        if str(reminder["id"]).startswith("auto-"):
            self.x("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)",
                   ("_auto_sent_" + reminder["item_id"], json.dumps(key)))
        else:
            self.x("UPDATE reminders SET sent_key=? WHERE id=?", (key, reminder["id"]))

    # ------------------------------------------------------------------ filters
    def filter_out(self, r):
        return {"id": r["id"], "name": r["name"], "query": r["query"], "color": r["color"],
                "item_order": r["item_order"], "is_favorite": bool(r["is_favorite"])}

    def filters(self):
        return [self.filter_out(r) for r in self.q("SELECT * FROM filters ORDER BY item_order, name")]

    def add_filter(self, d):
        name, query = _text(d.get("name"), 120), _text(d.get("query"), 1000)
        if not name or not query:
            raise Invalid("name and query are required")
        fid = new_id()
        order = (self.q1("SELECT MAX(item_order) m FROM filters")["m"] or 0) + 1
        self.x("INSERT INTO filters(id,name,query,color,item_order,is_favorite) VALUES(?,?,?,?,?,?)",
               (fid, name, query, _color(d.get("color")), order, int(bool(d.get("is_favorite")))))
        return self.filter_out(self.q1("SELECT * FROM filters WHERE id=?", (fid,)))

    def update_filter(self, fid, d):
        if not self.q1("SELECT 1 FROM filters WHERE id=?", (fid,)):
            raise NotFound("filter")
        sets = {}
        for k in ("name", "query"):
            if k in d:
                if not _text(d[k], 1000):
                    raise Invalid(f"{k} is required")
                sets[k] = _text(d[k], 1000)
        if "color" in d:
            sets["color"] = _color(d["color"])
        if "is_favorite" in d:
            sets["is_favorite"] = int(bool(d["is_favorite"]))
        if sets:
            self.x(f"UPDATE filters SET {', '.join(k + '=?' for k in sets)} WHERE id=?", (*sets.values(), fid))
        return self.filter_out(self.q1("SELECT * FROM filters WHERE id=?", (fid,)))

    def delete_filter(self, fid):
        self.x("DELETE FROM filters WHERE id=?", (fid,))

    # ------------------------------------------------------------------ activity & stats
    def log(self, event, t, extra=None):
        self.x("INSERT INTO activity(at,event_type,object_id,project_id,content,extra) VALUES(?,?,?,?,?,?)",
               (utcnow(), event, t["id"], t["project_id"], t["content"],
                json.dumps({**(extra or {}), "due": (t.get("due") or {}).get("date")}, ensure_ascii=False)))

    def activity(self, since=None, until=None, events=None, limit=200):
        sql, args = "SELECT * FROM activity WHERE 1=1", []
        if since:
            sql += " AND at >= ?"
            args.append(since)
        if until:
            sql += " AND at < ?"
            args.append(until)
        if events:
            sql += f" AND event_type IN ({','.join('?' * len(events))})"
            args += list(events)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(int(limit))
        return [{"id": r["id"], "event_date": r["at"], "event_type": r["event_type"], "object_type": "item",
                 "object_id": r["object_id"], "parent_project_id": r["project_id"], "content": r["content"],
                 "extra_data": json.loads(r["extra"] or "{}")} for r in self.q(sql, args)]

    def local_day(self, stamp: str) -> dt.date:
        x = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        return (x.astimezone(self.tz) if self.tz else x.astimezone()).date()

    def stats(self):
        s = self.settings()
        today = self.today()
        since = iso(dt.datetime.combine(today - dt.timedelta(days=400), dt.time()).replace(tzinfo=dt.timezone.utc))
        per_day = {}
        for r in self.q("SELECT at FROM activity WHERE event_type='completed' AND at >= ?", (since,)):
            d = self.local_day(r["at"])
            per_day[d] = per_day.get(d, 0) + 1
        goal = max(1, int(s.get("daily_goal") or 5))
        off = set(s.get("days_off") or [])

        def streak(start):
            n, d = 0, start
            while True:
                if per_day.get(d, 0) >= goal:
                    n += 1
                elif d.weekday() not in off:
                    break
                d -= dt.timedelta(days=1)
                if (start - d).days > 400:
                    break
            return n
        cur = streak(today) if per_day.get(today, 0) >= goal else streak(today - dt.timedelta(days=1))
        best, run = 0, 0
        for i in range(400, -1, -1):
            d = today - dt.timedelta(days=i)
            if per_day.get(d, 0) >= goal:
                run += 1
                best = max(best, run)
            elif d.weekday() not in off:
                run = 0
        monday = today - dt.timedelta(days=(today.weekday() - int(s.get("start_of_week") or 0)) % 7)
        week = sum(v for k, v in per_day.items() if k >= monday)
        days = [{"date": (today - dt.timedelta(days=i)).isoformat(),
                 "completed": per_day.get(today - dt.timedelta(days=i), 0)} for i in range(13, -1, -1)]
        total = self.q1("SELECT COUNT(*) n FROM activity WHERE event_type='completed'")["n"]
        return {"today": per_day.get(today, 0), "daily_goal": goal, "week": week,
                "weekly_goal": int(s.get("weekly_goal") or 25), "streak": cur, "best_streak": best,
                "days": days, "completed_total": total}

    # ------------------------------------------------------------------ tokens
    def tokens(self):
        return [{"id": r["id"], "name": r["name"], "added_at": r["added_at"], "last_used_at": r["last_used_at"]}
                for r in self.q("SELECT * FROM tokens ORDER BY added_at")]

    def create_token(self, name):
        tok = "coche_" + secrets.token_urlsafe(30)
        tid = new_id()
        self.x("INSERT INTO tokens(id,name,hash,added_at) VALUES(?,?,?,?)", (tid, _text(name, 60) or "token",
                                                                              hash_token(tok), utcnow()))
        return {"id": tid, "name": name, "token": tok}

    def check_token(self, tok):
        r = self.q1("SELECT id FROM tokens WHERE hash=?", (hash_token(tok),))
        if r:
            self.x("UPDATE tokens SET last_used_at=? WHERE id=?", (utcnow(), r["id"]))
        return bool(r)

    def delete_token(self, tid):
        self.x("DELETE FROM tokens WHERE id=?", (tid,))

    # ------------------------------------------------------------------ misc
    def _update(self, table, oid, sets):
        if not sets:
            return
        if table in ("tasks", "projects", "sections"):
            sets = {**sets, "updated_at": utcnow()}
        self.x(f"UPDATE {table} SET {', '.join(k + '=?' for k in sets)} WHERE id=?", (*sets.values(), oid))

    def export(self):
        dump = {"format": "coche-export", "version": 1, "exported_at": utcnow()}
        with self.lock:
            for table in ("projects", "sections", "labels", "tasks", "comments", "reminders", "filters", "activity"):
                dump[table] = [dict(r) for r in self.db.execute(f"SELECT * FROM {table}")]
            dump["settings"] = self.settings_public()
        return dump

    def import_dump(self, dump):
        if dump.get("format") != "coche-export":
            raise Invalid("not a Coche export")
        with self.tx():
            for table in ("projects", "sections", "labels", "tasks", "comments", "reminders", "filters", "activity"):
                cols = {r[1] for r in self.db.execute(f"PRAGMA table_info({table})")}
                self.db.execute(f"DELETE FROM {table}")
                for row in dump.get(table) or []:
                    row = {k: v for k, v in row.items() if k in cols}
                    self.db.execute(f"INSERT OR REPLACE INTO {table}({','.join(row)}) VALUES({','.join('?' * len(row))})",
                                    tuple(row.values()))
        if dump.get("settings"):
            self.set_settings({k: v for k, v in dump["settings"].items() if k in DEFAULT_SETTINGS})


def _text(v, n, keep_lines=False):
    if v is None:
        return ""
    s = str(v)
    if keep_lines:
        return s.replace("\r\n", "\n").strip()[:n]
    return " ".join(s.split())[:n]


def _num(v):
    return int(v) if isinstance(v, float) and v.is_integer() else v


def _color(c):
    return c if c in COLORS else "charcoal"


def _hm(v):
    if not v:
        return None
    t = dt.time.fromisoformat(str(v)[:5])
    return t.strftime("%H:%M")

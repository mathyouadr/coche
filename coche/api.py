"""HTTP API.

``/api/v1/...`` mirrors the Todoist unified API v1 (the subset a personal app
needs), so scripts written for Todoist work by changing the base URL.
``/api/coche/...`` holds what the web app needs on top (bootstrap, parse,
filters, reorder, stats, settings, export...).
"""
from __future__ import annotations

import datetime as dt
import json
import re

from . import dates, quickadd
from .filters import FilterError, compile_filter
from .store import Invalid, NotFound, Store

ID = r"([A-Za-z0-9_-]{1,64})"


class HTTPError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


def page(items, query):
    """Todoist-style cursor pagination over an already-built list."""
    try:
        limit = min(200, max(1, int(query.get("limit") or 50)))
        start = int(query.get("cursor") or 0)
    except ValueError:
        raise HTTPError(400, "invalid limit or cursor")
    chunk = items[start:start + limit]
    nxt = str(start + limit) if start + limit < len(items) else None
    return {"results": chunk, "next_cursor": nxt}


class API:
    def __init__(self, store: Store, app=None):
        self.s = store
        self.app = app                      # server.App, for notifiers / version / importer
        self.routes = []
        r = self.route
        # ---- Todoist v1 compatible
        r("GET", "/api/v1/projects", self.projects)
        r("GET", "/api/v1/projects/archived", self.projects_archived)
        r("POST", "/api/v1/projects", lambda b, q: self.s.add_project(b))
        r("GET", f"/api/v1/projects/{ID}", lambda b, q, i: self.s.project(i))
        r("POST", f"/api/v1/projects/{ID}", lambda b, q, i: self.s.update_project(i, b))
        r("DELETE", f"/api/v1/projects/{ID}", lambda b, q, i: self.s.delete_project(i))
        r("POST", f"/api/v1/projects/{ID}/archive", lambda b, q, i: self.s.archive_project(i, True))
        r("POST", f"/api/v1/projects/{ID}/unarchive", lambda b, q, i: self.s.archive_project(i, False))
        r("GET", "/api/v1/sections", lambda b, q: page(self.s.sections(q.get("project_id")), q))
        r("POST", "/api/v1/sections", lambda b, q: self.s.add_section(b))
        r("GET", f"/api/v1/sections/{ID}", lambda b, q, i: self.s.section(i))
        r("POST", f"/api/v1/sections/{ID}", lambda b, q, i: self.s.update_section(i, b))
        r("DELETE", f"/api/v1/sections/{ID}", lambda b, q, i: self.s.delete_section(i))
        r("GET", "/api/v1/labels", lambda b, q: page(self.s.labels(), q))
        r("POST", "/api/v1/labels", lambda b, q: self.s.add_label(b))
        r("GET", f"/api/v1/labels/{ID}", lambda b, q, i: self.s.label(i))
        r("POST", f"/api/v1/labels/{ID}", lambda b, q, i: self.s.update_label(i, b))
        r("DELETE", f"/api/v1/labels/{ID}", lambda b, q, i: self.s.delete_label(i))
        r("GET", "/api/v1/tasks", self.tasks)
        r("POST", "/api/v1/tasks", self.add_task)
        r("POST", "/api/v1/tasks/quick", self.quick)
        r("GET", "/api/v1/tasks/filter", self.filter_tasks)
        r("GET", "/api/v1/tasks/completed/by_completion_date", self.completed)
        r("GET", "/api/v1/tasks/completed", self.completed)
        r("GET", f"/api/v1/tasks/{ID}", lambda b, q, i: self.s.task(i))
        r("POST", f"/api/v1/tasks/{ID}", self.update_task)
        r("DELETE", f"/api/v1/tasks/{ID}", lambda b, q, i: self.s.delete_task(i))
        r("POST", f"/api/v1/tasks/{ID}/close", lambda b, q, i: self.close(i, b, compat=True))
        r("POST", f"/api/v1/tasks/{ID}/reopen", lambda b, q, i: self.s.reopen_task(i, b.get("previous_date")))
        r("POST", f"/api/v1/tasks/{ID}/move", lambda b, q, i: self.s.move_task(i, b))
        r("GET", "/api/v1/comments", self.comments)
        r("POST", "/api/v1/comments", lambda b, q: self.s.add_comment(b))
        r("POST", f"/api/v1/comments/{ID}", lambda b, q, i: self.s.update_comment(i, b))
        r("DELETE", f"/api/v1/comments/{ID}", lambda b, q, i: self.s.delete_comment(i))
        # ---- Coche extras
        r("GET", "/api/coche/bootstrap", self.bootstrap)
        r("POST", "/api/coche/parse", self.parse)
        r("POST", f"/api/coche/tasks/{ID}/close", lambda b, q, i: self.close(i, b))
        r("POST", f"/api/coche/tasks/{ID}/restore", lambda b, q, i: self.s.restore_task(i))
        r("POST", "/api/coche/reorder", self.reorder)
        r("POST", "/api/coche/reschedule", self.reschedule)
        r("GET", "/api/coche/filters", lambda b, q: self.s.filters())
        r("POST", "/api/coche/filters", lambda b, q: self._checked_filter(b) or self.s.add_filter(b))
        r("POST", f"/api/coche/filters/{ID}", lambda b, q, i: self._checked_filter(b) or self.s.update_filter(i, b))
        r("DELETE", f"/api/coche/filters/{ID}", lambda b, q, i: self.s.delete_filter(i))
        r("GET", "/api/coche/reminders", lambda b, q: self.s.reminders(q.get("task_id")))
        r("POST", "/api/coche/reminders", lambda b, q: self.s.add_reminder(b.get("task_id") or "", b))
        r("DELETE", f"/api/coche/reminders/{ID}", lambda b, q, i: self.s.delete_reminder(i))
        r("GET", "/api/coche/activity", self.activity)
        r("GET", "/api/coche/stats", lambda b, q: self.s.stats())
        r("GET", "/api/coche/settings", lambda b, q: self.s.settings_public())
        r("POST", "/api/coche/settings", lambda b, q: self.s.set_settings(b))
        r("GET", "/api/coche/export", lambda b, q: self.s.export())
        r("POST", "/api/coche/import", self.import_dump)
        r("POST", "/api/coche/import/todoist", self.import_todoist)
        r("GET", "/api/coche/tokens", lambda b, q: self.s.tokens())
        r("POST", "/api/coche/tokens", lambda b, q: self.s.create_token(b.get("name") or "token"))
        r("DELETE", f"/api/coche/tokens/{ID}", lambda b, q, i: self.s.delete_token(i))
        r("POST", "/api/coche/notify/test", self.notify_test)

    def route(self, method, pattern, fn):
        self.routes.append((method, re.compile("^" + pattern + "$"), fn))

    def handle(self, method, path, query, body):
        """-> (status, payload or None)."""
        allowed = False
        for m, rx, fn in self.routes:
            mt = rx.match(path)
            if not mt:
                continue
            allowed = True
            if m != method:
                continue
            try:
                out = fn(body, query, *mt.groups())
            except HTTPError as e:
                return e.status, {"error": e.message}
            except NotFound as e:
                return 404, {"error": f"{e} not found"}
            except (Invalid, FilterError) as e:
                return 400, {"error": str(e)}
            except (ValueError, TypeError, KeyError) as e:
                return 400, {"error": f"invalid request ({e})"}
            return (204, None) if out is None else (200, out)
        return (405, {"error": "method not allowed"}) if allowed else (404, {"error": "not found"})

    # ------------------------------------------------------------------ projects
    def projects(self, b, q):
        return page(self.s.projects(), q)

    def projects_archived(self, b, q):
        return page(self.s.projects(archived=True), q)

    # ------------------------------------------------------------------ tasks
    def tasks(self, b, q):
        where, args = ["checked=0"], []
        for key, col in (("project_id", "project_id"), ("section_id", "section_id"), ("parent_id", "parent_id")):
            if q.get(key):
                where.append(f"{col}=?")
                args.append(q[key])
        if q.get("ids"):
            ids = [x for x in q["ids"].split(",") if x][:200]
            where.append(f"id IN ({','.join('?' * len(ids))})")
            args += ids
        items = self.s.tasks(" AND ".join(where), tuple(args))
        if q.get("label"):
            items = [t for t in items if any(l.lower() == q["label"].lower() for l in t["labels"])]
        if q.get("filter"):
            items = self._filter(items, q["filter"])
        return page(items, q)

    def _ctx(self):
        projects = {p["id"]: p for p in self.s.projects()}
        sections = {s["id"]: s["name"] for s in self.s.sections()}
        return dict(today=self.s.today(), now=self.s.now(), projects=projects, sections=sections,
                    order=self.s.settings().get("date_order", "DMY"))

    def _filter(self, items, query):
        pred = compile_filter(query, **self._ctx())
        return [t for t in items if pred(t)]

    def _checked_filter(self, b):
        if "query" in b:
            compile_filter(b["query"], **self._ctx())
        return None

    def filter_tasks(self, b, q):
        query = q.get("query") or ""
        items = self.s.tasks()
        out = self._filter(items, query)
        out.sort(key=lambda t: ((t.get("due") or {}).get("date") or "9999", -t["priority"], t["child_order"]))
        return page(out, q)

    def completed(self, b, q):
        since = q.get("since") or (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
        until = q.get("until") or "9999"
        where, args = "checked=1 AND completed_at >= ? AND completed_at < ?", [_utc(since), _utc(until)]
        if q.get("project_id"):
            where += " AND project_id=?"
            args.append(q["project_id"])
        items = self.s.tasks(where, tuple(args), order="completed_at DESC")
        res = page(items, q)
        return {"items": res["results"], "next_cursor": res["next_cursor"]}

    def _resolve_names(self, p: quickadd.Parsed, body):
        project_id = body.get("project_id")
        section_id = body.get("section_id")
        if p.project:
            project_id = next((x["id"] for x in self.s.projects() if x["name"] == p.project), project_id)
        if p.section:
            secs = [s for s in self.s.sections(project_id or self.s.inbox_id()) if s["name"] == p.section]
            if secs:
                section_id = secs[0]["id"]
        return project_id, section_id

    def quick(self, b, q):
        text = " ".join(str(b.get("text") or "").split())
        if not text:
            raise Invalid("text is required")
        p = self._parse(text, b.get("project_id"))
        project_id, section_id = self._resolve_names(p, b)
        d = {"content": p.content, "priority": max(p.priority, int(b.get("priority") or 1)),
             "labels": list(dict.fromkeys(p.labels + list(b.get("labels") or []))),
             "description": b.get("note") or b.get("description") or "", "project_id": project_id,
             "section_id": section_id, "parent_id": b.get("parent_id")}
        if p.due and p.due.date:
            d.update(due_date=p.due.date.isoformat(), due_time=p.due.time,
                     rule=p.due.rule.to_dict() if p.due.rule else None)
            if p.due.duration:
                d["duration"] = p.due.duration
        elif b.get("due_string"):
            d["due_string"] = b["due_string"]
        elif b.get("due_date"):
            d["due_date"] = b["due_date"]
            if b.get("due_time"):
                d["due_time"] = b["due_time"]
        if p.deadline:
            d["deadline_date"] = p.deadline.isoformat()
        d["reminders"] = p.reminders + ([{"minutes_before": 0}] if b.get("auto_reminder") and p.due and p.due.time
                                        else [])
        t = self.s.add_task(d)
        if p.due and p.due.date:
            self.s.x("UPDATE tasks SET due_string=? WHERE id=?", (p.due.string[:120], t["id"]))
            t = self.s.task(t["id"])
        return t

    def _parse(self, text, project_id=None):
        projects = [x["name"] for x in self.s.projects()]
        sections = [s["name"] for s in self.s.sections()]
        return quickadd.parse(text, projects, sections, self.s.today(), self.s.now(),
                              self.s.settings().get("date_order", "DMY"))

    def parse(self, b, q):
        p = self._parse(str(b.get("text") or "")[:1000])
        out = p.to_dict()
        pid, sid = self._resolve_names(p, b)
        out["project_id"], out["section_id"] = pid, sid
        if p.due and p.due.rule:
            lang = b.get("lang") or self.s.settings().get("lang", "en")
            out["due"]["rule_text"] = dates.rule_to_text(p.due.rule, "fr" if str(lang).startswith("fr") else "en")
        return out

    def add_task(self, b, q):
        return self.s.add_task(b)

    def update_task(self, b, q, tid):
        out = self.s.update_task(tid, b)
        if any(k in b for k in ("project_id", "section_id", "parent_id")):
            mv = {k: b[k] for k in ("project_id", "section_id", "parent_id") if k in b}
            out = self.s.move_task(tid, mv)
        return out

    def close(self, tid, b, compat=False):
        res = self.s.close_task(tid)
        return None if compat else res

    def reorder(self, b, q):
        ids = [str(x) for x in (b.get("ids") or [])][:500]
        kind = b.get("type", "tasks")
        if kind != "tasks":
            if kind not in ("projects", "sections", "labels", "filters"):
                raise Invalid("unknown type")
            self.s.reorder_objects(kind, ids)
            return {"ok": True}
        move = "section_id" in b or "parent_id" in b or "project_id" in b
        return {"tasks": self.s.reorder(ids, b.get("project_id"), b.get("section_id"), b.get("parent_id"), move)}

    def reschedule(self, b, q):
        """Move many tasks to one day at once ("Reschedule overdue to today")."""
        ids = [str(x) for x in (b.get("ids") or [])][:500]
        day = dt.date.fromisoformat(str(b.get("date"))).isoformat()
        return {"tasks": [self.s.update_task(i, {"due_date": day, "due_time": self.s.task_row(i)["due_time"]})
                          for i in ids]}

    def comments(self, b, q):
        if q.get("task_id"):
            return page(self.s.comments(task_id=q["task_id"]), q)
        if q.get("project_id"):
            return page(self.s.comments(project_id=q["project_id"]), q)
        raise Invalid("task_id or project_id is required")

    def activity(self, b, q):
        ev = [x for x in (q.get("event_type") or "").split(",") if x]
        return {"events": self.s.activity(q.get("since"), q.get("until"), ev or None, int(q.get("limit") or 100))}

    def bootstrap(self, b, q):
        s = self.s
        return {"projects": s.projects(), "archived_projects": s.projects(archived=True), "sections": s.sections(),
                "labels": s.labels(), "filters": s.filters(), "tasks": s.tasks(), "reminders": s.reminders(),
                "settings": s.settings_public(), "stats": s.stats(), "today": s.today().isoformat(),
                "now": s.now().isoformat(timespec="minutes"),
                "app": self.app.info() if self.app else {}}

    def import_dump(self, b, q):
        self.s.import_dump(b)
        return {"ok": True}

    def import_todoist(self, b, q):
        from .todoist_import import import_from_todoist
        tok = str(b.get("token") or "").strip()
        if not tok:
            raise Invalid("a Todoist API token is required")
        return import_from_todoist(self.s, tok, completed=bool(b.get("completed", True)))

    def notify_test(self, b, q):
        if not self.app:
            raise Invalid("no notifier")
        return self.app.notifier.test()


def _utc(s):
    """Accept '2026-11-20', '2026-11-20T10:00:00Z', '...+01:00' -> comparable UTC string."""
    s = str(s)
    if s == "9999":
        return s
    if len(s) == 10:
        s += "T00:00:00"
    x = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if x.tzinfo is None:
        x = x.replace(tzinfo=dt.timezone.utc)
    return x.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def dumps(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode()

"""Import everything from a Todoist account (unified API v1), in one go.

    python -m coche import-todoist            # reads TODOIST_API_TOKEN

Projects, sections, labels, open tasks (with subtasks, recurrences, deadlines,
durations), comments and the last 3 months of completed tasks (so your streak
and stats survive the move). The token is used once and never stored.
Running it again only adds what is new.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.parse
import urllib.request

from . import dates
from .store import Store

API = "https://api.todoist.com/api/v1/"


class TodoistClient:
    def __init__(self, token, base=API):
        self.token, self.base = token, base

    def get(self, path, **params):
        url = self.base + path + ("?" + urllib.parse.urlencode(params) if params else "")
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + self.token})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)

    def all(self, path, key="results", **params):
        out, cursor = [], None
        for _ in range(200):
            q = dict(params, limit=200)
            if cursor:
                q["cursor"] = cursor
            d = self.get(path, **q)
            out += d.get(key) or []
            cursor = d.get("next_cursor")
            if not cursor:
                break
        return out


def _local(store: Store, raw: str):
    """Todoist date -> (YYYY-MM-DD, HH:MM | None) in the store's zone."""
    if "T" not in raw:
        return raw[:10], None
    x = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if x.tzinfo:
        x = x.astimezone(store.tz) if store.tz else x.astimezone()
    return x.date().isoformat(), x.strftime("%H:%M")


def import_from_todoist(store: Store, token: str, completed=True, client=None) -> dict:
    c = client or TodoistClient(token)
    known = json.loads((store.q1("SELECT value FROM settings WHERE key='_todoist_ids'") or {"value": "{}"})["value"])
    rep = {"projects": 0, "sections": 0, "labels": 0, "tasks": 0, "completed": 0, "comments": 0, "warnings": []}

    def remember(tid, cid):
        known[tid] = cid

    # projects (parents first)
    projects = sorted(c.all("projects"), key=lambda p: (p.get("parent_id") is not None, p.get("child_order", 0)))
    for p in projects:
        if p["id"] in known:
            continue
        if p.get("inbox_project") or p.get("is_inbox_project"):
            remember(p["id"], store.inbox_id())
            continue
        new = store.add_project({"name": p["name"], "color": p.get("color"), "is_favorite": p.get("is_favorite"),
                                 "view_style": p.get("view_style"), "child_order": p.get("child_order", 0),
                                 "description": p.get("description") or ""})
        remember(p["id"], new["id"])
        rep["projects"] += 1
    for p in projects:
        if p.get("parent_id") and p["parent_id"] in known and not (p.get("inbox_project") or p.get("is_inbox_project")):
            store.update_project(known[p["id"]], {"parent_id": known[p["parent_id"]]})

    for s in c.all("sections"):
        if s["id"] in known or s.get("project_id") not in known:
            continue
        new = store.add_section({"name": s["name"], "project_id": known[s["project_id"]],
                                 "order": s.get("section_order", s.get("order", 0))})
        remember(s["id"], new["id"])
        rep["sections"] += 1

    existing = {l["name"].lower() for l in store.labels()}
    for l in c.all("labels"):
        if l["name"].lower() in existing:
            continue
        store.add_label({"name": l["name"], "color": l.get("color"), "is_favorite": l.get("is_favorite")})
        rep["labels"] += 1

    def add(t, checked=False):
        if t["id"] in known:
            return
        d = {"content": t["content"], "description": t.get("description") or "", "priority": t.get("priority", 1),
             "labels": t.get("labels") or [], "project_id": known.get(t.get("project_id")),
             "section_id": known.get(t.get("section_id")), "parent_id": known.get(t.get("parent_id")),
             "child_order": t.get("child_order", 0), "_added_at": t.get("added_at")}
        due = t.get("due")
        if due and due.get("date"):
            day, hm = _local(store, due.get("datetime") or due["date"])
            d.update(due_date=day, due_time=hm, due_lang=due.get("lang") or "en")
            if due.get("is_recurring"):
                parsed = dates.parse_due(due.get("string") or "", store.today(), store.now(),
                                         store.settings().get("date_order", "DMY"))
                if parsed and parsed.rule:
                    d["rule"] = parsed.rule.to_dict()
                else:
                    rep["warnings"].append(f"recurrence not understood, kept as a one-off date: "
                                           f"{t['content'][:60]!r} ({due.get('string')!r})")
        if t.get("deadline") and t["deadline"].get("date"):
            d["deadline_date"] = t["deadline"]["date"][:10]
        if t.get("duration"):
            amt, unit = t["duration"].get("amount"), t["duration"].get("unit")
            d["duration"] = amt * (1440 if unit == "day" else 1) if amt else None
        new = store.add_task(d, log=False)
        if due and due.get("string") and d.get("rule"):
            store.x("UPDATE tasks SET due_string=? WHERE id=?", (due["string"][:120], new["id"]))
        if t.get("is_collapsed"):
            store.update_task(new["id"], {"is_collapsed": True})
        if checked:
            stamp = t.get("completed_at") or store_now()
            store.x("UPDATE tasks SET checked=1, completed_at=? WHERE id=?", (stamp, new["id"]))
            store.x("INSERT INTO activity(at,event_type,object_id,project_id,content,extra) VALUES(?,?,?,?,?,?)",
                    (stamp, "completed", new["id"], new["project_id"], new["content"], '{"imported": true}'))
        remember(t["id"], new["id"])
        if (t.get("note_count") or 0) > 0:
            try:
                for cm in c.all("comments", task_id=t["id"]):
                    store.add_comment({"task_id": new["id"], "content": cm.get("content") or "",
                                       "_posted_at": cm.get("posted_at")})
                    rep["comments"] += 1
            except Exception as e:
                rep["warnings"].append(f"comments of {t['content'][:40]!r} skipped ({type(e).__name__})")
        rep["completed" if checked else "tasks"] += 1

    def depth_sorted(tasks):
        ids = {t["id"]: t for t in tasks}

        def depth(t, n=0):
            p = ids.get(t.get("parent_id"))
            return depth(p, n + 1) if p and n < 20 else n
        return sorted(tasks, key=lambda t: (depth(t), t.get("child_order", 0)))

    for t in depth_sorted(c.all("tasks")):
        add(t)

    if completed:
        until = dt.datetime.now(dt.timezone.utc)
        try:
            done = []
            for _ in range(3):                      # the API answers windows of up to ~3 months
                since = until - dt.timedelta(days=30)
                done += c.all("tasks/completed/by_completion_date", key="items",
                              since=since.strftime("%Y-%m-%dT%H:%M:%SZ"), until=until.strftime("%Y-%m-%dT%H:%M:%SZ"))
                until = since
            for t in depth_sorted(done):
                add(t, checked=True)
        except Exception as e:
            rep["warnings"].append(f"completed tasks skipped ({type(e).__name__})")

    store.x("INSERT OR REPLACE INTO settings(key, value) VALUES('_todoist_ids', ?)", (json.dumps(known),))
    return rep


def store_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

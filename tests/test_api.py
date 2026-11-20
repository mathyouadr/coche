import datetime as dt
import json
import threading
import unittest
import urllib.error
import urllib.request

from coche.config import Config
from coche.server import make_server
from coche.store import Store

NOW = dt.datetime(2026, 11, 20, 10, 0)     # Friday


class Client:
    def __init__(self, base, token=None):
        self.base, self.token, self.cookie = base, token, None

    def call(self, method, path, body=None, headers=None):
        h = {"Content-Type": "application/json"} if body is not None else {}
        if self.token:
            h["Authorization"] = "Bearer " + self.token
        if self.cookie:
            h["Cookie"] = self.cookie
        h.update(headers or {})
        req = urllib.request.Request(self.base + path, method=method, headers=h,
                                     data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                raw = r.read()
                if r.headers.get("Set-Cookie"):
                    self.cookie = r.headers["Set-Cookie"].split(";")[0]
                return r.status, (json.loads(raw) if raw and "json" in (r.headers.get("Content-Type") or "") else raw)
        except urllib.error.HTTPError as e:
            raw = e.read()
            return e.code, (json.loads(raw) if raw else None)


class Base(unittest.TestCase):
    config = {}

    def setUp(self):
        self.store = Store(":memory:", clock=lambda: NOW)
        cfg = Config(host="127.0.0.1", port=0, **self.config)
        self.httpd, self.app = make_server(cfg, self.store)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.c = Client(f"http://127.0.0.1:{self.httpd.server_address[1]}{cfg.base_path}")

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.store.db.close()


class TodoistCompatTest(Base):
    def test_agenda_style_flow(self):
        """The exact calls a Todoist script makes: quick add, list with cursor, close, reopen, postpone."""
        st, t = self.c.call("POST", "/api/v1/tasks/quick", {"text": "Réviser SISR demain 14h p2"})
        self.assertEqual(st, 200)
        self.assertEqual(t["content"], "Réviser SISR")
        self.assertEqual(t["due"]["date"], "2026-11-21T14:00:00")
        self.assertEqual(t["priority"], 3)
        st, res = self.c.call("GET", "/api/v1/tasks?limit=200")
        self.assertEqual(len(res["results"]), 1)
        self.assertIsNone(res["next_cursor"])
        st, body = self.c.call("POST", f"/api/v1/tasks/{t['id']}/close")
        self.assertEqual((st, body), (204, b""))
        self.assertEqual(self.c.call("GET", "/api/v1/tasks")[1]["results"], [])
        self.assertEqual(self.c.call("POST", f"/api/v1/tasks/{t['id']}/reopen")[0], 200)
        st, t2 = self.c.call("POST", f"/api/v1/tasks/{t['id']}", {"due_date": "2026-11-25"})
        self.assertEqual(t2["due"]["date"], "2026-11-25")
        st, projects = self.c.call("GET", "/api/v1/projects?limit=200")
        self.assertEqual(projects["results"][0]["name"], "Inbox")

    def test_create_with_due_string_and_labels(self):
        st, t = self.c.call("POST", "/api/v1/tasks", {"content": "DS de maths", "due_string": "jeudi", "due_lang": "fr",
                                                     "labels": ["échéance"], "priority": 4})
        self.assertEqual(st, 200)
        self.assertEqual(t["due"]["date"], "2026-11-26")
        self.assertEqual(t["labels"], ["échéance"])
        self.assertEqual([l["name"] for l in self.c.call("GET", "/api/v1/labels")[1]["results"]], ["échéance"])
        st, err = self.c.call("POST", "/api/v1/tasks", {"content": "x", "due_string": "quand je veux"})
        self.assertEqual(st, 400)

    def test_due_datetime_utc(self):
        st, t = self.c.call("POST", "/api/v1/tasks", {"content": "Call", "due_datetime": "2026-11-21T13:00:00Z"})
        self.assertTrue(t["due"]["date"].startswith("2026-11-21T"))

    def test_pagination(self):
        for i in range(5):
            self.c.call("POST", "/api/v1/tasks", {"content": f"t{i}"})
        st, p1 = self.c.call("GET", "/api/v1/tasks?limit=2")
        st, p2 = self.c.call("GET", f"/api/v1/tasks?limit=2&cursor={p1['next_cursor']}")
        st, p3 = self.c.call("GET", f"/api/v1/tasks?limit=2&cursor={p2['next_cursor']}")
        self.assertEqual([len(p["results"]) for p in (p1, p2, p3)], [2, 2, 1])
        self.assertIsNone(p3["next_cursor"])

    def test_recurring_completion(self):
        st, t = self.c.call("POST", "/api/v1/tasks/quick", {"text": "Sport tous les lundis et jeudis"})
        self.assertEqual(t["due"]["date"], "2026-11-23")
        self.assertTrue(t["due"]["is_recurring"])
        st, res = self.c.call("POST", f"/api/coche/tasks/{t['id']}/close")
        self.assertTrue(res["recurring"])
        self.assertEqual(res["task"]["due"]["date"], "2026-11-26")
        self.assertFalse(res["task"]["checked"])
        # undo
        st, back = self.c.call("POST", f"/api/v1/tasks/{t['id']}/reopen", {"previous_date": res["previous_date"]})
        self.assertEqual(back["due"]["date"], "2026-11-23")

    def test_subtasks_close_and_reopen(self):
        p = self.c.call("POST", "/api/v1/tasks", {"content": "Parent"})[1]
        k = self.c.call("POST", "/api/v1/tasks", {"content": "Child", "parent_id": p["id"]})[1]
        self.c.call("POST", f"/api/v1/tasks/{p['id']}/close")
        self.assertEqual(self.c.call("GET", "/api/v1/tasks")[1]["results"], [])
        self.c.call("POST", f"/api/v1/tasks/{k['id']}/reopen")
        self.assertEqual(len(self.c.call("GET", "/api/v1/tasks")[1]["results"]), 2)   # parent reopened too

    def test_filter(self):
        self.c.call("POST", "/api/v1/tasks/quick", {"text": "A aujourd'hui p1"})
        self.c.call("POST", "/api/v1/tasks", {"content": "B en retard", "due_date": "2026-11-18"})
        self.c.call("POST", "/api/v1/tasks", {"content": "C plus tard", "due_date": "2026-12-18"})
        self.c.call("POST", "/api/v1/tasks/quick", {"text": "D @courses"})
        q = lambda s: [t["content"] for t in self.c.call("GET", "/api/v1/tasks/filter?query=" +
                                                        urllib.request.quote(s))[1]["results"]]
        self.assertEqual(q("today | overdue"), ["B en retard", "A"])
        self.assertEqual(q("aujourd'hui"), ["A"])
        self.assertEqual(q("p1"), ["A"])
        self.assertEqual(q("@courses"), ["D"])
        self.assertEqual(q("no date"), ["D"])
        self.assertEqual(q("!no date & !p1"), ["B en retard", "C plus tard"])
        self.assertEqual(q("30 days"), ["A", "C plus tard"])
        self.assertEqual(q("search: plus"), ["C plus tard"])
        self.assertEqual(self.c.call("GET", "/api/v1/tasks/filter?query=(today")[0], 400)

    def test_projects_sections_move(self):
        p = self.c.call("POST", "/api/v1/projects", {"name": "Cours", "color": "blue"})[1]
        s = self.c.call("POST", "/api/v1/sections", {"name": "Examens", "project_id": p["id"]})[1]
        st, t = self.c.call("POST", "/api/v1/tasks/quick", {"text": "Réviser #Cours /Examens"})
        self.assertEqual((t["project_id"], t["section_id"], t["content"]), (p["id"], s["id"], "Réviser"))
        inbox = self.store.inbox_id()
        st, t = self.c.call("POST", f"/api/v1/tasks/{t['id']}/move", {"project_id": inbox})
        self.assertEqual((t["project_id"], t["section_id"]), (inbox, None))
        self.assertEqual(self.c.call("DELETE", f"/api/v1/projects/{inbox}")[0], 400)
        self.assertEqual(self.c.call("DELETE", f"/api/v1/projects/{p['id']}")[0], 204)

    def test_comments_and_delete_restore(self):
        t = self.c.call("POST", "/api/v1/tasks", {"content": "Note me"})[1]
        self.c.call("POST", "/api/v1/comments", {"task_id": t["id"], "content": "hello"})
        self.assertEqual(self.c.call("GET", f"/api/v1/tasks/{t['id']}")[1]["note_count"], 1)
        self.assertEqual(self.c.call("DELETE", f"/api/v1/tasks/{t['id']}")[0], 204)
        self.assertEqual(self.c.call("GET", f"/api/v1/tasks/{t['id']}")[0], 404)
        self.c.call("POST", f"/api/coche/tasks/{t['id']}/restore")
        self.assertEqual(self.c.call("GET", f"/api/v1/tasks/{t['id']}")[0], 200)

    def test_completed_endpoint_and_stats(self):
        t = self.c.call("POST", "/api/v1/tasks", {"content": "Done"})[1]
        self.c.call("POST", f"/api/v1/tasks/{t['id']}/close")
        st, res = self.c.call("GET", "/api/v1/tasks/completed/by_completion_date?since=2000-01-01T00:00:00Z")
        self.assertEqual([x["content"] for x in res["items"]], ["Done"])
        st, stats = self.c.call("GET", "/api/coche/stats")
        self.assertEqual(stats["completed_total"], 1)


class CocheApiTest(Base):
    def test_bootstrap_parse_reorder(self):
        st, b = self.c.call("GET", "/api/coche/bootstrap")
        self.assertEqual(st, 200)
        self.assertIn("settings", b)
        st, p = self.c.call("POST", "/api/coche/parse", {"text": "Payer loyer tous les 5 p1"})
        self.assertEqual(p["content"], "Payer loyer")
        self.assertTrue(p["due"]["is_recurring"])
        self.assertEqual(p["due"]["rule_text"], "every 5th")
        ids = [self.c.call("POST", "/api/v1/tasks", {"content": c})[1]["id"] for c in "abc"]
        self.c.call("POST", "/api/coche/reorder", {"ids": list(reversed(ids))})
        self.assertEqual([t["content"] for t in self.c.call("GET", "/api/v1/tasks")[1]["results"]], ["c", "b", "a"])

    def test_filters_crud_validates(self):
        self.assertEqual(self.c.call("POST", "/api/coche/filters", {"name": "x", "query": "(today"})[0], 400)
        st, f = self.c.call("POST", "/api/coche/filters", {"name": "Urgent", "query": "p1 | overdue"})
        self.assertEqual(st, 200)

    def test_reminder_fires_once(self):
        t = self.c.call("POST", "/api/v1/tasks/quick", {"text": "Appeler à 10h !0m"})[1]
        due = self.store.due_reminders()
        self.assertEqual(len(due), 1)
        self.store.mark_sent(due[0][0], due[0][2])
        self.assertEqual(self.store.due_reminders(), [])

    def test_ics_and_pages(self):
        self.c.call("POST", "/api/v1/tasks/quick", {"text": "Sport tous les lundis 18h"})
        st, body = self.c.call("GET", "/calendar.ics")
        self.assertIn(b"RRULE:FREQ=WEEKLY;BYDAY=MO", body)
        st, html = self.c.call("GET", "/today")
        self.assertEqual(st, 200)
        self.assertIn(b"<html", html)
        self.assertEqual(self.c.call("GET", "/static/../server.py")[0], 404)


class PasswordModeTest(Base):
    config = {"password": "s3cret", "base_path": "/tasks"}

    def test_login_flow(self):
        self.assertEqual(self.c.call("GET", "/api/v1/tasks")[0], 401)
        self.assertEqual(self.c.call("POST", "/api/coche/login", {"password": "nope"})[0], 401)
        self.assertEqual(self.c.call("POST", "/api/coche/login", {"password": "s3cret"})[0], 200)
        self.assertEqual(self.c.call("GET", "/api/v1/tasks")[0], 200)
        # cookie auth refuses non-JSON posts (CSRF) and foreign origins
        st, _ = self.c.call("POST", "/api/v1/tasks", None, {"Content-Type": "text/plain", "Content-Length": "0"})
        self.assertEqual(self.c.call("POST", "/api/v1/tasks", {"content": "x"},
                                     {"Origin": "http://evil.example"})[0], 403)

    def test_token(self):
        tok = self.store.create_token("script")["token"]
        c = Client(self.c.base, token=tok)
        self.assertEqual(c.call("GET", "/api/v1/projects")[0], 200)
        c.token = "wrong"
        self.assertEqual(c.call("GET", "/api/v1/projects")[0], 401)

    def test_ics_key(self):
        self.assertEqual(self.c.call("GET", "/calendar.ics")[0], 401)
        key = self.store.secret("ics_key")
        self.assertEqual(self.c.call("GET", "/calendar.ics?key=" + key)[0], 200)


if __name__ == "__main__":
    unittest.main()

"""Command line.

    coche                       start the server (same as `coche serve`)
    coche add "Pay rent every 5th #Home p1"
    coche list [filter]         e.g. coche list "today | overdue"
    coche import-todoist        import a Todoist account (TODOIST_API_TOKEN)
    coche token create NAME     API token for scripts (shown once)
    coche export > backup.json  /  coche import backup.json
    coche demo [--lang fr]      sample tasks in an empty database
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .config import Config


def _store(cfg):
    from .server import App
    return App(cfg).store


def main(argv=None):
    ap = argparse.ArgumentParser(prog="coche", description="Coche, a self-hosted Todoist alternative.")
    ap.add_argument("--env", help="path to a .env file (default: ./.env)")
    ap.add_argument("--version", action="version", version=f"coche {__version__}")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("serve", help="start the web server")
    s.add_argument("--host")
    s.add_argument("--port", type=int)
    a = sub.add_parser("add", help="quick add a task")
    a.add_argument("text", nargs="+")
    l = sub.add_parser("list", help="list open tasks, optionally filtered")
    l.add_argument("query", nargs="*")
    l.add_argument("--json", action="store_true")
    t = sub.add_parser("token", help="manage API tokens")
    t.add_argument("action", choices=["create", "list", "revoke"])
    t.add_argument("name", nargs="?")
    i = sub.add_parser("import-todoist", help="import from Todoist (uses $TODOIST_API_TOKEN)")
    i.add_argument("--no-completed", action="store_true")
    dm = sub.add_parser("demo", help="fill an empty database with sample tasks")
    dm.add_argument("--lang", default="en", choices=["en", "fr"])
    sub.add_parser("export", help="print a JSON backup")
    im = sub.add_parser("import", help="restore a JSON backup (replaces everything)")
    im.add_argument("file")
    args = ap.parse_args(argv)
    cfg = Config.from_env(args.env)

    if args.cmd in (None, "serve"):
        if getattr(args, "host", None):
            cfg.host = args.host
        if getattr(args, "port", None):
            cfg.port = args.port
        from .server import serve
        return serve(cfg)

    store = _store(cfg)
    from .api import API
    api = API(store)
    if args.cmd == "add":
        st, t = api.handle("POST", "/api/v1/tasks/quick", {}, {"text": " ".join(args.text)})
        if st != 200:
            sys.exit(t["error"])
        due = (t.get("due") or {}).get("date") or "no date"
        print(f"✓ {t['content']}  ({due})  id={t['id']}")
    elif args.cmd == "list":
        q = " ".join(args.query)
        path = "/api/v1/tasks/filter" if q else "/api/v1/tasks"
        st, res = api.handle("GET", path, {"query": q, "limit": "200"}, {})
        if st != 200:
            sys.exit(res["error"])
        items = res["results"]
        if args.json:
            print(json.dumps(items, ensure_ascii=False, indent=2))
        for x in items if not args.json else []:
            due = (x.get("due") or {}).get("date", "")
            pr = {4: "p1", 3: "p2", 2: "p3"}.get(x["priority"], "  ")
            print(f"{pr}  {due[:16]:16}  {x['content']}" + ("  @" + " @".join(x["labels"]) if x["labels"] else ""))
    elif args.cmd == "token":
        if args.action == "create":
            tok = store.create_token(args.name or "cli")
            print(tok["token"])
            print("Shown once - store it somewhere safe.", file=sys.stderr)
        elif args.action == "list":
            for x in store.tokens():
                print(x["id"], x["name"], "last used:", x["last_used_at"] or "never")
        else:
            store.delete_token(args.name or "")
            print("revoked")
    elif args.cmd == "import-todoist":
        tok = os.environ.get("TODOIST_API_TOKEN", "")
        if not tok:
            sys.exit("Set TODOIST_API_TOKEN (Todoist > Settings > Integrations > Developer).")
        from .todoist_import import import_from_todoist
        rep = import_from_todoist(store, tok, completed=not args.no_completed)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    elif args.cmd == "demo":
        from .demo import seed
        seed(store, args.lang)
        print("Sample tasks added. Start the server with: coche")
    elif args.cmd == "export":
        print(json.dumps(store.export(), ensure_ascii=False))
    elif args.cmd == "import":
        with open(args.file, encoding="utf-8") as f:
            store.import_dump(json.load(f))
        print("restored")


if __name__ == "__main__":
    main()

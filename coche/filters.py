"""Filter queries, Todoist style.

    today | overdue          (p1 | p2) & #Work         @errand & !no date
    7 days & !@waiting       search: invoice           date before: next monday

Operators: ``|`` or, ``&`` and, ``!`` not, parentheses, ``,`` behaves like ``|``.
French words work too: ``aujourd'hui | en retard``, ``7 jours``, ``sans date``.
An unknown word is a text search, so typing "invoice" just finds invoices.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import re

from . import dates


class FilterError(ValueError):
    pass


def tokenize(q: str):
    out, buf, depth = [], "", 0
    for c in q:
        if c in "|&(),":
            if buf.strip():
                out.append(("term", buf.strip()))
            buf = ""
            out.append(("op", "|" if c == "," else c))
        elif c == "!" and not buf.strip():
            out.append(("op", "!"))
        else:
            buf += c
    if buf.strip():
        out.append(("term", buf.strip()))
    return out


class _Parser:
    def __init__(self, toks, term):
        self.t, self.i, self.term = toks, 0, term

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def eat(self, v=None):
        tok = self.peek()
        if v is not None and tok[1] != v:
            raise FilterError(f"expected {v!r}")
        self.i += 1
        return tok

    def parse(self):
        f = self.or_()
        if self.i != len(self.t):
            raise FilterError("unexpected " + repr(self.peek()[1]))
        return f

    def or_(self):
        parts = [self.and_()]
        while self.peek() == ("op", "|"):
            self.eat()
            parts.append(self.and_())
        return parts[0] if len(parts) == 1 else (lambda t, ps=parts: any(p(t) for p in ps))

    def and_(self):
        parts = [self.unary()]
        while self.peek() == ("op", "&"):
            self.eat()
            parts.append(self.unary())
        return parts[0] if len(parts) == 1 else (lambda t, ps=parts: all(p(t) for p in ps))

    def unary(self):
        kind, v = self.peek()
        if (kind, v) == ("op", "!"):
            self.eat()
            inner = self.unary()
            return lambda t: not inner(t)
        if (kind, v) == ("op", "("):
            self.eat()
            inner = self.or_()
            self.eat(")")
            return inner
        if kind == "term":
            self.eat()
            return self.term(v)
        raise FilterError("empty filter" if kind is None else "unexpected " + repr(v))


def compile_filter(query: str, *, today: dt.date, now: dt.datetime, projects: dict, sections: dict,
                   order: str = "DMY"):
    """-> predicate(task_dict). ``projects``: id -> {name, parent_id}; ``sections``: id -> name."""
    if not (query or "").strip():
        raise FilterError("empty filter")

    def day(t):
        d = (t.get("due") or {}).get("date")
        return dt.date.fromisoformat(d[:10]) if d else None

    def tm(t):
        d = (t.get("due") or {}).get("date") or ""
        return d[11:16] if "T" in d else None

    def descendants(pid):
        out, todo = {pid}, [pid]
        while todo:
            cur = todo.pop()
            for k, p in projects.items():
                if p.get("parent_id") == cur and k not in out:
                    out.add(k)
                    todo.append(k)
        return out

    def by_name(name, table):
        f = dates.fold(name.strip())
        return {k for k, v in table.items() if fnmatch.fnmatch(dates.fold(v if isinstance(v, str) else v["name"]), f)}

    def term(raw: str):
        w = dates.fold(raw.strip())
        w = " ".join(w.split())
        if w in ("today", "aujourd'hui", "aujourdhui", "auj", "tod"):
            return lambda t: day(t) == today
        if w in ("tomorrow", "demain", "tom"):
            return lambda t: day(t) == today + dt.timedelta(days=1)
        if w in ("yesterday", "hier"):
            return lambda t: day(t) == today - dt.timedelta(days=1)
        if w in ("overdue", "od", "en retard", "retard"):
            hm = now.strftime("%H:%M")
            return lambda t: bool(day(t)) and (day(t) < today or (day(t) == today and (tm(t) or "99") < hm))
        if w in ("no date", "sans date", "pas de date"):
            return lambda t: day(t) is None
        if w in ("no time", "sans heure"):
            return lambda t: day(t) is not None and tm(t) is None
        if w in ("recurring", "recurrent", "recurrente", "recurrentes"):
            return lambda t: bool((t.get("due") or {}).get("is_recurring"))
        if w in ("subtask", "subtasks", "sous-tache", "sous-taches"):
            return lambda t: bool(t.get("parent_id"))
        if w in ("deadline", "echeance", "has deadline"):
            return lambda t: bool(t.get("deadline"))
        if w in ("no labels", "no label", "sans etiquette", "sans etiquettes"):
            return lambda t: not t.get("labels")
        if w in ("all", "tout", "toutes", "*"):
            return lambda t: True
        if w in ("no priority", "sans priorite"):
            return lambda t: t.get("priority", 1) == 1
        m = re.fullmatch(r"(?:next\s+|les\s+)?(\d{1,3})\s+(?:days|day|jours|jour|prochains\s+jours)(?:\s+prochains)?", w)
        if m:
            n = int(m.group(1))
            return lambda t: day(t) is not None and today <= day(t) < today + dt.timedelta(days=n)
        m = re.fullmatch(r"p([1-4])", w)
        if m:
            p = 5 - int(m.group(1))
            return lambda t: t.get("priority", 1) == p
        m = re.fullmatch(r"(date|deadline|echeance)\s*(before|after|avant|apres)?\s*:\s*(.+)", w)
        if m:
            d = dates.parse_due(m.group(3), today, now, order)
            if not d or not d.date:
                raise FilterError("unknown date " + repr(m.group(3)))
            ref, op = d.date, (m.group(2) or "on")
            get = day if m.group(1) == "date" else (lambda t: dt.date.fromisoformat(t["deadline"]["date"])
                                                    if t.get("deadline") else None)
            if op in ("before", "avant"):
                return lambda t: get(t) is not None and get(t) < ref
            if op in ("after", "apres"):
                return lambda t: get(t) is not None and get(t) > ref
            return lambda t: get(t) == ref
        m = re.fullmatch(r"(?:search|recherche|cherche)\s*:\s*(.+)", w)
        if m or not re.match(r"[#@/]", w):
            needle = (m.group(1) if m else w).strip()
            return lambda t: needle in dates.fold(t.get("content", "") + " " + (t.get("description") or ""))
        if w.startswith("##"):
            ids = set().union(*[descendants(p) for p in by_name(raw.strip()[2:], projects)] or [set()])
            return lambda t: t.get("project_id") in ids
        if w.startswith("#"):
            ids = by_name(raw.strip()[1:], projects)
            return lambda t: t.get("project_id") in ids
        if w.startswith("/"):
            ids = by_name(raw.strip()[1:], sections)
            return lambda t: t.get("section_id") in ids
        if w.startswith("@"):
            pat = dates.fold(raw.strip()[1:])
            return lambda t: any(fnmatch.fnmatch(dates.fold(l), pat) for l in t.get("labels") or [])
        raise FilterError("unknown term " + repr(raw))

    return _Parser(tokenize(query), term).parse()

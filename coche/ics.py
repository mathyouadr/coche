"""iCalendar feed of dated tasks, to subscribe from any calendar app."""
from __future__ import annotations

import datetime as dt

from .dates import Rule


def _esc(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    out, b = [], line.encode()
    while len(b) > 74:
        cut = 74
        while cut and (b[cut] & 0xC0) == 0x80:      # don't split a UTF-8 character
            cut -= 1
        out.append(b[:cut].decode())
        b = b" " + b[cut:]
    out.append(b.decode())
    return "\r\n".join(out)


RRULE_DAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def rrule(rule: Rule) -> str | None:
    if rule.from_completion:
        return None
    if rule.freq == "daily" and rule.workdays:
        return "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
    parts = ["FREQ=" + rule.freq.upper()]
    if rule.interval and rule.interval > 1:
        parts.append(f"INTERVAL={rule.interval}")
    if rule.weekdays:
        parts.append("BYDAY=" + ",".join(RRULE_DAYS[d] for d in rule.weekdays))
    if rule.monthday and rule.freq in ("monthly", "yearly"):
        parts.append(f"BYMONTHDAY={rule.monthday}")
    if rule.month and rule.freq == "yearly":
        parts.append(f"BYMONTH={rule.month}")
    return ";".join(parts)


def build(store, title="Coche") -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    projects = {p["id"]: p["name"] for p in store.projects()}
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Coche//Tasks//EN", "CALSCALE:GREGORIAN",
             f"X-WR-CALNAME:{_esc(title)}", "X-PUBLISHED-TTL:PT15M", "REFRESH-INTERVAL;VALUE=DURATION:PT15M"]
    for t in store.tasks():
        due = t.get("due")
        if not due:
            continue
        d = due["date"]
        lines += ["BEGIN:VEVENT", f"UID:{t['id']}@coche", f"DTSTAMP:{stamp}", f"SUMMARY:{_esc(t['content'])}"]
        if "T" in d:
            start = dt.datetime.fromisoformat(d)
            mins = (t.get("duration") or {}).get("amount") or 30
            end = start + dt.timedelta(minutes=mins)
            lines += [f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}", f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}"]
        else:
            day = dt.date.fromisoformat(d)
            lines += [f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
                      f"DTEND;VALUE=DATE:{(day + dt.timedelta(days=1)).strftime('%Y%m%d')}"]
        rule = Rule.from_dict(t.get("rule"))
        if rule and rrule(rule):
            lines.append("RRULE:" + rrule(rule))
        desc = t.get("description") or ""
        if projects.get(t["project_id"]):
            desc = (f"#{projects[t['project_id']]}\n" + desc).strip()
        if desc:
            lines.append(f"DESCRIPTION:{_esc(desc)}")
        if t.get("labels"):
            lines.append("CATEGORIES:" + ",".join(_esc(l) for l in t["labels"]))
        lines.append(f"PRIORITY:{ {4: 1, 3: 5, 2: 7}.get(t['priority'], 0) }")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"

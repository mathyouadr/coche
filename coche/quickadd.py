"""Quick Add: one line of text -> a structured task.

    "Réviser SISR jeudi 14h #Cours /Examens @école p1 {vendredi} !30min"

    #Project  /Section  @label  p1..p4  {deadline}  !reminder  + any date / time /
    recurrence understood by :mod:`coche.dates` ("tous les lundis", "every 2 weeks").

Markers are only taken from known projects / sections (an unknown ``#word``
stays in the text, like Todoist); labels are created on the fly.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from . import dates

TRAILING = re.compile(r"(?:\s+(?:pour|for|on|le|avant|by|at|à|a|de|du|d'ici))+\s*$", re.I)


@dataclass
class Parsed:
    content: str
    project: str | None = None          # project name as typed / matched
    section: str | None = None
    labels: list[str] = field(default_factory=list)
    priority: int = 1                   # API scale: 4 = p1 (urgent) ... 1 = p4 (normal)
    due: dates.Due | None = None
    deadline: dt.date | None = None
    reminders: list[dict] = field(default_factory=list)   # {"minutes_before": n} | {"time": "HH:MM"}
    marks: list[dict] = field(default_factory=list)       # what to highlight in the UI

    def to_dict(self) -> dict:
        d = self.due
        return {
            "content": self.content, "project": self.project, "section": self.section, "labels": self.labels,
            "priority": self.priority, "deadline": self.deadline.isoformat() if self.deadline else None,
            "reminders": self.reminders, "marks": self.marks,
            "due": None if not d or not (d.date or d.clear) else {
                "date": d.date.isoformat() if d.date else None, "time": d.time, "string": d.string,
                "is_recurring": d.is_recurring, "clear": d.clear, "duration": d.duration,
                "rule": d.rule.to_dict() if d.rule else None},
        }


def _match_name(text: str, pos: int, names: list[str]) -> str | None:
    """Longest known name (case-insensitive, spaces allowed) starting at text[pos:]."""
    low = dates.fold(text[pos:])
    best = None
    for n in names:
        f = dates.fold(n)
        if low.startswith(f) and (len(low) == len(f) or not low[len(f)].isalnum()):
            if best is None or len(n) > len(best):
                best = n
    return best


def parse(text: str, projects: list[str] = (), sections: list[str] = (), today: dt.date | None = None,
          now: dt.datetime | None = None, order: str = "DMY") -> Parsed:
    now = now or dt.datetime.now()
    today = today or now.date()
    text = " ".join((text or "").split())
    out = Parsed(content="")
    cut: list[tuple[int, int]] = []

    def mark(kind, s, e, value):
        cut.append((s, e))
        out.marks.append({"kind": kind, "start": s, "end": e, "text": text[s:e], "value": value})

    # #Project and /Section (known names only, longest match so "#Side project" works)
    for m in re.finditer(r"(?<!\S)#(\S)", text):
        name = _match_name(text, m.start() + 1, list(projects))
        if name and out.project is None:
            mark("project", m.start(), m.start() + 1 + len(name), name)
            out.project = name
    for m in re.finditer(r"(?<!\S)/(\S)", text):
        name = _match_name(text, m.start() + 1, list(sections))
        if name and out.section is None:
            mark("section", m.start(), m.start() + 1 + len(name), name)
            out.section = name
    for m in re.finditer(r"(?<!\S)@([\w\-.:éèêàâçùûôîïëü]+)", text, re.I):
        if m.group(1).lower() not in [l.lower() for l in out.labels]:
            out.labels.append(m.group(1))
        mark("label", m.start(), m.end(), m.group(1))
    for m in re.finditer(r"(?<!\S)[pP]([1-4])(?!\S)", text):
        out.priority = 5 - int(m.group(1))
        mark("priority", m.start(), m.end(), out.priority)
    for m in re.finditer(r"\{([^{}]{1,60})\}", text):
        d = dates.parse_due(m.group(1), today, now, order)
        if d and d.date:
            out.deadline = d.date
            mark("deadline", m.start(), m.end(), d.date.isoformat())
    for m in re.finditer(r"(?<!\S)!(\d{1,3})\s?(min|m|h|j|d)(?!\w)", text, re.I):
        n = int(m.group(1)) * {"h": 60, "j": 1440, "d": 1440}.get(m.group(2).lower(), 1)
        if {"minutes_before": n} not in out.reminders:
            out.reminders.append({"minutes_before": n})
        mark("reminder", m.start(), m.end(), f"-{n}min")
    for m in re.finditer(r"(?<!\S)!(\d{1,2})(?:h(\d{2})?|:(\d{2}))(?!\w)", text):
        if any(s <= m.start() < e for s, e in cut):
            continue                                  # "!1h" is already "1 hour before"
        hh, mm = int(m.group(1)), int(m.group(2) or m.group(3) or 0)
        if hh < 24 and mm < 60:
            out.reminders.append({"time": "%02d:%02d" % (hh, mm)})
            mark("reminder", m.start(), m.end(), "%02d:%02d" % (hh, mm))

    # Dates: scan the text with the markers blanked out (same length, so spans stay valid)
    blank = list(text)
    for s, e in cut:
        blank[s:e] = " " * (e - s)
    due = dates.find_due("".join(blank), today, now, order)
    if due.date or due.clear:
        out.due = due
        for s, e in due.spans:
            mark("due", s, e, due.date.isoformat() if due.date else None)

    keep = [c for i, c in enumerate(text) if not any(s <= i < e for s, e in cut)]
    content = " ".join("".join(keep).split())
    content = TRAILING.sub("", content).strip(" ,;-") if out.due or out.deadline else content
    out.content = content or text
    out.marks.sort(key=lambda m: m["start"])
    return out

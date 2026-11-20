"""Natural-language dates, times and recurrences, in English and French.

    >>> parse_due("tomorrow 2pm", today=date(2026, 11, 20)).date
    datetime.date(2026, 11, 21)

Both languages are always understood, whatever the UI language. Every function
here is pure: pass ``today`` / ``now`` to make results deterministic.

The scanner works on a *folded* copy of the text (lower case, no accents, same
length as the original) so that matched spans can be cut out of the original.
"""
from __future__ import annotations

import calendar
import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field

date = dt.date

# --------------------------------------------------------------------------- vocab

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4, "samedi": 5, "dimanche": 6,
}
MONTHS = {
    "january": 1, "jan": 1, "janvier": 1, "janv": 1,
    "february": 2, "feb": 2, "fevrier": 2, "fevr": 2, "fev": 2,
    "march": 3, "mar": 3, "mars": 3,
    "april": 4, "apr": 4, "avril": 4, "avr": 4,
    "may": 5, "mai": 5,
    "june": 6, "jun": 6, "juin": 6,
    "july": 7, "jul": 7, "juillet": 7, "juil": 7,
    "august": 8, "aug": 8, "aout": 8,
    "september": 9, "sept": 9, "sep": 9, "septembre": 9,
    "october": 10, "oct": 10, "octobre": 10,
    "november": 11, "nov": 11, "novembre": 11,
    "december": 12, "dec": 12, "decembre": 12,
}
NUMBERS = {
    "a": 1, "an": 1, "one": 1, "un": 1, "une": 1, "two": 2, "deux": 2, "three": 3, "trois": 3,
    "four": 4, "quatre": 4, "five": 5, "cinq": 5, "six": 6, "seven": 7, "sept": 7, "eight": 8,
    "huit": 8, "nine": 9, "neuf": 9, "ten": 10, "dix": 10, "eleven": 11, "onze": 11,
    "twelve": 12, "douze": 12, "fifteen": 15, "quinze": 15, "other": 2,
}
# Words that name a moment of the day (only used right after a date word).
DAYPARTS = {
    "matin": (9, 0), "morning": (9, 0), "midi": (12, 0), "noon": (12, 0),
    "apres-midi": (15, 0), "apres midi": (15, 0), "aprem": (15, 0), "afternoon": (15, 0),
    "soir": (19, 0), "evening": (19, 0), "night": (21, 0), "nuit": (21, 0),
}

_alt = lambda words: "|".join(sorted((re.escape(w) for w in words), key=len, reverse=True))
WD = _alt(WEEKDAYS)
MON = _alt(MONTHS)
NUMW = r"\d{1,3}|" + _alt(NUMBERS)
PART = _alt(DAYPARTS)
B = r"(?<![\w#@/{!+-])"   # left boundary: not inside a word or a #tag / @label
E = r"(?![\w])"           # right boundary


def fold(text: str) -> str:
    """Lower case + strip accents, keeping the exact length (spans stay valid)."""
    out = []
    for c in text:
        base = unicodedata.normalize("NFD", c)[0].lower()
        out.append(base[0] if base else c)
    return "".join(out).replace("\u2019", "'")


def num(s: str) -> int:
    s = s.strip()
    return int(s) if s.isdigit() else NUMBERS[s]


# --------------------------------------------------------------------------- result types

@dataclass
class Rule:
    """A recurrence. ``freq`` is daily | weekly | monthly | yearly."""
    freq: str
    interval: int = 1
    weekdays: list[int] | None = None   # weekly on these days (0 = Monday)
    monthday: int | None = None         # monthly / yearly on this day of month
    month: int | None = None            # yearly in this month
    workdays: bool = False              # daily, Monday to Friday only
    from_completion: bool = False       # "every!": counted from the completion date

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v not in (None, False) or k == "freq"}

    @classmethod
    def from_dict(cls, d: dict | None) -> "Rule | None":
        if not d or "freq" not in d:
            return None
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class Due:
    date: date | None = None
    time: str | None = None             # "HH:MM", local floating time
    string: str = ""                    # the words that were understood
    rule: Rule | None = None
    clear: bool = False                 # "no date"
    duration: int | None = None         # minutes
    spans: list = field(default_factory=list)   # [(start, end)] in the original text

    @property
    def is_recurring(self) -> bool:
        return self.rule is not None


# --------------------------------------------------------------------------- calendar helpers

def add_months(d: date, n: int, day: int | None = None) -> date:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(day or d.day, calendar.monthrange(y, m)[1]))


def next_weekday(today: date, wd: int, allow_today: bool) -> date:
    delta = (wd - today.weekday()) % 7
    if delta == 0 and not allow_today:
        delta = 7
    return today + dt.timedelta(days=delta)


def safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def upcoming_day_month(today: date, day: int, month: int, year: int | None = None) -> date | None:
    if year is not None:
        if year < 100:
            year += 2000
        return safe_date(year, month, day)
    d = safe_date(today.year, month, day)
    if d is None and month == 2 and day == 29:          # next leap year
        y = today.year + 1
        while not calendar.isleap(y):
            y += 1
        return date(y, 2, 29)
    if d is not None and d < today:
        d = safe_date(today.year + 1, month, day) or d
    return d


def upcoming_monthday(today: date, day: int) -> date | None:
    if not 1 <= day <= 31:
        return None
    d = today
    for _ in range(24):
        last = calendar.monthrange(d.year, d.month)[1]
        if day <= last:
            cand = date(d.year, d.month, day)
            if cand >= today:
                return cand
        d = add_months(date(d.year, d.month, 1), 1)
    return None


# --------------------------------------------------------------------------- recurrence math

def first_occurrence(rule: Rule, start: date) -> date:
    """First date >= start matching the rule."""
    if rule.freq == "daily":
        d = start
        while rule.workdays and d.weekday() > 4:
            d += dt.timedelta(days=1)
        return d
    if rule.freq == "weekly":
        if rule.weekdays:
            return min(next_weekday(start, w, True) for w in rule.weekdays)
        return start
    if rule.freq == "monthly":
        return upcoming_monthday(start, rule.monthday) if rule.monthday else start
    if rule.freq == "yearly":
        if rule.month and rule.monthday:
            return upcoming_day_month(start, rule.monthday, rule.month) or start
        return start
    return start


def next_occurrence(rule: Rule, current: date) -> date:
    """The occurrence strictly after ``current``."""
    n = max(1, int(rule.interval or 1))
    if rule.freq == "daily":
        if rule.workdays:
            d = current + dt.timedelta(days=1)
            while d.weekday() > 4:
                d += dt.timedelta(days=1)
            return d
        return current + dt.timedelta(days=n)
    if rule.freq == "weekly":
        if not rule.weekdays:
            return current + dt.timedelta(weeks=n)
        anchor = current - dt.timedelta(days=current.weekday())
        d = current + dt.timedelta(days=1)
        for _ in range(7 * n + 7):
            week = (d - dt.timedelta(days=d.weekday()) - anchor).days // 7
            if d.weekday() in rule.weekdays and week % n == 0:
                return d
            d += dt.timedelta(days=1)
        return current + dt.timedelta(weeks=n)
    if rule.freq == "monthly":
        return add_months(current, n, rule.monthday or current.day)
    if rule.freq == "yearly":
        y = current.year + n
        m, day = rule.month or current.month, rule.monthday or current.day
        return date(y, m, min(day, calendar.monthrange(y, m)[1]))
    return current + dt.timedelta(days=1)


def advance(rule: Rule, current: date, today: date) -> date:
    """New due date when a recurring task is completed on ``today``.

    Regular rules move forward from the current due date and skip missed
    occurrences (never land in the past). ``every!`` rules count from today.
    """
    if rule.from_completion:
        return next_occurrence(rule, today)
    d = next_occurrence(rule, current)
    for _ in range(5000):
        if d >= today:
            break
        d = next_occurrence(rule, d)
    return d


# --------------------------------------------------------------------------- patterns

_DMY_NUM = r"(\d{1,2})/(\d{1,2})(?:/(\d{2}|\d{4}))?"
_ORD = r"(?:er|eme|e|st|nd|rd|th)?"

PATTERNS: list[tuple[str, str]] = []   # (kind, regex) - order does not matter, longest match wins


def P(kind: str, rx: str):
    PATTERNS.append((kind, B + rx + E))


# recurrences ---------------------------------------------------------------
EVERY = r"(?P<every>every|each|chaque|tou(?:s|tes)\s+les|tous\s+les|tou?tes\s+les)(?P<bang>!)?\s+"
P("rec", EVERY + r"(?:(?P<n>" + NUMW + r")\s+)?(?P<unit>jours?|days?|semaines?|weeks?|mois|months?|ans|annees?|years?)"
      r"(?P<work>\s+ouvres?|\s+ouvrables?)?")
P("rec", r"(?P<every>every)(?P<bang>!)?\s+(?P<unit>weekday|workday|work\s+day)s?")
P("rec", EVERY + r"(?P<wds>(?:" + WD + r")s?(?:\s*(?:,|et|and|&)\s*(?:" + WD + r")s?)*)")
P("rec", EVERY + r"(?:le\s+|the\s+)?(?P<md>\d{1,2})" + _ORD + r"(?:\s+(?P<mon>" + MON + r")\.?)?")
P("rec", EVERY + r"(?:le\s+)?(?P<md>\d{1,2})/(?P<mnum>\d{1,2})")
P("rec", EVERY + r"(?P<mon2>" + MON + r")\.?\s+(?P<md>\d{1,2})" + _ORD)
P("rec", EVERY + r"(?P<part>" + PART + r")s?")
P("rec", r"(?P<word>daily|weekly|monthly|yearly|annually|quotidiennement|hebdomadairement|mensuellement)")

# dates ---------------------------------------------------------------------
_P = r"(?:\s+(?P<part>" + PART + r"))?"
P("date", r"(?P<w>aujourd'hui|aujourdhui|today|ajd)" + _P)
P("date", r"(?P<w>apres[- ]demain|day\s+after\s+tomorrow)" + _P)
P("date", r"(?P<w>demain|tomorrow|tmrw|tmr)" + _P)
P("date", r"(?P<w>ce\s+soir|tonight|ce\s+matin|this\s+morning|cet\s+apres[- ]midi|cet\s+aprem|this\s+afternoon|this\s+evening)")
P("date", r"(?:(?P<this>ce|this|cette)\s+|(?P<next>next|prochain)\s+)?(?P<wd>" + WD + r")(?:\s+(?P<next2>prochain|qui\s+vient))?" + _P)
P("date", r"(?P<w>la\s+semaine\s+prochaine|semaine\s+prochaine|next\s+week)")
P("date", r"(?P<w>ce\s+week-?end|this\s+week-?end|le\s+week-?end|week-?end|ce\s+w-?e)")
P("date", r"(?P<w>le\s+week-?end\s+prochain|week-?end\s+prochain|next\s+week-?end)")
P("date", r"(?P<w>le\s+mois\s+prochain|mois\s+prochain|next\s+month)")
P("date", r"(?P<w>l'annee\s+prochaine|annee\s+prochaine|next\s+year)")
P("date", r"(?P<w>fin\s+du\s+mois|fin\s+de\s+mois|end\s+of\s+(?:the\s+)?month)")
P("date", r"(?P<w>fin\s+de\s+(?:la\s+)?semaine|end\s+of\s+(?:the\s+)?week)")
P("date", r"(?:dans|in|d'ici)\s+(?P<n>" + NUMW + r")\s*(?P<unit>jours?|j|semaines?|sem|mois|ans?|annees?|days?|d|weeks?|wks?|w|months?|years?|y|heures?|h|hours?|hrs?|minutes?|mins?|min)")
P("date", r"(?:le\s+|on\s+)?(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})")
P("date", r"(?:le\s+|on\s+)?" + _DMY_NUM)
P("date", r"(?:le\s+|on\s+)?(?P<d>\d{1,2})\.(?P<m>\d{1,2})\.(?P<y>\d{4})")
P("date", r"(?:(?:le|on|the|on\s+the)\s+)?(?P<d>\d{1,2}|1er)" + _ORD + r"\s+(?:of\s+)?(?P<mon>" + MON + r")\.?(?:\s+(?P<y>\d{4}))?")
P("date", r"(?:on\s+)?(?P<mon>" + MON + r")\.?\s+(?P<d>\d{1,2})" + _ORD + r"(?:,?\s+(?P<y>\d{4}))?")
P("date", r"(?:le|the|on\s+the)\s+(?P<md>\d{1,2}|1er)" + _ORD)
P("clear", r"(?:sans\s+date|no\s+date|pas\s+de\s+date|no\s+due\s+date)")

# times ---------------------------------------------------------------------
_AT = r"(?:(?:a|at|vers|around|@)\s+)?"
P("time", _AT + r"(?P<h>\d{1,2})\s?h(?:\s?(?P<mi>\d{2}))?(?!\s*(?:de|d'|of)\b)")
P("time", _AT + r"(?P<h>\d{1,2}):(?P<mi>\d{2})(?:\s*(?P<ap>am|pm))?")
P("time", _AT + r"(?P<h>\d{1,2})\s*(?P<ap>am|pm)")
P("time", r"(?:a|at|vers|around)\s+(?P<word>midi|noon|minuit|midnight)")
P("duration", r"(?:pendant|for|durant)\s+(?P<n>" + NUMW + r")\s*(?P<unit>h|heures?|hours?|hrs?|min|mins?|minutes?)")

COMPILED = [(k, re.compile(rx)) for k, rx in PATTERNS]


# --------------------------------------------------------------------------- interpreters

def _date_of(m: re.Match, today: date, now: dt.datetime, order: str):
    """-> (date, time or None) for a 'date' match, or None if invalid."""
    g = m.groupdict()
    w = (g.get("w") or "").replace("  ", " ")
    part = DAYPARTS.get((g.get("part") or "").strip())
    hm = "%02d:%02d" % part if part else None
    if w:
        if w in ("aujourd'hui", "aujourdhui", "today", "ajd"):
            return today, hm
        if w.startswith("apres") or w.startswith("day after"):
            return today + dt.timedelta(days=2), hm
        if w in ("demain", "tomorrow", "tmrw", "tmr"):
            return today + dt.timedelta(days=1), hm
        if "soir" in w or w in ("tonight", "this evening"):
            return today, "19:00"
        if "matin" in w or "morning" in w:
            return today, "09:00"
        if "aprem" in w or "apres" in w or "afternoon" in w:
            return today, "15:00"
        if w.startswith(("fin", "end of")):
            if "mois" in w or "month" in w:
                return date(today.year, today.month, calendar.monthrange(today.year, today.month)[1]), None
            return next_weekday(today, 4, True), None
        this_sat = today - dt.timedelta(days=1) if today.weekday() == 6 else next_weekday(today, 5, True)
        if re.search(r"week-?end|w-?e$", w):
            if "prochain" in w or w.startswith("next"):
                return this_sat + dt.timedelta(days=7), None
            return (today if today.weekday() >= 5 else this_sat), None
        if "semaine" in w or w == "next week":
            return next_weekday(today, 0, False), None
        if "mois" in w or w == "next month":
            return add_months(date(today.year, today.month, 1), 1), None
        if "annee" in w or w == "next year":
            return date(today.year + 1, 1, 1), None
    if g.get("wd"):
        allow = bool(g.get("this"))
        return next_weekday(today, WEEKDAYS[g["wd"]], allow), hm
    if g.get("unit"):
        n, u = num(g["n"]), g["unit"]
        if u.startswith(("h", "min")) or u.startswith("hr"):
            mins = n * 60 if u.startswith("h") else n
            x = now + dt.timedelta(minutes=mins)
            return x.date(), x.strftime("%H:%M")
        if u.startswith(("j", "d")):
            return today + dt.timedelta(days=n), None
        if u.startswith(("sem", "w")):
            return today + dt.timedelta(weeks=n), None
        if u.startswith(("mois", "month")):
            return add_months(today, n), None
        return add_months(today, 12 * n), None
    if g.get("md"):
        md = 1 if g["md"] == "1er" else int(g["md"])
        return upcoming_monthday(today, md), None
    if g.get("mon"):
        d = 1 if g["d"] == "1er" else int(g["d"])
        return upcoming_day_month(today, d, MONTHS[g["mon"]], int(g["y"]) if g.get("y") else None), None
    if g.get("y") and g.get("m"):
        return safe_date(int(g["y"]), int(g["m"]), int(g["d"])), None
    # numeric d/m(/y): groups 1..3 of _DMY_NUM
    a, b, y = m.group(1), m.group(2), m.group(3)
    if a and b:
        d, mo = (int(a), int(b)) if order == "DMY" else (int(b), int(a))
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            return None
        return upcoming_day_month(today, d, mo, int(y) if y else None), None
    return None


def _time_of(m: re.Match):
    g = m.groupdict()
    if g.get("word"):
        return "12:00" if g["word"] in ("midi", "noon") else "00:00"
    h, mi, ap = int(g["h"]), int(g.get("mi") or 0), g.get("ap")
    if ap:
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if ap == "pm" else 0)
    if h > 23 or mi > 59:
        return None
    return "%02d:%02d" % (h, mi)


def _rule_of(m: re.Match, today: date):
    """-> (Rule, first date, time or None)."""
    g = m.groupdict()
    bang = bool(g.get("bang"))
    if g.get("word"):
        w = g["word"]
        freq = {"daily": "daily", "quotidiennement": "daily", "weekly": "weekly", "hebdomadairement": "weekly",
                "monthly": "monthly", "mensuellement": "monthly"}.get(w, "yearly")
        r = Rule(freq)
        return r, first_occurrence(r, today), None
    if g.get("part"):
        r = Rule("daily", from_completion=bang)
        return r, today, "%02d:%02d" % DAYPARTS[g["part"]]
    if g.get("wds"):
        days = sorted({WEEKDAYS[x] for x in re.findall(WD, g["wds"])})
        r = Rule("weekly", weekdays=days, from_completion=bang)
        return r, first_occurrence(r, today), None
    if g.get("md"):
        md = int(g["md"])
        mon = MONTHS.get(g.get("mon") or g.get("mon2") or "") or (int(g["mnum"]) if g.get("mnum") else None)
        if mon:
            if not (1 <= mon <= 12 and safe_date(2024, mon, md)):
                return None
            r = Rule("yearly", monthday=md, month=mon, from_completion=bang)
        else:
            if not 1 <= md <= 31:
                return None
            r = Rule("monthly", monthday=md, from_completion=bang)
        return r, first_occurrence(r, today), None
    unit = g.get("unit") or ""
    if unit.startswith(("weekday", "workday", "work")) or g.get("work"):
        r = Rule("daily", workdays=True, from_completion=bang)
        return r, first_occurrence(r, today), None
    n = num(g["n"]) if g.get("n") else 1
    freq = ("daily" if unit.startswith(("jour", "day")) else "weekly" if unit.startswith(("sem", "week"))
            else "monthly" if unit.startswith(("mois", "month")) else "yearly")
    r = Rule(freq, interval=n, from_completion=bang)
    return r, today, None


def scan(text: str):
    """All candidate matches as (start, end, kind, match), overlaps resolved (longest wins)."""
    f = fold(text)
    cands = []
    for kind, rx in COMPILED:
        for m in rx.finditer(f):
            if m.end() > m.start():
                cands.append((m.start(), m.end(), kind, m))
    cands.sort(key=lambda c: (-(c[1] - c[0]), c[0]))
    chosen = []
    for c in cands:
        if all(c[1] <= o[0] or c[0] >= o[1] for o in chosen):
            chosen.append(c)
    return sorted(chosen, key=lambda c: c[0])


def find_due(text: str, today: date | None = None, now: dt.datetime | None = None, order: str = "DMY") -> Due:
    """Find a date / time / recurrence anywhere in ``text`` (used by Quick Add)."""
    now = now or dt.datetime.now()
    today = today or now.date()
    due = Due()
    for s, e, kind, m in scan(text):
        if kind == "rec" and due.rule is None and due.date is None:
            res = _rule_of(m, today)
            if res:
                due.rule, due.date, t = res
                due.time = due.time or t
                due.spans.append((s, e))
        elif kind == "date" and due.date is None:
            res = _date_of(m, today, now, order)
            if res and res[0]:
                due.date, t = res
                due.time = due.time or t
                due.spans.append((s, e))
        elif kind == "date" and due.rule is not None and due.date is not None:
            # "every monday starting 30/11" style: an explicit date after a rule = start date
            res = _date_of(m, today, now, order)
            if res and res[0]:
                due.date = first_occurrence(due.rule, res[0])
                due.spans.append((s, e))
        elif kind == "time" and due.time is None:
            t = _time_of(m)
            if t:
                due.time = t
                due.spans.append((s, e))
        elif kind == "duration" and due.duration is None:
            n, u = num(m.group("n")), m.group("unit")
            due.duration = n * 60 if u.startswith("h") else n
            due.spans.append((s, e))
        elif kind == "clear" and not due.clear:
            due.clear = True
            due.spans.append((s, e))
    if due.rule and due.date == today and due.time and due.time < now.strftime("%H:%M") and not due.rule.from_completion:
        due.date = next_occurrence(due.rule, today)       # "every day at 8am" typed at 10am starts tomorrow
    if due.time and due.date is None and not due.clear:
        due.date = today if due.time >= now.strftime("%H:%M") else today + dt.timedelta(days=1)
    if due.spans:
        due.string = " ".join(text[s:e].strip() for s, e in sorted(due.spans))
    return due


def parse_due(text: str, today: date | None = None, now: dt.datetime | None = None, order: str = "DMY") -> Due | None:
    """Parse a text that is *only* a due expression ("every monday 9am").

    Returns None if part of it is not understood (so the API can answer 400,
    like Todoist does for an unknown ``due_string``).
    """
    text = " ".join((text or "").split())
    if not text:
        return None
    due = find_due(text, today, now, order)
    rest = text
    for s, e in sorted(due.spans, reverse=True):
        rest = rest[:s] + " " + rest[e:]
    rest = fold(rest)
    rest = re.sub(r"\b(a|at|le|on|the|de|du|starting|from|a partir|partir|des|,|et|and)\b", " ", rest)
    if re.sub(r"[\s,.;:!-]", "", rest):
        return None
    if not (due.date or due.clear or due.rule):
        return None
    due.string = text
    return due


# --------------------------------------------------------------------------- formatting

def rule_to_text(rule: Rule, lang: str = "en") -> str:
    """Human description, e.g. 'every 2 weeks' / 'toutes les 2 semaines'."""
    fr = lang == "fr"
    bang = "!" if rule.from_completion else ""
    n = rule.interval or 1
    if rule.freq == "daily" and rule.workdays:
        return f"tous les{bang} jours ouvrés" if fr else f"every{bang} weekday"
    names_fr = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    names_en = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    if rule.freq == "weekly" and rule.weekdays:
        if fr:
            return f"tous les{bang} " + ", ".join(names_fr[d] + "s" for d in rule.weekdays)
        return f"every{bang} " + ", ".join(names_en[d] for d in rule.weekdays)
    if rule.freq == "monthly" and rule.monthday:
        return (f"tous les{bang} {rule.monthday}" if fr else f"every{bang} {rule.monthday}{_en_ord(rule.monthday)}")
    if rule.freq == "yearly" and rule.month and rule.monthday:
        mfr = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
        men = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
        return (f"tous les{bang} {rule.monthday} {mfr[rule.month - 1]}" if fr
                else f"every{bang} {men[rule.month - 1]} {rule.monthday}")
    unit_fr = {"daily": ("jour", "jours"), "weekly": ("semaine", "semaines"), "monthly": ("mois", "mois"),
               "yearly": ("an", "ans")}[rule.freq]
    unit_en = {"daily": "day", "weekly": "week", "monthly": "month", "yearly": "year"}[rule.freq]
    if fr:
        fem = rule.freq == "weekly"
        if n == 1:
            return f"{'toutes' if fem else 'tous'} les{bang} {unit_fr[1]}"
        return f"{'toutes' if fem else 'tous'} les{bang} {n} {unit_fr[1]}"
    return f"every{bang} {unit_en}" if n == 1 else f"every{bang} {n} {unit_en}s"


def _en_ord(n: int) -> str:
    return "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")

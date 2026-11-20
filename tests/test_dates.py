import datetime as dt
import unittest

from coche import dates, quickadd
from coche.dates import Rule, advance, next_occurrence, parse_due

TODAY = dt.date(2026, 11, 20)            # a Friday
NOW = dt.datetime(2026, 11, 20, 10, 0)
D = lambda s: dt.date.fromisoformat(s)


def due(text, order="DMY"):
    return parse_due(text, TODAY, NOW, order)


class DatesTest(unittest.TestCase):
    def check(self, text, day, time=None):
        d = due(text)
        self.assertIsNotNone(d, text)
        self.assertEqual(d.date, D(day), text)
        self.assertEqual(d.time, time, text)

    def test_relative_words(self):
        self.check("today", "2026-11-20")
        self.check("aujourd'hui", "2026-11-20")
        self.check("demain", "2026-11-21")
        self.check("Tomorrow", "2026-11-21")
        self.check("après-demain", "2026-11-22")
        self.check("ce soir", "2026-11-20", "19:00")
        self.check("demain matin", "2026-11-21", "09:00")
        self.check("tomorrow evening", "2026-11-21", "19:00")

    def test_weekdays(self):
        self.check("lundi", "2026-11-23")
        self.check("vendredi", "2026-11-27")           # today is Friday: next one
        self.check("ce vendredi", "2026-11-20")
        self.check("next monday", "2026-11-23")
        self.check("jeudi prochain", "2026-11-26")
        self.check("jeudi 14h", "2026-11-26", "14:00")
        self.check("thursday at 2:30pm", "2026-11-26", "14:30")

    def test_periods(self):
        self.check("semaine prochaine", "2026-11-23")
        self.check("next week", "2026-11-23")
        self.check("ce week-end", "2026-11-21")
        self.check("next weekend", "2026-11-28")
        self.check("mois prochain", "2026-12-01")
        self.check("fin du mois", "2026-11-30")
        self.check("end of week", "2026-11-20")
        self.check("dans 3 jours", "2026-11-23")
        self.check("in 2 weeks", "2026-12-04")
        self.check("dans un mois", "2026-12-20")
        self.check("dans 2h", "2026-11-20", "12:00")

    def test_explicit(self):
        self.check("25/12", "2026-12-25")
        self.check("le 3/1", "2027-01-03")           # past this year -> next year
        self.check("12/25", "2026-12-25") if False else None
        self.assertEqual(due("12/25", "MDY").date, D("2026-12-25"))
        self.check("2027-02-01", "2027-02-01")
        self.check("25 nov", "2026-11-25")
        self.check("1er décembre", "2026-12-01")
        self.check("le 5 janvier 2027", "2027-01-05")
        self.check("Dec 3rd", "2026-12-03")
        self.check("le 25", "2026-11-25")
        self.check("le 10", "2026-12-10")
        self.check("15.01.2027", "2027-01-15")

    def test_times(self):
        self.check("14h", "2026-11-20", "14:00")
        self.check("9h", "2026-11-21", "09:00")       # already past -> tomorrow
        self.check("demain à midi", "2026-11-21", "12:00")
        self.check("demain 8h45", "2026-11-21", "08:45")
        self.check("tomorrow 9am", "2026-11-21", "09:00")

    def test_clear_and_garbage(self):
        self.assertTrue(due("no date").clear)
        self.assertTrue(due("sans date").clear)
        self.assertIsNone(due("banane"))
        self.assertIsNone(due("demain banane"))
        self.assertIsNone(due(""))

    def test_recurrences(self):
        cases = {
            "every day": ("daily", 1, "2026-11-20"),
            "tous les jours": ("daily", 1, "2026-11-20"),
            "every 3 days": ("daily", 3, "2026-11-20"),
            "toutes les 2 semaines": ("weekly", 2, "2026-11-20"),
            "every other week": ("weekly", 2, "2026-11-20"),
            "tous les mois": ("monthly", 1, "2026-11-20"),
            "every year": ("yearly", 1, "2026-11-20"),
        }
        for text, (freq, n, first) in cases.items():
            d = due(text)
            self.assertIsNotNone(d, text)
            self.assertEqual((d.rule.freq, d.rule.interval, d.date), (freq, n, D(first)), text)

    def test_recurrence_shapes(self):
        d = due("tous les lundis et jeudis")
        self.assertEqual(d.rule.weekdays, [0, 3])
        self.assertEqual(d.date, D("2026-11-23"))
        d = due("every friday")
        self.assertEqual(d.date, TODAY)                # recurrences may start today
        d = due("tous les 5")
        self.assertEqual((d.rule.freq, d.rule.monthday, d.date), ("monthly", 5, D("2026-12-05")))
        d = due("every 25 dec")
        self.assertEqual((d.rule.freq, d.rule.month, d.rule.monthday, d.date), ("yearly", 12, 25, D("2026-12-25")))
        d = due("tous les jours ouvrés")
        self.assertTrue(d.rule.workdays)
        d = due("every! 3 days")
        self.assertTrue(d.rule.from_completion)
        d = due("tous les jours à 8h")
        self.assertEqual((d.date, d.time), (D("2026-11-21"), "08:00"))   # 8am already past
        d = due("every morning")
        self.assertEqual(d.time, "09:00")
        self.assertTrue(due("daily").is_recurring)

    def test_next_occurrence(self):
        self.assertEqual(next_occurrence(Rule("daily"), D("2026-11-20")), D("2026-11-21"))
        self.assertEqual(next_occurrence(Rule("daily", workdays=True), D("2026-11-20")), D("2026-11-23"))
        self.assertEqual(next_occurrence(Rule("weekly", weekdays=[0, 3]), D("2026-11-23")), D("2026-11-26"))
        self.assertEqual(next_occurrence(Rule("weekly", 2, weekdays=[0]), D("2026-11-23")), D("2026-12-07"))
        self.assertEqual(next_occurrence(Rule("monthly", monthday=31), D("2026-01-31")), D("2026-02-28"))
        self.assertEqual(next_occurrence(Rule("monthly", monthday=31), D("2026-02-28")), D("2026-03-31"))
        self.assertEqual(next_occurrence(Rule("yearly"), D("2028-02-29")), D("2029-02-28"))

    def test_advance_skips_missed(self):
        self.assertEqual(advance(Rule("daily"), D("2026-11-15"), TODAY), TODAY)
        self.assertEqual(advance(Rule("weekly", weekdays=[0]), D("2026-11-09"), TODAY), D("2026-11-23"))
        self.assertEqual(advance(Rule("daily", 3, from_completion=True), D("2026-11-01"), TODAY), D("2026-11-23"))

    def test_rule_text(self):
        self.assertEqual(dates.rule_to_text(Rule("weekly", 2), "fr"), "toutes les 2 semaines")
        self.assertEqual(dates.rule_to_text(Rule("weekly", weekdays=[0, 3]), "en"), "every monday, thursday")
        self.assertEqual(dates.rule_to_text(Rule("monthly", monthday=5), "en"), "every 5th")
        self.assertEqual(dates.rule_to_text(Rule("daily", workdays=True), "fr"), "tous les jours ouvrés")


class QuickAddTest(unittest.TestCase):
    def qa(self, text, **kw):
        return quickadd.parse(text, kw.get("projects", ["Inbox", "Cours", "Side project"]),
                              kw.get("sections", ["Examens"]), TODAY, NOW)

    def test_full_line(self):
        p = self.qa("Réviser SISR jeudi 14h #Cours /Examens @école p1 {vendredi} !30min")
        self.assertEqual(p.content, "Réviser SISR")
        self.assertEqual((p.project, p.section, p.labels, p.priority), ("Cours", "Examens", ["école"], 4))
        self.assertEqual((p.due.date, p.due.time), (D("2026-11-26"), "14:00"))
        self.assertEqual(p.deadline, D("2026-11-27"))
        self.assertEqual(p.reminders, [{"minutes_before": 30}])
        self.assertEqual(self.qa("Dentiste 12/03 9h30 !1h").reminders, [{"minutes_before": 60}])
        self.assertEqual(self.qa("Appel demain !14h30").reminders, [{"time": "14:30"}])

    def test_unknown_project_stays(self):
        p = self.qa("Lire #Inconnu demain")
        self.assertEqual(p.content, "Lire #Inconnu")
        self.assertIsNone(p.project)

    def test_project_with_space_and_case(self):
        p = self.qa("Coder #side project tous les lundis")
        self.assertEqual(p.project, "Side project")
        self.assertEqual(p.content, "Coder")
        self.assertTrue(p.due.is_recurring)

    def test_no_false_positives(self):
        for text in ["Faire 2h de sport", "Acheter un jeu", "Préparer la soirée", "Version 1.5 à tester",
                     "Lire le chapitre", "Mettre à jour le Mac"]:
            p = self.qa(text)
            self.assertIsNone(p.due, text)
            self.assertEqual(p.content, text)

    def test_trailing_preposition(self):
        self.assertEqual(self.qa("Rendre le dossier pour vendredi").content, "Rendre le dossier")
        self.assertEqual(self.qa("Call mom on monday at 6pm").content, "Call mom")

    def test_marks_for_highlighting(self):
        p = self.qa("Payer loyer tous les 5 @maison")
        kinds = [m["kind"] for m in p.marks]
        self.assertEqual(kinds, ["due", "label"])
        self.assertEqual(p.marks[0]["text"], "tous les 5")


if __name__ == "__main__":
    unittest.main()

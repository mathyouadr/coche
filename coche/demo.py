"""Sample data, to try Coche or take screenshots:  coche demo  (only on an empty database)."""
from __future__ import annotations

from .api import API


def seed(store, lang="en"):
    if store.q1("SELECT 1 FROM tasks LIMIT 1"):
        raise SystemExit("The database already has tasks: demo data is only added to an empty one.")
    store.set_settings({"lang": lang})
    api = API(store)
    fr = lang == "fr"

    def call(method, path, body):
        st, out = api.handle(method, path, {}, body)
        if st >= 400:
            raise RuntimeError(f"{path}: {out}")
        return out
    work = call("POST", "/api/v1/projects", {"name": "Travail" if fr else "Work", "color": "blue", "is_favorite": True})
    home = call("POST", "/api/v1/projects", {"name": "Maison" if fr else "Home", "color": "green"})
    side = call("POST", "/api/v1/projects", {"name": "Projet perso" if fr else "Side project", "color": "grape",
                                             "view_style": "board"})
    for name in (["À faire", "En cours", "Fait bientôt"] if fr else ["To do", "Doing", "Almost done"]):
        call("POST", "/api/v1/sections", {"name": name, "project_id": side["id"]})
    call("POST", "/api/v1/sections", {"name": "Réunions" if fr else "Meetings", "project_id": work["id"]})
    lines_fr = [
        "Préparer la démo client demain 10h #Travail p1 @focus !30min",
        "Répondre aux mails aujourd'hui 17h #Travail",
        "Revue de code de la PR #Travail /Réunions jeudi 14h pendant 1h",
        "Payer le loyer tous les 5 #Maison p2 @admin",
        "Sortir les poubelles tous les lundis et jeudis 20h #Maison",
        "Acheter du pain, des œufs et du café aujourd'hui @courses",
        "Arroser les plantes tous les 3 jours #Maison",
        "Écrire le README du projet #Projet perso /À faire p3",
        "Dessiner les maquettes #Projet perso /En cours @focus",
        "Mettre en ligne la v1 #Projet perso /Fait bientôt {vendredi}",
        "Appeler le garage lundi 9h p2",
        "Lire « Atomic Habits »",
        "Réserver les billets de train dans 2 semaines @voyage",
        "Sport tous les jours ouvrés 7h @santé",
    ]
    lines_en = [
        "Prepare the client demo tomorrow 10am #Work p1 @focus !30min",
        "Answer emails today 5pm #Work",
        "Code review #Work /Meetings thursday 2pm for 1h",
        "Pay rent every 5th #Home p2 @admin",
        "Take the bins out every monday and thursday 8pm #Home",
        "Buy bread, eggs and coffee today @errands",
        "Water the plants every 3 days #Home",
        "Write the project README #Side project /To do p3",
        "Draw the mockups #Side project /Doing @focus",
        "Ship v1 #Side project /Almost done {friday}",
        "Call the garage monday 9am p2",
        "Read “Atomic Habits”",
        "Book train tickets in 2 weeks @travel",
        "Workout every weekday 7am @health",
    ]
    first = None
    for line in (lines_fr if fr else lines_en):
        t = call("POST", "/api/v1/tasks/quick", {"text": line})
        first = first or t
    for sub in (["Slides", "Vérifier la démo", "Envoyer l'ordre du jour"] if fr else ["Slides", "Dry run", "Send the agenda"]):
        call("POST", "/api/v1/tasks", {"content": sub, "parent_id": first["id"]})
    call("POST", "/api/v1/comments", {"task_id": first["id"], "content": "Lien du deck : https://example.com/deck" if fr
                                      else "Deck link: https://example.com/deck"})
    old = call("POST", "/api/v1/tasks", {"content": "Renvoyer le colis" if fr else "Return the parcel",
                                         "due_date": store.today().fromordinal(store.today().toordinal() - 2).isoformat()})
    for c in (["Faire le plein", "Envoyer la facture"] if fr else ["Get fuel", "Send the invoice"]):
        t = call("POST", "/api/v1/tasks", {"content": c})
        call("POST", f"/api/coche/tasks/{t['id']}/close", {})
    call("POST", "/api/coche/filters", {"name": "Urgent", "query": "p1 | p2 | overdue" if not fr else "p1 | p2 | en retard",
                                        "color": "red", "is_favorite": True})
    return old

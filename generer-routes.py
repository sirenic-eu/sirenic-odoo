#!/usr/bin/env python3
"""Génère sirenic/models/routes.py depuis openapi.json.

Le module Odoo ne doit JAMAIS porter sa propre liste de routes écrite à la
main : elle divergerait de l'API au premier ajout. Même doctrine que
generer.mjs pour l'app Make.
"""
import json, re

SPEC = json.load(open("openapi.json"))
# Libellés FRANÇAIS : notre OpenAPI public ne porte que le résumé anglais, les
# textes français vivant dans la grille tarifaire. Un module destiné à des PME
# françaises ne peut pas afficher un menu en anglais tronqué, donc le
# générateur lit la grille, la source unique, plutôt que de retaper des
# libellés qui périmeraient au premier changement de prix ou de périmètre.
LIBELLES_FR = json.load(open("libelles-fr.json"))
META = ("/v1/compte", "/v1/credits", "/v1/provenance", "/v1/usage", "/v1/demo",
        "/v1/reperer", "/v1/sante-api")

# Routes trop lentes pour une action synchrone sur une fiche : l'utilisateur
# croirait Odoo figé. Mesurées en production.
LENTES = ("/v1/intelligence/", "/v1/rapport/", "/v1/kyb/batch")


def libelle(chemin, op):
    t = LIBELLES_FR.get(chemin) or op.get("summary") or chemin
    return re.sub(r"\s+", " ", t).strip()[:70]


routes = []
for chemin, ops in SPEC["paths"].items():
    op = ops.get("get")
    if not op:
        continue
    if any(chemin.startswith(m) for m in META):
        continue
    if any(chemin.startswith(l) for l in LENTES):
        continue
    params = [p["name"] for p in op.get("parameters", []) if p.get("in") == "path"]
    if not params or set(params) - {"siren", "siret"}:
        continue
    routes.append({
        "code": re.sub(r"[^a-z0-9]+", "_", chemin.lower()).strip("_"),
        "chemin": chemin,
        "cle": params[0],
        "libelle": libelle(chemin, op),
        "prix": op.get("x-price") or "",
    })

routes.sort(key=lambda r: r["libelle"])
corps = "\n".join(
    "    %r: %r," % (r["code"], {k: r[k] for k in ("chemin", "cle", "libelle", "prix")})
    for r in routes
)
sortie = '''# -*- coding: utf-8 -*-
# FICHIER GÉNÉRÉ PAR generer-routes.py, NE PAS ÉDITER À LA MAIN.
# Source : openapi.json de https://api.sirenic.eu, %d routes retenues.
#
# Critère de sélection, appliqué par le générateur et non décrété ici :
# une route entre si sa clé de chemin est un SIREN ou un SIRET seul, donc si
# elle a un geste évident sur une fiche partenaire Odoo. Les routes de compte
# et celles dont la latence dépasse une action synchrone sont écartées.

ROUTES = {
%s
}
''' % (len(routes), corps)
open("sirenic/models/routes.py", "w").write(sortie)
print("routes générées :", len(routes))
for r in routes[:5]:
    print("   ", r["code"][:44].ljust(46), r["prix"])

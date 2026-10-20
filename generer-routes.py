#!/usr/bin/env python3
"""Génère sirenic/models/routes.py depuis la grille SERVIE par l'API.

Le module Odoo ne doit JAMAIS porter sa propre liste de routes écrite à la
main : elle divergerait de l'API au premier ajout. Même doctrine que
generer.mjs pour l'app Make.

Deux entrées, téléchargées par curl (voir README) et jamais commitées, pour
qu'aucune copie ne périme dans le dépôt :
  openapi.json  https://api.sirenic.eu/openapi.json : chemins, paramètres,
                formats de réponse et prix de la grille (x-price, en dollars) ;
  index.md      https://api.sirenic.eu/index.md : l'accueil FRANÇAIS, dont le
                tableau des routes porte la description française de chacune et
                son prix affiché en euros.

    python3 generer-routes.py              écrit sirenic/models/routes.py
    python3 generer-routes.py --verifier   régénère en mémoire et refuse toute
                                           différence avec routes.py et la fiche

--verifier lit aussi mcp.json (https://api.sirenic.eu/.well-known/mcp.json,
téléchargé de même) : la fiche boutique y confronte ce qu'elle dit de l'offre
(appels offerts par mois, valeur d'un crédit, recharge par carte).
"""
import json, pathlib, re, sys

SORTIE = pathlib.Path("sirenic/models/routes.py")
FICHE = pathlib.Path("sirenic/static/description/index.html")

META = ("/v1/compte", "/v1/credits", "/v1/provenance", "/v1/usage", "/v1/demo",
        "/v1/reperer", "/v1/sante-api")

# Routes trop lentes pour une action synchrone sur une fiche : l'utilisateur
# croirait Odoo figé. Mesurées en production.
LENTES = ("/v1/intelligence/", "/v1/rapport/", "/v1/kyb/batch")

# Le geste le moins cher du module : la saisie assistée. La fiche boutique
# annonce les appels « à partir de » son prix, que --verifier relit.
ROUTE_SAISIE = "/v1/recherche"

LIBELLE_MAX = 70


class Refus(Exception):
    pass


def resoudre(param, spec):
    """Un paramètre en ligne, ou la cible de son $ref (#/components/parameters/x).

    Depuis le 13/09, l'OpenAPI servi factorise ses paramètres : sans cette
    résolution, le générateur ne voyait plus de clé de chemin et ne gardait
    que 8 routes sur 26.
    """
    ref = param.get("$ref")
    if not ref:
        return param
    prefixe = "#/components/parameters/"
    if not ref.startswith(prefixe):
        raise Refus("référence de paramètre inattendue : %s" % ref)
    cible = spec.get("components", {}).get("parameters", {}).get(ref[len(prefixe):])
    if cible is None:
        raise Refus("référence de paramètre introuvable : %s" % ref)
    return cible


def prix_en_euros(brut):
    """« $0.01 » devient « 0,01 € ».

    Ce n'est PAS une conversion : la grille facture le même montant NUMÉRIQUE
    en USDC, en EURC ou en crédits, et un crédit vaut un euro. Un utilisateur
    d'Odoo paie avec sa clé, donc en crédits : l'euro est sa devise réelle
    (décision du 29/09/2026 : toute surface française écrit ses prix en euros,
    au même nombre).
    """
    if not brut:
        return ""
    montant = str(brut).strip()
    if not re.fullmatch(r"\$[0-9]+(\.[0-9]+)?", montant):
        raise Refus("prix de grille illisible : %r" % brut)
    return montant[1:].replace(".", ",") + " €"


def grille_francaise(texte):
    """{chemin OpenAPI: (prix affiché, description française)} lus dans index.md."""
    grille = {}
    for ligne in texte.splitlines():
        m = re.match(r"^\| `GET ([^`]+)` \| ([^|]+) \| [^|]* \| (.*) \|\s*$", ligne)
        if not m:
            continue
        chemin = re.sub(r":(\w+)", r"{\1}", m.group(1))
        grille[chemin] = (m.group(2).strip(), m.group(3).replace("\\|", "|").strip())
    if not grille:
        raise Refus("aucune route lue dans index.md : tableau introuvable ou format changé")
    return grille


def libelle(description):
    """La première proposition de la description, coupée au mot et annoncée
    par « … » si elle dépasse la place d'une liste déroulante.

    Jusqu'au 19/10/2026, le libellé était coupé à 70 caractères au milieu d'un
    mot et sans signe (« issues du BODACC, le journa ») : une coupe muette.
    """
    t = re.sub(r"\s+", " ", description).strip()
    # Le tiret long sépare aussi : la fiche et le module n'en publient aucun.
    m = re.search(r" : |\. |; |\s*\u2014", t)
    if m:
        t = t[:m.start()]
    if len(t) <= LIBELLE_MAX:
        return t
    coupe = t[:LIBELLE_MAX - 1]
    if " " in coupe:
        coupe = coupe.rsplit(" ", 1)[0]
    return coupe.rstrip(" ,") + "…"


def raison_ecartee(chemin, op, spec):
    """None si la route a un geste sur une fiche partenaire, sinon pourquoi pas.

    Critère lu dans la spec, jamais décrété route par route : clé de chemin
    SIREN ou SIRET seule, aucun paramètre de requête obligatoire (le geste
    n'a pas de champ de saisie), et une réponse JSON (le client lit du JSON).
    """
    params = [resoudre(p, spec) for p in op.get("parameters", [])]
    chemin_ = [p["name"] for p in params if p.get("in") == "path"]
    if not chemin_ or set(chemin_) - {"siren", "siret"}:
        return "clé de chemin autre qu'un SIREN ou un SIRET"
    requis = sorted(p["name"] for p in params if p.get("in") == "query" and p.get("required"))
    if requis:
        return "paramètre de requête obligatoire : %s" % ", ".join(requis)
    formats = op.get("responses", {}).get("200", {}).get("content", {})
    if "application/json" not in formats:
        return "réponse en %s seulement" % (", ".join(sorted(formats)) or "format non déclaré")
    return None


def selectionner(spec, grille):
    """(routes retenues, [(chemin, raison)] écartées sur une clé SIREN ou SIRET)."""
    routes, ecartees = [], []
    for chemin, ops in spec["paths"].items():
        op = ops.get("get")
        if not op:
            continue
        if any(chemin.startswith(m) for m in META):
            continue
        if any(chemin.startswith(l) for l in LENTES):
            continue
        raison = raison_ecartee(chemin, op, spec)
        if raison:
            if not raison.startswith("clé de chemin"):
                ecartees.append((chemin, raison))
            continue
        if chemin not in grille:
            raise Refus("%s : absente du tableau français de index.md, aucun libellé lisible" % chemin)
        affiche, description = grille[chemin]
        prix = prix_en_euros(op.get("x-price"))
        if prix.replace(" ", " ") != affiche.replace(" ", " "):
            raise Refus("%s : prix de la grille %s, index.md affiche %s" % (chemin, prix, affiche))
        cle = [resoudre(p, spec)["name"] for p in op.get("parameters", [])
               if resoudre(p, spec).get("in") == "path"][0]
        routes.append({
            "code": re.sub(r"[^a-z0-9]+", "_", chemin.lower()).strip("_"),
            "chemin": chemin,
            "cle": cle,
            "libelle": libelle(description),
            "prix": prix,
        })
    routes.sort(key=lambda r: (r["libelle"], r["chemin"]))
    return routes, sorted(ecartees)


def rendre(routes, ecartees):
    corps = "\n".join(
        "    %r: %r," % (r["code"], {k: r[k] for k in ("chemin", "cle", "libelle", "prix")})
        for r in routes
    )
    exclues = "\n".join("#   %s : %s." % e for e in ecartees) or "#   aucune."
    return '''# -*- coding: utf-8 -*-
# FICHIER GÉNÉRÉ PAR generer-routes.py, NE PAS ÉDITER À LA MAIN.
# Source : openapi.json et index.md servis par https://api.sirenic.eu,
# %d routes retenues.
#
# Critère de sélection, lu dans la spec et non décrété ici : une route entre si
# sa clé de chemin est un SIREN ou un SIRET seul (un geste évident sur une
# fiche partenaire Odoo), sans paramètre de requête obligatoire (le geste n'a
# pas de champ de saisie) et avec une réponse JSON. Les routes de compte et
# celles dont la latence dépasse une action synchrone sont écartées.
#
# Écartées malgré une clé SIREN ou SIRET seule :
%s

ROUTES = {
%s
}
''' % (len(routes), exclues, corps)


def verifier_offre(html, cle):
    """Ce que la fiche dit de l'offre, contre payment.api_key_alternative de mcp.json.

    Le texte de la fiche est celui que CDU a relu (lettre Q2 A du 20/10/2026) :
    ce contrôle n'en écrit aucun mot, il refuse quand le service le contredit.
    """
    html = re.sub(r"\s+", " ", html)  # une phrase repliée sur deux lignes reste lue
    servi = re.match(r"([0-9]+) calls/month", cle.get("free_quota") or "")
    if not servi:
        raise Refus("mcp.json : quota gratuit illisible (free_quota : %r)" % (cle.get("free_quota") or "")[:120])
    ecrits = set(re.findall(r"([0-9]+) appels", html))
    if ecrits - {servi.group(1)}:
        raise Refus("fiche : %s appels offerts écrits, le service en sert %s par mois"
                    % (", ".join(sorted(ecrits - {servi.group(1)})), servi.group(1)))
    if "cr&#233;dit = " in html:
        unite = re.match(r"1 credit = ([0-9]+) EUR", cle.get("unit") or "")
        if not unite or "1 cr&#233;dit = %s &#8364;" % unite.group(1) not in html:
            raise Refus("fiche : « 1 crédit = 1 € », le service dit %r" % (cle.get("unit") or "")[:80])
    if "recharge par carte n'est pas encore ouverte" in html:
        if "card top-up is not open yet" not in (cle.get("purchase") or ""):
            raise Refus("fiche : la recharge par carte « pas encore ouverte », le service ne le dit plus "
                        "(purchase : %r)" % (cle.get("purchase") or "")[:160])


def verifier_fiche(spec, routes, mcp):
    """La fiche boutique ne porte aucun nombre que le service contredit."""
    html = FICHE.read_text(encoding="utf-8")
    verifier_offre(html, (mcp.get("payment") or {}).get("api_key_alternative") or {})
    m = re.search(r"&#224; partir de ([0-9]+(?:,[0-9]+)?) &#8364;", html)
    if not m:
        raise Refus("fiche : « à partir de N € » introuvable, la phrase a changé")
    saisie = spec["paths"].get(ROUTE_SAISIE, {}).get("get", {})
    attendu = prix_en_euros(saisie.get("x-price")).split(" ")[0]
    if m.group(1) != attendu:
        raise Refus("fiche : « à partir de %s € », la saisie assistée coûte %s €" % (m.group(1), attendu))
    plus_bas = [r for r in routes if float(r["prix"].split(" ")[0].replace(",", ".")) <
                float(attendu.replace(",", "."))]
    if plus_bas:
        raise Refus("fiche : « à partir de %s € », mais %s coûte moins" % (attendu, plus_bas[0]["chemin"]))


def main(argv):
    try:
        spec = json.loads(pathlib.Path("openapi.json").read_text(encoding="utf-8"))
        grille = grille_francaise(pathlib.Path("index.md").read_text(encoding="utf-8"))
        routes, ecartees = selectionner(spec, grille)
        texte = rendre(routes, ecartees)
        if "--verifier" in argv:
            mcp = json.loads(pathlib.Path("mcp.json").read_text(encoding="utf-8"))
            verifier_fiche(spec, routes, mcp)
            actuel = SORTIE.read_text(encoding="utf-8")
            if actuel != texte:
                import difflib
                sys.stdout.writelines(difflib.unified_diff(
                    actuel.splitlines(True), texte.splitlines(True), str(SORTIE), "grille servie"))
                raise Refus("%s n'est plus celui que donne la grille servie : relancer "
                            "python3 generer-routes.py et commiter" % SORTIE)
            print("OK : %d routes, identiques à la grille servie ; fiche d'accord." % len(routes))
            return 0
        SORTIE.write_text(texte, encoding="utf-8")
    except FileNotFoundError as e:
        print("REFUS : entrée absente, %s : la télécharger (README, « Régénérer le catalogue de routes »)"
              % e.filename, file=sys.stderr)
        return 1
    except Refus as e:
        print("REFUS :", e, file=sys.stderr)
        return 1
    print("routes générées :", len(routes))
    for chemin, raison in ecartees:
        print("    écartée", chemin, ":", raison)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

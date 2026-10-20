#!/usr/bin/env python3
"""Le générateur de catalogue, joué sur une petite spec à la forme de la spec servie.

Chaque cas lance generer-routes.py tel qu'un humain le lance (un dossier, deux
entrées, un routes.py écrit), puis lit ce qu'il a écrit. Les paramètres en
$ref reprennent la forme exacte de /openapi.json depuis la factorisation du
13/09 : c'est elle qui avait cassé l'ancien générateur sans qu'aucune erreur ne
sorte (8 routes gardées sur 26).
"""
import ast, json, pathlib, shutil, subprocess, sys, tempfile

ICI = pathlib.Path(__file__).resolve().parent
ok = ko = 0


def v(condition, quoi):
    global ok, ko
    ok, ko = ok + (1 if condition else 0), ko + (0 if condition else 1)
    print(("  OK    " if condition else "  ECHEC ") + quoi)


# Le paramètre factorisé, tel que servi par components.parameters.siren.
SIREN = {"name": "siren", "in": "path", "required": True,
         "schema": {"type": "string", "pattern": "^\\d{9}$"},
         "description": "9-digit SIREN (Luhn-validated)"}
JSON_200 = {"200": {"description": "OK", "content": {"application/json": {}}}}


def route(params, prix, reponses=None):
    return {"get": {"summary": "en anglais", "x-price": prix, "parameters": params,
                    "responses": reponses or JSON_200}}


SPEC = {
    "openapi": "3.1.0",
    "components": {"parameters": {"siren": SIREN}},
    "paths": {
        "/v1/entreprise/{siren}/en-ligne": route([dict(SIREN)], "$0.01"),
        "/v1/entreprise/{siren}/factorisee": route([{"$ref": "#/components/parameters/siren"}], "$0.02"),
        "/v1/entreprise/{siren}/avec-date": route(
            [{"$ref": "#/components/parameters/siren"},
             {"name": "depuis", "in": "query", "required": True, "schema": {"type": "string"}}], "$0.01"),
        "/v1/entreprise/{siren}/markdown": route(
            [{"$ref": "#/components/parameters/siren"}], "$0.05",
            {"200": {"description": "OK", "content": {"text/markdown": {}}}}),
        "/v1/intelligence/{siren}": route([{"$ref": "#/components/parameters/siren"}], "$1.00"),
        "/v1/compte/solde": route([], "$0.00"),
        "/v1/recherche": route([{"name": "q", "in": "query", "required": True}], "$0.002"),
    },
}

LONGUE = ("Accords collectifs d'entreprise d'une société française publiés sur Légifrance, "
          "avec leur thème et leur date : la suite ne compte pas")


def ligne(chemin, prix, description):
    return "| `GET %s` | %s | [exemple](https://api.sirenic.eu/exemples/x.json) | %s |" % (chemin, prix, description)


def index_md(lignes):
    return "\n".join(["# Sirenic", "", "| Route | Prix | Exemple | Description |",
                      "| --- | --- | --- | --- |"] + lignes) + "\n"


INDEX = index_md([
    ligne("/v1/entreprise/:siren/en-ligne", "0,01 €", "Route en ligne : la suite ne compte pas"),
    ligne("/v1/entreprise/:siren/factorisee", "0,02 €", LONGUE),
    ligne("/v1/entreprise/:siren/avec-date", "0,01 €", "Route datée"),
    ligne("/v1/entreprise/:siren/markdown", "0,05 €", "Route en Markdown"),
    ligne("/v1/recherche", "0,002 €", "Recherche"),
])


def jouer(spec, index, *args):
    """(code, ROUTES ou None, sortie) du générateur lancé dans un dossier neuf."""
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        shutil.copy(ICI / "generer-routes.py", d)
        (d / "sirenic/models").mkdir(parents=True)
        (d / "openapi.json").write_text(json.dumps(spec), encoding="utf-8")
        (d / "index.md").write_text(index, encoding="utf-8")
        # L'ancien générateur lisait libelles-fr.json : présent et vide, il
        # tourne aussi, et le test le juge sur ce qu'il écrit, pas sur un plantage.
        (d / "libelles-fr.json").write_text("{}", encoding="utf-8")
        p = subprocess.run([sys.executable, "-I", "generer-routes.py", *args], cwd=d,
                           capture_output=True, text=True)
        sortie = d / "sirenic/models/routes.py"
        routes = None
        if sortie.exists():
            arbre = ast.parse(sortie.read_text(encoding="utf-8"))
            for n in arbre.body:
                if isinstance(n, ast.Assign) and n.targets[0].id == "ROUTES":
                    routes = ast.literal_eval(n.value)
        return p.returncode, routes, p.stdout + p.stderr


print("Catalogue sur la spec de forme servie")
code, routes, sortie = jouer(SPEC, INDEX)
routes = routes or {}
chemins = {r["chemin"] for r in routes.values()}
v(code == 0, "le générateur rend 0 (%s)" % sortie.strip().splitlines()[:1])
v("/v1/entreprise/{siren}/en-ligne" in chemins, "paramètre de chemin en ligne : route gardée")
v("/v1/entreprise/{siren}/factorisee" in chemins, "paramètre de chemin en $ref : route gardée")
v("/v1/entreprise/{siren}/avec-date" not in chemins, "paramètre de requête obligatoire : route écartée")
v("/v1/entreprise/{siren}/markdown" not in chemins, "réponse sans JSON : route écartée")
v("/v1/intelligence/{siren}" not in chemins, "route lente : écartée")
v(not any(c.startswith("/v1/compte") or c == "/v1/recherche" for c in chemins),
  "routes de compte et sans clé de chemin : écartées")
fact = next((r for r in routes.values() if r["chemin"].endswith("/factorisee")), {})
v(fact.get("cle") == "siren", "la clé d'une route en $ref est lue : %r" % fact.get("cle"))
v(fact.get("prix") == "0,02 €", "prix lu dans la grille, en euros au même nombre : %r" % fact.get("prix"))
lib = fact.get("libelle", "")
tronc = lib[:-1]
v(len(lib) <= 70 and lib.endswith("…") and LONGUE.startswith(tronc) and LONGUE[len(tronc):][:1] in (" ", ","),
  "libellé long coupé au mot, la coupe dite par « … » : %r" % lib)
en_ligne = next((r for r in routes.values() if r["chemin"].endswith("/en-ligne")), {})
v(en_ligne.get("libelle") == "Route en ligne", "libellé = première proposition de la description française : %r"
  % en_ligne.get("libelle"))

print("Refus plutôt qu'une valeur inventée")
faux_prix = index_md([ligne("/v1/entreprise/:siren/en-ligne", "0,03 €", "Route en ligne"),
                      ligne("/v1/entreprise/:siren/factorisee", "0,02 €", LONGUE)])
code, _, sortie = jouer(SPEC, faux_prix)
v(code == 1 and "prix" in sortie, "prix de la grille et prix affiché en désaccord : refus (%s)" % sortie.strip().splitlines()[-1])
sans_libelle = index_md([ligne("/v1/entreprise/:siren/en-ligne", "0,01 €", "Route en ligne")])
code, _, sortie = jouer(SPEC, sans_libelle)
v(code == 1 and "factorisee" in sortie, "route gardée sans description française : refus, pas de libellé anglais")
code, _, sortie = jouer(SPEC, "# Sirenic\n\nplus de tableau\n")
v(code == 1, "index.md sans tableau : refus")

print("La fiche boutique contre /.well-known/mcp.json")
# Les trois champs relus, tels que les sert /.well-known/mcp.json le 20/10/2026.
CLE = {"unit": "1 credit = 1 EUR, same per-call prices",
       "free_quota": "150 calls/month on 109 of 125 routes (the price list says which) with a verified account",
       "purchase": "Open today: 150 free calls a month with an account, on 109 of 125 routes (the price list "
                   "says which), and pay-per-call over x402 (USDC or EURC), with no account except registry "
                   "filings. Prepaid credits: card top-up is not open yet."}


def verifier(cle, fiche=None):
    """(code, sortie) de --verifier sur la VRAIE fiche du dépôt (ou une variante) et un mcp.json donné."""
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        shutil.copy(ICI / "generer-routes.py", d)
        (d / "sirenic/models").mkdir(parents=True)
        (d / "sirenic/static/description").mkdir(parents=True)
        (d / "openapi.json").write_text(json.dumps(SPEC), encoding="utf-8")
        (d / "index.md").write_text(INDEX, encoding="utf-8")
        (d / "libelles-fr.json").write_text("{}", encoding="utf-8")
        reelle = (ICI / "sirenic/static/description/index.html").read_text(encoding="utf-8")
        (d / "sirenic/static/description/index.html").write_text(fiche or reelle, encoding="utf-8")
        (d / "mcp.json").write_text(json.dumps({"payment": {"api_key_alternative": cle}}), encoding="utf-8")
        subprocess.run([sys.executable, "-I", "generer-routes.py"], cwd=d, capture_output=True, text=True)
        p = subprocess.run([sys.executable, "-I", "generer-routes.py", "--verifier"], cwd=d,
                           capture_output=True, text=True)
        return p.returncode, (p.stdout + p.stderr).strip().splitlines()[-1:] or [""]


code, sortie = verifier(CLE)
v(code == 0, "fiche du dépôt et service d'accord : %s" % sortie)
code, sortie = verifier(dict(CLE, free_quota=CLE["free_quota"].replace("150", "149", 1)))
v(code == 1 and "149" in sortie[0], "quota servi changé (149) : refus (%s)" % sortie)
code, sortie = verifier(dict(CLE, free_quota="free calls, see the price list"))
v(code == 1, "quota servi illisible : refus (%s)" % sortie)
code, sortie = verifier(dict(CLE, unit="1 credit = 2 EUR, same per-call prices"))
v(code == 1 and "cr" in sortie[0], "valeur du crédit changée : refus (%s)" % sortie)
code, sortie = verifier(dict(CLE, purchase=CLE["purchase"].replace(" Prepaid credits: card top-up is not open yet.", "")))
v(code == 1 and "recharge" in sortie[0], "recharge par carte ouverte, la fiche dit le contraire : refus (%s)" % sortie)
reelle = (ICI / "sirenic/static/description/index.html").read_text(encoding="utf-8")
code, sortie = verifier(CLE, reelle.replace("150 appels offerts", "100 appels offerts"))
v(code == 1 and "100" in sortie[0], "fiche qui écrit 100 appels : refus (%s)" % sortie)

print("%d contrôles, %d en échec" % (ok + ko, ko))
sys.exit(1 if ko else 0)

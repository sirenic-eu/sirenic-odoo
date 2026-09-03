#!/usr/bin/env python3
"""Contrôles statiques du module, faute de pouvoir le charger dans Odoo.

Ne remplace PAS une installation réelle : dit ce qu'il vérifie, et rien de plus.
"""
import ast, csv, pathlib, re, sys
import xml.etree.ElementTree as ET

R = pathlib.Path("sirenic")
erreurs, controles = [], []


def dire(ok, quoi):
    controles.append((ok, quoi))
    if not ok:
        erreurs.append(quoi)


man = ast.literal_eval(re.search(r"\{.*\}", (R / "__manifest__.py").read_text(encoding="utf-8"), re.S).group())
dire(len(man["name"]) <= 25, "nom du module <= 25 caracteres (regle boutique) : %d" % len(man["name"]))
dire(bool(man.get("license")), "licence declaree : %s" % man.get("license"))
dire("description" in man and "TRANSMIS" in man["description"],
     "manifeste declare les donnees transmises (regle boutique)")

# 1. tous les fichiers de `data` existent
for f in man["data"]:
    dire((R / f).exists(), "fichier declare present : %s" % f)

# 2. ordre de chargement : une reference %(xxx)d doit etre DEFINIE avant
definis, refs = {}, []
for i, f in enumerate(man["data"]):
    if not f.endswith(".xml"):
        continue
    txt = (R / f).read_text(encoding="utf-8")
    for rid in re.findall(r'<record[^>]*id="([^"]+)"', txt):
        definis.setdefault(rid, i)
    for rid in re.findall(r"%\((\w+)\)d", txt):
        refs.append((rid, i, f))
for rid, i, f in refs:
    ou = definis.get(rid)
    dire(ou is not None and ou <= i, "reference %s definie avant son usage (%s)" % (rid, f))

# 3. les modeles cites dans les droits existent dans le code
modeles = set()
for py in R.rglob("*.py"):
    modeles |= set(re.findall(r'_name\s*=\s*"([^"]+)"', py.read_text(encoding="utf-8")))
for ligne in csv.DictReader(open(R / "security/ir.model.access.csv")):
    m = ligne["model_id:id"].replace("model_", "").replace("_", ".")
    dire(m in modeles, "droit d acces sur un modele existant : %s" % m)

# 4. XML bien forme
for f in R.rglob("*.xml"):
    try:
        ET.parse(f); dire(True, "XML bien forme : %s" % f.name)
    except Exception as e:
        dire(False, "XML CASSE : %s (%s)" % (f.name, e))

# 4 bis. Fichiers EXIGES par la boutique Odoo pour publier
#        (source : https://apps.odoo.com/apps/upload)
for exige, quoi in [
    ("static/description/icon.png", "icone PNG"),
    ("static/description/index.html", "fiche boutique HTML"),
    ("LICENSE", "fichier de licence a la racine du module"),
]:
    dire((R / exige).exists(), "exige par la boutique : %s (%s)" % (exige, quoi))
if (R / "static/description/icon.png").exists():
    entete = (R / "static/description/icon.png").read_bytes()[:8]
    dire(entete == b"\x89PNG\r\n\x1a\n", "l icone est un VRAI PNG, pas un fichier renomme")

# 5. Python compilable
import py_compile
for py in R.rglob("*.py"):
    try:
        py_compile.compile(str(py), doraise=True); dire(True, "compile : %s" % py.name)
    except Exception as e:
        dire(False, "NE COMPILE PAS : %s (%s)" % (py.name, e))

print("%d controles, %d en echec" % (len(controles), len(erreurs)))
for e in erreurs:
    print("  ECHEC :", e)
print("\nCE QUI N EST PAS CONTROLE ICI : le chargement reel dans Odoo, la validite")
print("des vues heritees (xpath), et le comportement a l execution.")
sys.exit(1 if erreurs else 0)

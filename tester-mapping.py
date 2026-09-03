#!/usr/bin/env python3
"""Éprouve la logique pure sur les réponses RÉELLES de l'API, pas sur des
fixtures inventées : une fixture écrite à la main encode l'hypothèse qu'on
teste, elle ne peut que la confirmer."""
import json, sys, importlib.util, glob

s = importlib.util.spec_from_file_location("m", "sirenic/models/sirenic_mapping.py")
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)

ok = fail = 0
def verifier(cond, quoi):
    global ok, fail
    if cond: ok += 1; print("  OK   ", quoi)
    else: fail += 1; print("  ECHEC", quoi)

print("=== separation de l adresse ===")
cas = [
    (("59 RUE LA FAYETTE 75009 PARIS", "75009", "PARIS"), "59 RUE LA FAYETTE"),
    (("2 RUE KELLERMANN 59100 ROUBAIX", "59100", "ROUBAIX"), "2 RUE KELLERMANN"),
    # Pas de suffixe a retirer : doit ressortir INTACTE, pas tronquee.
    (("LIEU-DIT LA CROIX", "12345", "AILLEURS"), "LIEU-DIT LA CROIX"),
    # La commune apparait AUSSI dans la rue : on ne retire que le suffixe.
    (("RUE DE PARIS 75009 PARIS", "75009", "PARIS"), "RUE DE PARIS"),
    ((None, None, None), ""),
    (("", "75009", "PARIS"), ""),
]
for (a, cp, c), attendu in cas:
    got = m.separer_adresse(a, cp, c)
    verifier(got == attendu, "%-34r -> %r" % (a, got))

print("\n=== champs depuis le profil REEL de DANONE ===")
profil = json.load(open([f for f in glob.glob("reponse-entreprise*")][0]))
ch = m.champs_depuis_profil(profil)
verifier(ch.get("name") == "DANONE", "name = %r" % ch.get("name"))
verifier(ch.get("vat") == "FR27552032534", "vat = %r (calcule par l API, pas par nous)" % ch.get("vat"))
verifier(ch.get("zip") == "75009", "zip = %r" % ch.get("zip"))
verifier(ch.get("city") == "PARIS", "city = %r" % ch.get("city"))
verifier(ch.get("street") == "59 RUE LA FAYETTE", "street = %r (sans le CP ni la ville)" % ch.get("street"))
verifier(ch.get("is_company") is True, "is_company")
verifier(all(v not in (None, "") for v in ch.values()), "aucun champ vide ne serait ecrit")

print("\n=== un profil AMPUTE ne doit rien ecraser ===")
ch2 = m.champs_depuis_profil({"denomination": "X", "siege": {}})
verifier(set(ch2) == {"name", "is_company"}, "seuls les champs presents sont rendus : %s" % sorted(ch2))

print("\n=== rapport KYB sur la reponse REELLE ===")
kyb = json.load(open("reponse-kyb.json"))
html = m.rapport_kyb_html(kyb)
verifier("Dossier KYB Sirenic" in html, "titre present")
verifier("FR27552032534" in html, "TVA presente")
verifier("Criblage sanctions" in html, "criblage restitue")
verifier(html.count("<tr>") >= 8, "au moins 8 lignes de rapport (%d)" % html.count("<tr>"))
verifier("{" not in html.replace("style='","").replace("{",""), "aucune accolade JSON brute laissee")

print("\n=== l en-tete ALERTE quand il le faut ===")
danger = dict(kyb); danger["alertes_bodacc"] = dict(kyb.get("alertes_bodacc") or {}, procedures_collectives=[{"x": 1}])
h2 = m.rapport_kyb_html(danger)
verifier("À vérifier avant de payer" in h2, "procedure collective -> en-tete rouge")
# ⚠️ MON TEMOIN ETAIT FAUX. J avais suppose DANONE « propre » ; le dossier REEL
# porte 4 correspondances de criblage sur un dirigeant homonyme, donc l en-tete
# rouge est JUSTE. Le temoin se construit maintenant en VIDANT les
# correspondances du dossier reel, au lieu de parier sur son contenu.
propre = json.loads(json.dumps(kyb))
for c in (propre.get("criblage_sanctions") or {}).get("cibles") or []:
    c["correspondances"] = []
h3 = m.rapport_kyb_html(propre)
verifier("Aucun signal bloquant" in h3, "temoin : dossier sans correspondance -> en-tete vert")
verifier("homonyme" in html, "le rapport DIT qu une correspondance est un homonyme a lever")
# ⚠️ La cible se DEDUIT de la fixture, elle ne s ecrit pas en dur : ce depot est
# PUBLIC, et figer le nom d une personne physique y serait une publication
# nouvelle. Le test reste valable si le dossier change.
touchee = next((c.get("cible") for c in (kyb.get("criblage_sanctions") or {}).get("cibles") or []
                if c.get("correspondances")), None)
verifier(bool(touchee) and touchee in html, "le rapport NOMME la cible touchee, pas un statut nu")
verifier("homonyme" not in h3, "et ne le dit PAS quand il n y a rien a lever")

print("\n%d verifications, %d en echec" % (ok + fail, fail))
sys.exit(1 if fail else 0)

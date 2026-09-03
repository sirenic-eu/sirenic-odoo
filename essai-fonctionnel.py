# Exécuté dans le shell Odoo : appelle VRAIMENT l'API et vérifie les effets.
import os
ok = ko = 0
def v(cond, quoi):
    global ok, ko
    if cond: ok += 1; print("  OK   ", quoi)
    else: ko += 1; print("  ECHEC", quoi)

P = env["ir.config_parameter"].sudo()
cle = os.environ["SIRENIC_KEY"]

# 1. La garde de consentement doit REFUSER avant tout.
P.set_param("sirenic.api_key", cle)
P.set_param("sirenic.consent", "False")
# ⚠️ LE PARTENAIRE DOIT AVOIR UN SIREN, sinon action_sirenic_kyb echoue sur
# l identifiant AVANT d atteindre la garde de consentement, et le test passe
# a vide en croyant l avoir eprouvee.
p = env["res.partner"].create({"name": "Essai Sirenic", "is_company": True, "vat": "FR27552032534"})
try:
    p.action_sirenic_kyb(); v(False, "sans consentement : aurait du REFUSER")
except Exception as e:
    v("accord" in str(e), "sans consentement : refus explicite (%s)" % str(e)[:70])

# Et le cas sans identifiant, sur un AUTRE partenaire.
vide = env["res.partner"].create({"name": "Sans identifiant", "is_company": True})

# 2. Avec consentement mais sans identifiant : message utile, pas un plantage.
P.set_param("sirenic.consent", "True")
try:
    vide.action_sirenic_kyb(); v(False, "sans SIREN : aurait du refuser")
except Exception as e:
    v("SIREN" in str(e), "sans identifiant : message qui dit quoi faire")

# 3. Saisie assistee : recherche par NOM, puis recopie.
w = env["sirenic.autocomplete"].create({"partner_id": p.id, "recherche": "danone"})
w.action_chercher()
v(len(w.ligne_ids) > 0, "recherche par nom : %d candidat(s)" % len(w.ligne_ids))
premiere = w.ligne_ids[0]
v(bool(premiere.siren) and bool(premiere.denomination), "candidat renseigne : %s / %s" % (premiere.denomination, premiere.siren))
premiere.action_choisir()
p.invalidate_recordset()
v(p.name and p.name != "Essai Sirenic", "nom recopie : %r" % p.name)
v(bool(p.vat), "TVA recopiee : %r" % p.vat)
v(bool(p.zip) and bool(p.city), "code postal / ville : %r %r" % (p.zip, p.city))
v(p.street and p.zip not in (p.street or ""), "rue SANS le code postal : %r" % p.street)

# 4. Le dossier KYB atterrit dans le fil, en HTML lisible.
avant = len(p.message_ids)
p.action_sirenic_kyb()
p.invalidate_recordset()
msgs = p.message_ids.sorted("id", reverse=True)
v(len(p.message_ids) > avant, "un message ajoute au fil")
corps = msgs[0].body or ""
v("Dossier KYB Sirenic" in corps, "le fil contient le rapport titre")
v("<table>" in corps, "rendu en tableau, pas en JSON brut")
v("&lt;" not in corps, "HTML RENDU et non echappe (le defaut du 03/09)")
v("{" not in corps.replace("{{", ""), "aucune accolade JSON dans le fil")
print("      corps stocke par Odoo :", corps[:300].replace("\n", " "))

# 5. Une route du catalogue genere, appelee pour de vrai.
r = p.sirenic_appeler_route("v1_entreprise_siren")
v(isinstance(r, dict) and r.get("siren"), "route generee appelee : siren %s" % r.get("siren"))

print("\n%d verifications, %d en echec" % (ok + ko, ko))

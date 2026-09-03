import os
ok = ko = 0
def v(c, q):
    global ok, ko
    ok, ko = ok + (1 if c else 0), ko + (0 if c else 1)
    print(("  OK   " if c else "  ECHEC"), q)
P = env["ir.config_parameter"].sudo()
P.set_param("sirenic.api_key", os.environ["SIRENIC_KEY"]); P.set_param("sirenic.consent", "True")
p = env["res.partner"].create({"name": "Client d essai", "is_company": True, "vat": "FR27552032534"})
avant = len(p.message_ids)
r = p.action_sirenic_client()
p.invalidate_recordset()
v(len(p.message_ids) > avant, "un rapport ajoute au fil")
corps = p.message_ids.sorted("id", reverse=True)[0].body or ""
v("Risque de defaillance" in corps, "titre du rapport present")
v("&lt;" not in corps, "HTML rendu, pas echappe")
v("notation de credit" in corps, "l avertissement de l API est visible par le lecteur")
v("mois d anciennete" in corps or "anciennete" in corps, "l age des comptes est dit")
v(r["params"]["type"] in ("success", "warning"), "notification typee : %s" % r["params"]["type"])
v("Classe de risque" in r["params"]["title"] or "BODACC" in r["params"]["title"], "titre : %s" % r["params"]["title"])
print("\n%d verifications, %d en echec" % (ok + ko, ko))

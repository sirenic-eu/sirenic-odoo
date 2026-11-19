#!/usr/bin/env python3
"""La trace au fil de l'assistant « Vérification Sirenic » dit ce que l'API a débité.

Depuis les appels offerts du mois, un appel couvert par eux ne coûte rien : l'API
le dit dans l'en-tête X-Credits-Charged (0), et le débit réel sinon (en crédits,
un crédit vaut un euro). La trace écrivait le prix de la grille dans tous les cas
(kopko13/sirenic#188, case du 30/10/2026) : un appel offert s'y lisait payé.

Faute de banc Odoo 19, Odoo et requests sont remplacés ici par le strict
nécessaire pour charger sirenic_client.py et sirenic_verification.py tels quels :
ce banc éprouve la lecture de l'en-tête et le texte de la trace, pas le
chargement dans Odoo (controler-module.py dit ce qui reste hors contrôle).
"""
import importlib, pathlib, sys, types

ICI = pathlib.Path(__file__).resolve().parent
ok = ko = 0


def v(condition, quoi):
    global ok, ko
    ok, ko = ok + (1 if condition else 0), ko + (0 if condition else 1)
    print(("  OK    " if condition else "  ECHEC ") + quoi)


# --- Odoo et requests, le strict nécessaire --------------------------------
class UserError(Exception):
    pass


class Champ:
    def __init__(self, *a, **k):
        pass


def traduire(source, *args):
    # Comme odoo._ : la chaîne source, formatée par ses arguments.
    return source % args if args else source


odoo = types.ModuleType("odoo")
odoo._ = traduire
odoo.api = types.SimpleNamespace(depends=lambda *a: (lambda f: f))
odoo.fields = types.SimpleNamespace(Many2one=Champ, Selection=Champ, Char=Champ, Text=Champ)
odoo.models = types.SimpleNamespace(TransientModel=object, AbstractModel=object, Model=object)
odoo.exceptions = types.ModuleType("odoo.exceptions")
odoo.exceptions.UserError = UserError
sys.modules["odoo"], sys.modules["odoo.exceptions"] = odoo, odoo.exceptions


class Reponse:
    def __init__(self, entetes, corps=None, statut=200):
        self.status_code, self.headers, self._corps = statut, entetes, corps or {"ok": True}

    def json(self):
        return self._corps


requetes = types.ModuleType("requests")
requetes.Timeout = type("Timeout", (Exception,), {})
requetes.RequestException = type("RequestException", (Exception,), {})
requetes.reponse = None
requetes.get = lambda *a, **k: requetes.reponse
sys.modules["requests"] = requetes

# Le paquet du module sans son __init__ (qui chargerait tout le reste d'Odoo).
for nom in ("sirenic", "sirenic.models", "sirenic.wizards"):
    paquet = types.ModuleType(nom)
    paquet.__path__ = [str(ICI.joinpath(*nom.split(".")))]
    sys.modules[nom] = paquet
client_mod = importlib.import_module("sirenic.models.sirenic_client")
assistant_mod = importlib.import_module("sirenic.wizards.sirenic_verification")
ROUTES = importlib.import_module("sirenic.models.routes").ROUTES


def client():
    c = client_mod.SirenicClient()
    c._config = lambda: ("https://api.sirenic.eu", "srn_live_essai", True)
    return c


print("Le débit lu dans X-Credits-Charged")
for entetes, attendu, quoi in [
    ({"X-Credits-Charged": "0"}, "0", "appel offert : 0"),
    ({"X-Credits-Charged": "0.12"}, "0.12", "appel débité : 0.12"),
    ({"X-Credits-Charged": "0.5"}, "0.5", "rapport : 0.5"),
    ({}, None, "en-tête absent : débit non lu, pas 0"),
    ({"X-Credits-Charged": "gratuit"}, None, "en-tête illisible : débit non lu"),
    ({"X-Credits-Charged": "-1"}, None, "débit négatif : non lu"),
    ({"X-Credits-Charged": "NaN"}, None, "NaN : non lu"),
]:
    requetes.reponse = Reponse(entetes, {"siren": "552032534"})
    try:
        corps, debit = client().appeler_et_debit("/v1/entreprise/552032534")
        lu = None if debit is None else str(debit)
        v(corps == {"siren": "552032534"} and lu == attendu, "%s (lu %r)" % (quoi, lu))
    except Exception as e:  # l'ancien client n'a pas appeler_et_debit
        v(False, "%s (%s : %s)" % (quoi, type(e).__name__, e))
requetes.reponse = Reponse({"X-Credits-Charged": "0"}, {"a": 1})
v(client().appeler("/v1/x") == {"a": 1}, "appeler() rend toujours le seul corps (gestes d'en-tête inchangés)")
requetes.reponse = Reponse({}, statut=402)
try:
    client().appeler_et_debit("/v1/x")
    v(False, "402 : aurait dû refuser")
except UserError as e:
    v("rien n'a été débité" in str(e), "402 : le même refus lisible que appeler()")
except Exception as e:
    v(False, "402 : %s" % type(e).__name__)

print("La trace au fil de l'assistant")
code = "v1_entreprise_siren_alertes" if "v1_entreprise_siren_alertes" in ROUTES else sorted(ROUTES)[0]
route = ROUTES[code]


class Partenaire:
    def __init__(self, debit):
        self.debit, self.fil = debit, []

    def sirenic_appeler_route(self, code, avec_debit=False):
        corps = {"siren": "552032534"}
        return (corps, self.debit) if avec_debit else corps

    def message_post(self, body):
        self.fil.append(body)


def trace(debit):
    w = assistant_mod.SirenicVerification()
    w.partner_id, w.route, w.id, w._name = Partenaire(debit), code, 1, "sirenic.verification"
    w.ensure_one = lambda: None
    try:
        w.action_verifier()
    except Exception as e:
        return "%s : %s" % (type(e).__name__, e)
    return w.partner_id.fil[-1] if w.partner_id.fil else ""


Decimal = __import__("decimal").Decimal
t = trace(Decimal("0"))
v("offert" in t and route["prix"] not in t, "appel offert : la trace le dit, sans le prix de la grille (%r)" % t)
t = trace(Decimal("0.12"))
v("0,12 €" in t and "offert" not in t, "appel débité de 0.12 : la trace dit 0,12 € (%r)" % t)
t = trace(Decimal("0.5"))
v("0,50 €" in t, "appel débité de 0.5 : la trace dit 0,50 € (%r)" % t)
t = trace(Decimal("0.002"))
v("0,002 €" in t, "appel débité de 0.002 : la trace dit 0,002 € (%r)" % t)
t = trace(None)
v(route["prix"] in t and "non lu" in t, "débit non lu : le prix de la grille, dit comme tel (%r)" % t)
v(t.startswith("Sirenic, %s" % route["libelle"]), "la trace nomme toujours la vérification (%r)" % t)

print("\n%d contrôles, %d en échec" % (ok + ko, ko))
sys.exit(1 if ko else 0)

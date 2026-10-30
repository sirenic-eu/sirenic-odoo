# -*- coding: utf-8 -*-
"""Client HTTP de l'API Sirenic.

Un seul point de sortie vers le réseau pour tout le module : la garde de
consentement, le masquage de la clé et la traduction des erreurs vivent ici et
nulle part ailleurs. Dupliquer un appel `requests` ailleurs dans le module
contournerait les trois d'un coup.
"""
import logging

import requests

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Au-delà, l'utilisateur croit l'interface figée. Nos routes lentes (rapport,
# intelligence) dépassent la minute : elles ne sont volontairement PAS exposées
# en action synchrone sur une fiche.
DELAI_S = 30


class SirenicClient(models.AbstractModel):
    _name = "sirenic.client"
    _description = "Appel de l'API Sirenic"

    def _config(self):
        params = self.env["ir.config_parameter"].sudo()
        return (
            params.get_param("sirenic.base_url", "https://api.sirenic.eu"),
            params.get_param("sirenic.api_key", ""),
            params.get_param("sirenic.consent", "False") == "True",
        )

    def appeler(self, chemin, params=None):
        """Rend le corps JSON, ou lève un UserError lisible.

        ⚠️ LA GARDE DE CONSENTEMENT EST ICI, pas dans les vues. Les règles
        éditeurs d'Odoo exigent un opt-in AVANT toute transmission ; une garde
        posée sur un bouton laisserait passer les appels déclenchés par une
        action planifiée ou par un autre module.
        """
        base, cle, consenti = self._config()
        if not consenti:
            raise UserError(_(
                "Sirenic n'a pas encore votre accord pour transmettre des données.\n\n"
                "Paramètres → Sirenic : lisez ce qui est envoyé, puis cochez le "
                "consentement. Aucun appel n'est émis avant."
            ))
        if not cle:
            raise UserError(_(
                "Aucune clé d'API Sirenic n'est enregistrée.\n\n"
                "Paramètres → Sirenic. Créez la vôtre sur %s/compte.", base))

        try:
            reponse = requests.get(
                "%s%s" % (base, chemin),
                params=params or {},
                # La clé voyage en en-tête, JAMAIS dans l'URL : une URL finit
                # dans les journaux, les référents et l'historique.
                headers={"X-Api-Key": cle, "User-Agent": "sirenic-odoo/1.0"},
                timeout=DELAI_S,
            )
        except requests.Timeout:
            raise UserError(_("Sirenic n'a pas répondu en %s secondes. Réessayez.", DELAI_S))
        except requests.RequestException:
            # Le détail contiendrait l'URL, donc potentiellement l'identifiant
            # contrôlé : on ne le remonte pas à l'écran.
            _logger.warning("Sirenic injoignable sur %s", chemin)
            raise UserError(_("Sirenic est injoignable. Vérifiez votre connexion réseau."))

        # 401 et 402 méritent un message qui dit ce qui se passe et où regarder :
        # ce sont les deux cas qui tiennent à la clé et au compte de l'utilisateur.
        if reponse.status_code == 401:
            raise UserError(_("Clé d'API Sirenic refusée. Vérifiez-la dans Paramètres → Sirenic."))
        if reponse.status_code == 402:
            # Avec une clé, le 402 vient du rail des crédits de l'API (src/compte/
            # rail.ts, `credits_insuffisants`) : l'appel n'est entré ni dans les
            # appels offerts ni dans le solde, et rien n'est débité. Ceux du mois
            # sont utilisés, ou la route n'est pas éligible, ou (en-tête
            # X-Free-Quota-Refused) ceux du jour, partagés par tous les comptes sur
            # les routes qui appellent un modèle, le sont. La recharge par carte
            # n'est pas ouverte (`purchase` de /.well-known/mcp.json) : le message
            # n'y invite pas, et generer-routes.py --verifier le refuserait.
            if reponse.headers.get("X-Free-Quota-Refused"):
                pourquoi = _("ceux du jour sur cette route, partagés par tous les comptes, sont tous utilisés")
            else:
                pourquoi = _("ceux du mois sont tous utilisés, ou cette route n'en fait pas partie")
            raise UserError(_(
                "Cet appel n'a pas été servi et rien n'a été débité : il n'entre pas dans vos "
                "appels offerts (%s) et votre solde de crédits ne le couvre pas.\n\n"
                "Votre solde et vos appels offerts restants : %s/compte. Crédits prépayés : "
                "leur recharge par carte n'est pas encore ouverte.", pourquoi, base))
        if reponse.status_code == 404:
            raise UserError(_("Sirenic ne connaît pas cet identifiant."))
        if reponse.status_code == 406:
            raise UserError(_("Sirenic ne publie pas cette donnée dans le format demandé."))
        if reponse.status_code == 503:
            raise UserError(_("La source officielle est temporairement indisponible. Réessayez plus tard."))
        if reponse.status_code >= 400:
            raise UserError(_("Sirenic a répondu %s.", reponse.status_code))
        return reponse.json()

# -*- coding: utf-8 -*-
"""Assistant « vérification Sirenic ».

Les routes du catalogue ont chacune un geste sur une fiche partenaire. Un
bouton par route rendrait la fiche illisible : l'assistant les rassemble en UNE
liste déroulante, dont les options sont GÉNÉRÉES depuis la grille servie
(generer-routes.py). Ajouter une route à l'API la fait apparaître ici sans
toucher à ce fichier.
"""
import json

from odoo import _, api, fields, models

from ..models.routes import ROUTES
from ..models.sirenic_client import montant_euros


class SirenicVerification(models.TransientModel):
    _name = "sirenic.verification"
    _description = "Vérification Sirenic"

    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade")
    route = fields.Selection(
        selection=lambda self: self._selection_routes(),
        required=True,
        string="Vérification",
    )
    # Le prix est affiché AVANT l'appel : personne ne doit découvrir une
    # facturation après coup.
    prix = fields.Char(compute="_compute_prix", string="Prix de cet appel")
    resultat = fields.Text(readonly=True)

    @staticmethod
    def _selection_routes():
        return [(code, "%s  (%s)" % (r["libelle"], r["prix"] or "-"))
                for code, r in ROUTES.items()]

    @api.depends("route")
    def _compute_prix(self):
        for wiz in self:
            wiz.prix = (ROUTES.get(wiz.route) or {}).get("prix") or ""

    def action_verifier(self):
        self.ensure_one()
        corps, debit = self.partner_id.sirenic_appeler_route(self.route, avec_debit=True)
        self.resultat = json.dumps(corps, indent=2, ensure_ascii=False)
        # Trace datée dans le fil : une vérification sans trace ne prouve rien
        # le jour où il faut justifier une décision de paiement. Elle dit ce que
        # l'API a débité (X-Credits-Charged), pas le prix de la grille : un appel
        # couvert par les appels offerts du mois ne coûte rien
        # (kopko13/sirenic#188). Sans débit lu, le prix de la grille, dit comme tel.
        route = ROUTES[self.route]
        if debit is None:
            cout = _("%s à la grille, débit non lu", route["prix"])
        elif debit == 0:
            cout = _("appel offert, aucun débit")
        else:
            cout = _("débit de %s", montant_euros(debit))
        self.partner_id.message_post(body=_("Sirenic, %s (%s)", route["libelle"], cout))
        return {"type": "ir.actions.act_window", "res_model": self._name,
                "res_id": self.id, "view_mode": "form", "target": "new"}

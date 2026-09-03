# -*- coding: utf-8 -*-
"""Saisie assistée : chercher une entreprise, puis remplir la fiche."""
from odoo import _, fields, models
from odoo.exceptions import UserError

from ..models.sirenic_mapping import avertissement_etat, champs_depuis_profil


class SirenicAutocompleteLine(models.TransientModel):
    _name = "sirenic.autocomplete.line"
    _description = "Candidat de recherche Sirenic"
    _order = "score desc, denomination"

    wizard_id = fields.Many2one("sirenic.autocomplete", ondelete="cascade")
    siren = fields.Char(readonly=True)
    denomination = fields.Char(readonly=True)
    commune = fields.Char(readonly=True)
    etat = fields.Char(string="État", readonly=True)
    score = fields.Float(readonly=True)

    def action_choisir(self):
        self.ensure_one()
        return self.wizard_id._remplir(self.siren)


class SirenicAutocomplete(models.TransientModel):
    _name = "sirenic.autocomplete"
    _description = "Saisie assistée Sirenic"

    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade")
    recherche = fields.Char(
        string="Nom ou SIREN", required=True,
        help="Un nom d'entreprise, ou directement un SIREN à neuf chiffres.")
    ligne_ids = fields.One2many("sirenic.autocomplete.line", "wizard_id", readonly=True)
    message = fields.Char(readonly=True)

    def action_chercher(self):
        self.ensure_one()
        terme = (self.recherche or "").strip()
        self.ligne_ids.unlink()
        # Un SIREN saisi directement évite un appel de recherche : on remplit
        # tout de suite. Neuf chiffres ne sont jamais un nom d'entreprise.
        nu = terme.replace(" ", "")
        if len(nu) == 9 and nu.isdigit():
            return self._remplir(nu)
        if len(terme) < 2:
            raise UserError(_("Saisissez au moins deux caractères, ou un SIREN complet."))

        corps = self.env["sirenic.client"].appeler("/v1/recherche", {"q": terme})
        resultats = corps.get("resultats") or []
        for r in resultats[:10]:
            self.env["sirenic.autocomplete.line"].create({
                "wizard_id": self.id,
                "siren": r.get("siren"),
                "denomination": r.get("denomination"),
                "commune": r.get("commune_siege"),
                "etat": r.get("etat_administratif"),
                "score": r.get("score_confiance") or 0.0,
            })
        # Dire « rien trouvé » explicitement : une liste vide sans un mot
        # ressemble à une panne.
        self.message = (_("%s résultat(s). Choisissez l'entreprise à recopier.", len(resultats))
                        if resultats else _("Aucune entreprise ne correspond à « %s ».", terme))
        return self._rouvrir()

    def _remplir(self, siren):
        self.ensure_one()
        corps = self.env["sirenic.client"].appeler("/v1/entreprise/%s" % siren)
        champs = champs_depuis_profil(corps)
        if not champs:
            raise UserError(_("Sirenic n'a renvoyé aucun champ exploitable pour ce SIREN."))
        self.partner_id.write(champs)
        # Le SIRET n'existe comme champ que si la localisation française est
        # installée : on ne l'écrit que s'il est là, sans supposer.
        siege = corps.get("siege") or {}
        if siege.get("siret") and "siret" in self.partner_id._fields:
            self.partner_id.write({"siret": siege["siret"]})
        avertissement = avertissement_etat(corps)
        self.partner_id.message_post(body=_(
            "Fiche complétée depuis Sirenic (SIREN %s). %s", siren, avertissement))
        self.message = _("Fiche complétée. %s", avertissement)
        return {"type": "ir.actions.act_window_close"}

    def _rouvrir(self):
        return {"type": "ir.actions.act_window", "res_model": self._name,
                "res_id": self.id, "view_mode": "form", "target": "new"}

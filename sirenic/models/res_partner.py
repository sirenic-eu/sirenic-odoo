# -*- coding: utf-8 -*-
import re

from markupsafe import Markup

from odoo import _, models
from odoo.exceptions import UserError

from .routes import ROUTES
from .sirenic_mapping import rapport_kyb_html, rapport_score_html

# Pays dont le numéro de TVA se TERMINE par l'identifiant national, et dont
# nous savons donc l'extraire sans inventer de correspondance.
#
# ⚠️ Ne pas étendre cette table « par analogie ». Mesuré le 03/09/2026 en
# construisant le scénario Make : FR = FR + 2 caractères de clé + 9 chiffres de
# SIREN ; BE = BE + le numéro d'entreprise à 10 chiffres ; PL = PL + le NIP à
# 10 chiffres, ce que notre propre OpenAPI confirme. Pour l'Estonie ou la
# Slovaquie, le code de registre n'est PAS le numéro de TVA : en dériver un
# produirait un identifiant plausible et faux, exactement ce que ce produit
# s'interdit.
LONGUEUR_ID_PAR_PAYS = {"FR": 9, "BE": 10, "PL": 10}


class ResPartner(models.Model):
    _inherit = "res.partner"

    # ── Identifiant ───────────────────────────────────────────────────────
    def _sirenic_tva_normalisee(self):
        """La TVA débarrassée de ce que la saisie humaine y laisse.

        Mesuré sur un carnet volontairement sale : minuscules, espaces autour,
        espaces internes, points « à la belge » et tirets sont tous présents en
        vrai. Sans cette normalisation, un partenaire sur trois échouait.
        """
        return re.sub(r"[^A-Z0-9]", "", (self.vat or "").upper())

    def _sirenic_siren(self):
        """Le SIREN français, ou None, jamais une valeur devinée."""
        self.ensure_one()
        # Le champ SIRET n'existe que si la localisation française est
        # installée : ne pas le supposer présent.
        siret = (getattr(self, "siret", "") or "").replace(" ", "")
        if len(siret) == 14 and siret.isdigit():
            return siret[:9]
        tva = self._sirenic_tva_normalisee()
        if tva[:2] == "FR" and len(tva) == 13 and tva[-9:].isdigit():
            return tva[-9:]
        # Un SIREN saisi tel quel dans le champ TVA, cas fréquent.
        if len(tva) == 9 and tva.isdigit():
            return tva
        return None

    def _sirenic_identifiant_national(self):
        """(pays, identifiant) pour les pays où l'extraction est licite."""
        self.ensure_one()
        tva = self._sirenic_tva_normalisee()
        pays, reste = tva[:2], tva[2:]
        attendu = LONGUEUR_ID_PAR_PAYS.get(pays)
        if attendu and len(reste) == attendu:
            return pays, reste
        return None, None

    # ── Actions ───────────────────────────────────────────────────────────
    def action_sirenic_dossier(self):
        """Le geste principal : peut-on payer ce fournisseur ?"""
        self.ensure_one()
        client = self.env["sirenic.client"]
        siren = self._sirenic_siren()
        if siren:
            corps = client.appeler("/v1/facturation/dossier", {"siren": siren})
        else:
            pays, ident = self._sirenic_identifiant_national()
            if not pays:
                raise UserError(_(
                    "Impossible d'identifier ce partenaire.\n\n"
                    "Renseignez son numéro de TVA intracommunautaire (ou son SIRET). "
                    "Sirenic sait extraire l'identifiant national pour la France, "
                    "la Belgique et la Pologne ; ailleurs, seul le contrôle VIES du "
                    "numéro est possible."))
            if pays not in ("BE", "PL"):
                corps = client.appeler("/v1/tva/verifier/%s" % self._sirenic_tva_normalisee())
                return self._sirenic_afficher(corps, _("Numéro de TVA contrôlé au VIES SEULEMENT, "
                                                       "ni procédure collective, ni IBAN, ni identité au registre."))
            corps = client.appeler("/v1/eu/facturation/dossier", {"pays": pays, "id": ident})
        return self._sirenic_afficher(corps)

    def sirenic_appeler_route(self, code):
        """Appelle une route du catalogue généré, sur ce partenaire."""
        self.ensure_one()
        route = ROUTES.get(code)
        if not route:
            raise UserError(_("Route Sirenic inconnue : %s", code))
        siren = self._sirenic_siren()
        if not siren:
            raise UserError(_("Ce partenaire n'a ni SIRET ni numéro de TVA française exploitable."))
        valeur = siren
        if route["cle"] == "siret":
            siret = (getattr(self, "siret", "") or "").replace(" ", "")
            if len(siret) != 14:
                raise UserError(_("Cette vérification demande un SIRET (14 chiffres), pas seulement un SIREN."))
            valeur = siret
        chemin = route["chemin"].replace("{%s}" % route["cle"], valeur)
        return self.env["sirenic.client"].appeler(chemin)

    def _sirenic_afficher(self, corps, avertissement=None):
        """Rend le résultat dans une notification, et le trace dans le fil.

        Le fil de discussion sert de PREUVE datée : une vérification dont il ne
        reste rien ne vaut rien le jour où l'on doit justifier un paiement.
        """
        self.ensure_one()
        verdict = (corps or {}).get("verdict") or {}
        pret = verdict.get("pret_a_facturer")
        raisons = [r.get("code") for r in (verdict.get("raisons") or []) if r.get("niveau") == "bloquante"]
        titre = _("Sirenic : prêt à facturer") if pret else _("Sirenic : à ne pas payer en l'état")
        detail = ", ".join(raisons) if raisons else _("aucun motif bloquant")
        message = "%s, %s" % (titre, detail)
        if avertissement:
            message = "%s\n%s" % (message, avertissement)
        self.message_post(body=message)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": titre, "message": detail,
                       "type": "success" if pret else "warning", "sticky": False},
        }

    def action_sirenic_kyb(self):
        """Le dossier KYB, rendu LISIBLE dans le fil de discussion.

        Le JSON brut n'est pas un rapport : personne ne justifie une entrée en
        relation en collant des accolades. Le fil sert de trace datée, c'est
        elle qu'on produira le jour où il faudra montrer ce qui avait été
        vérifié, et quand.
        """
        self.ensure_one()
        siren = self._sirenic_siren()
        if not siren:
            raise UserError(_(
                "Aucun SIREN exploitable sur cette fiche.\n\n"
                "Renseignez le SIRET ou le numéro de TVA française, ou utilisez "
                "la saisie assistée pour compléter la fiche depuis le registre."))
        corps = self.env["sirenic.client"].appeler("/v1/kyb/%s" % siren)
        # ⚠️ Markup, PAS une chaîne nue. Depuis Odoo 17, `message_post`
        # ÉCHAPPE tout str : le fil afficherait « &lt;div&gt;&lt;h4&gt;… », les
        # balises en clair. Constaté au banc d'essai le 03/09/2026, invisible
        # à tout contrôle statique, et à l'œil nu seulement une fois le module
        # chargé dans un vrai Odoo.
        self.message_post(body=Markup(rapport_kyb_html(corps)))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Dossier KYB ajouté au fil"),
                       "message": _("Complétude %s %%", corps.get("score_completude")),
                       "type": "success", "sticky": False},
        }

    def action_sirenic_completer(self):
        """Ouvre la saisie assistée sur ce partenaire."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sirenic.autocomplete",
            "view_mode": "form",
            "target": "new",
            "context": {"default_partner_id": self.id,
                        "default_recherche": self.name or ""},
        }

    def action_sirenic_client(self):
        """Le geste principal cote CLIENT : peut-on lui ouvrir un encours ?

        Le score de defaillance repond directement a cette question, la ou le
        dossier de facturation repond a « puis-je payer ce fournisseur ». Ce
        sont deux gestes distincts, sur deux routes distinctes.
        """
        self.ensure_one()
        siren = self._sirenic_siren()
        if not siren:
            raise UserError(_(
                "Aucun SIREN exploitable sur cette fiche.\n\n"
                "Renseignez le SIRET ou le numero de TVA francaise, ou utilisez "
                "la saisie assistee pour completer la fiche depuis le registre."))
        corps = self.env["sirenic.client"].appeler("/v1/score/defaillance/%s" % siren)
        self.message_post(body=Markup(rapport_score_html(corps)))
        signaux = corps.get("signaux_bodacc") or {}
        alerte = any(signaux.values())
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Signal au BODACC") if alerte else _("Classe de risque : %s", corps.get("classe")),
                "message": _("Risque a 12 mois : %s", corps.get("risque_12m") or _("non calcule")),
                "type": "warning" if alerte else "success",
                "sticky": False,
            },
        }

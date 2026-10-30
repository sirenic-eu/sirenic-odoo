# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sirenic_api_key = fields.Char(
        string="Clé d'API Sirenic",
        config_parameter="sirenic.api_key",
        help="Votre propre clé, créée sur api.sirenic.eu/compte. Le module ne coûte rien. "
             "Un compte vérifié reçoit des appels offerts chaque mois sur les routes éligibles "
             "(la grille, api.sirenic.eu/offres, dit lesquelles). Au-delà, les appels se paieront "
             "à l'unité avec vos crédits prépayés ; leur recharge par carte n'est pas encore ouverte.",
    )
    sirenic_base_url = fields.Char(
        string="Adresse de l'API",
        config_parameter="sirenic.base_url",
        default="https://api.sirenic.eu",
    )
    # ⚠️ Ce champ N'EST PAS décoratif : `sirenic.client` refuse tout appel tant
    # qu'il est faux. C'est l'opt-in exigé par les règles éditeurs d'Odoo.
    sirenic_consent = fields.Boolean(
        string="J'autorise l'envoi des identifiants à Sirenic",
        config_parameter="sirenic.consent",
    )

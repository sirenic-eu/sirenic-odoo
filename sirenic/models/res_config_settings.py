# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sirenic_api_key = fields.Char(
        string="Clé d'API Sirenic",
        config_parameter="sirenic.api_key",
        help="Votre propre clé, créée sur api.sirenic.eu/compte. "
             "Le module est gratuit ; les appels sont facturés à l'unité par Sirenic.",
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

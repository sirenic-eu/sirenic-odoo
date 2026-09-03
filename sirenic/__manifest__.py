# -*- coding: utf-8 -*-
{
    # ⚠️ 25 caractères maximum, règle de la boutique Odoo. Celui-ci en fait 22.
    "name": "Sirenic KYB & risque",
    "version": "19.0.1.0.0",
    "category": "Accounting/Accounting",
    "summary": "Savoir a qui vous vendez avant d'ouvrir un encours : risque de defaillance, "
               "procedure collective, comptes deposes, sanctions. France et 12 pays d'Europe.",
    "author": "Sirenic",
    "website": "https://api.sirenic.eu",
    "license": "LGPL-3",
    "depends": ["base", "contacts"],
    # Image de couverture de la fiche boutique. Sans elle, Odoo plafonne la
    # note du module à 4/5 et l'affiche en avertissement sur la page publique.
    "images": ["static/description/banner.png"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        # ⚠️ L'ORDRE COMPTE : res_partner_views.xml référence l'action
        # %(action_sirenic_verification)d, donc le fichier qui la DÉFINIT doit
        # être chargé avant. Inverser les deux lignes fait échouer
        # l'installation avec « External ID not found », et rien ne le signale
        # avant le chargement réel.
        "wizards/sirenic_verification_views.xml",
        "wizards/sirenic_autocomplete_views.xml",
        "views/res_partner_views.xml",
    ],
    "installable": True,
    "application": False,
    # ─────────────────────────────────────────────────────────────────────
    # SERVICE EXTERNE ET DONNÉES TRANSMISES.
    # Les règles éditeurs d'Odoo l'exigent explicitement : « if your app
    # collects data to send to another service, the data sent must be clearly
    # explained in your app manifest and store description page, as well as in
    # the application, to get a user opt-in before transmitting data ».
    # D'où ce bloc, la section dédiée dans les Paramètres, ET le refus de tout
    # appel tant que l'opt-in n'est pas coché (voir models/sirenic_client.py).
    # ─────────────────────────────────────────────────────────────────────
    "external_dependencies": {"python": ["requests"]},
    "description": """
Sirenic, vérification d'entreprises françaises et européennes
==============================================================

Ce module appelle un SERVICE EXTERNE : l'API Sirenic (https://api.sirenic.eu).

DONNÉES TRANSMISES, et rien d'autre :
  - le numéro d'identification du partenaire que vous vérifiez (SIREN, SIRET,
    numéro de TVA intracommunautaire ou identifiant de registre national) ;
  - le cas échéant, l'IBAN que vous voulez contrôler.

NE SONT JAMAIS TRANSMIS : le nom de vos contacts, leurs adresses e-mail, vos
factures, vos montants, ni aucune donnée de votre base autre que
l'identifiant contrôlé.

Aucun appel n'est émis tant que vous n'avez pas coché le consentement dans
Paramètres → Sirenic. Le module est gratuit ; les appels à l'API sont facturés
à l'unité par Sirenic, avec votre propre clé.
""",
}

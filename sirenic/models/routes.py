# -*- coding: utf-8 -*-
# FICHIER GÉNÉRÉ PAR generer-routes.py, NE PAS ÉDITER À LA MAIN.
# Source : openapi.json et index.md servis par https://api.sirenic.eu,
# 24 routes retenues.
#
# Critère de sélection, lu dans la spec et non décrété ici : une route entre si
# sa clé de chemin est un SIREN ou un SIRET seul (un geste évident sur une
# fiche partenaire Odoo), sans paramètre de requête obligatoire (le geste n'a
# pas de champ de saisie) et avec une réponse JSON. Les routes de compte et
# celles dont la latence dépasse une action synchrone sont écartées.
#
# Écartées malgré une clé SIREN ou SIRET seule :
#   /v1/entreprise/{siren}/briefing : réponse en text/markdown seulement.
#   /v1/entreprise/{siren}/changements : paramètre de requête obligatoire : depuis.
#   /v1/entreprise/{siren}/dossier : paramètre de requête obligatoire : blocs.
#   /v1/entreprise/{siren}/nouveautes : paramètre de requête obligatoire : depuis.

ROUTES = {
    'v1_entreprise_siren_accords_collectifs': {'chemin': '/v1/entreprise/{siren}/accords-collectifs', 'cle': 'siren', 'libelle': "Accords collectifs d'entreprise d'une société française publiés sur…", 'prix': '0,02\xa0€'},
    'v1_entreprise_siren_agrements': {'chemin': '/v1/entreprise/{siren}/agrements', 'cle': 'siren', 'libelle': 'Agréments et autorisations réglementaires détenus par une entreprise…', 'prix': '0,02\xa0€'},
    'v1_entreprise_siren_alertes': {'chemin': '/v1/entreprise/{siren}/alertes', 'cle': 'siren', 'libelle': "Alertes légales d'une entreprise française issues du BODACC, le…", 'prix': '0,01\xa0€'},
    'v1_entreprise_siren_sante': {'chemin': '/v1/entreprise/{siren}/sante', 'cle': 'siren', 'libelle': "Bilan de santé d'une entreprise française", 'prix': '0,15\xa0€'},
    'v1_entreprise_siren_finances': {'chemin': '/v1/entreprise/{siren}/finances', 'cle': 'siren', 'libelle': "Comptes d'une entreprise française déposés à l'INPI, avec les ratios…", 'prix': '0,01\xa0€'},
    'v1_kyb_siren': {'chemin': '/v1/kyb/{siren}', 'cle': 'siren', 'libelle': 'Consultation KYB', 'prix': '0,15\xa0€'},
    'v1_entreprise_siren_contentieux': {'chemin': '/v1/entreprise/{siren}/contentieux', 'cle': 'siren', 'libelle': 'Décisions des tribunaux de commerce rattachées à une entreprise…', 'prix': '0,01\xa0€'},
    'v1_entreprise_siren_documents': {'chemin': '/v1/entreprise/{siren}/documents', 'cle': 'siren', 'libelle': "Dépôts officiels d'une entreprise française au registre INPI RNE", 'prix': '0,02\xa0€'},
    'v1_entreprise_siren_capital': {'chemin': '/v1/entreprise/{siren}/capital', 'cle': 'siren', 'libelle': "Détention et capital d'une entreprise française, extraits par IA des…", 'prix': '0,35\xa0€'},
    'v1_entreprise_siren_encours': {'chemin': '/v1/entreprise/{siren}/encours', 'cle': 'siren', 'libelle': "Encours d'un nouveau client français", 'prix': '0,12\xa0€'},
    'v1_entreprise_siren_facturation_prep': {'chemin': '/v1/entreprise/{siren}/facturation-prep', 'cle': 'siren', 'libelle': 'Entrée en relation fournisseur', 'prix': '0,02\xa0€'},
    'v1_entreprise_siren': {'chemin': '/v1/entreprise/{siren}', 'cle': 'siren', 'libelle': "Fiche complète d'une entreprise française par SIREN", 'prix': '0,005\xa0€'},
    'v1_entreprise_siren_financements_ue': {'chemin': '/v1/entreprise/{siren}/financements-ue', 'cle': 'siren', 'libelle': "Financements de l'Union pour la recherche et l'innovation reçus par…", 'prix': '0,02\xa0€'},
    'v1_entreprise_siren_marches_publics': {'chemin': '/v1/entreprise/{siren}/marches-publics', 'cle': 'siren', 'libelle': 'Marchés publics et attributions remportés par une entreprise…', 'prix': '0,01\xa0€'},
    'v1_entreprise_siren_marches_publics_ue': {'chemin': '/v1/entreprise/{siren}/marches-publics-ue', 'cle': 'siren', 'libelle': 'Marchés publics européens remportés par une entreprise française…', 'prix': '0,02\xa0€'},
    'v1_entreprise_siren_pi': {'chemin': '/v1/entreprise/{siren}/pi', 'cle': 'siren', 'libelle': "Portefeuille de propriété intellectuelle d'une entreprise française…", 'prix': '0,03\xa0€'},
    'v1_acheteur_siret_profil': {'chemin': '/v1/acheteur/{siret}/profil', 'cle': 'siret', 'libelle': "Profil d'achat d'un acheteur public français (SIRET)", 'prix': '0,02\xa0€'},
    'v1_entreprise_siren_lobbying': {'chemin': '/v1/entreprise/{siren}/lobbying', 'cle': 'siren', 'libelle': "Profil de lobbying et d'influence d'une entreprise française d'après…", 'prix': '0,01\xa0€'},
    'v1_entreprise_siren_risques_industriels': {'chemin': '/v1/entreprise/{siren}/risques-industriels', 'cle': 'siren', 'libelle': "Profil de risque industriel et environnemental d'une entreprise…", 'prix': '0,01\xa0€'},
    'v1_entreprise_siren_concurrents_marches': {'chemin': '/v1/entreprise/{siren}/concurrents-marches', 'cle': 'siren', 'libelle': 'Qui remporte des marchés publics français sur les MÊMES segments CPV…', 'prix': '0,02\xa0€'},
    'v1_score_defaillance_siren': {'chemin': '/v1/score/defaillance/{siren}', 'cle': 'siren', 'libelle': "Score de risque de défaillance d'une entreprise française", 'prix': '0,10\xa0€'},
    'v1_entreprise_siren_emploi': {'chemin': '/v1/entreprise/{siren}/emploi', 'cle': 'siren', 'libelle': "Signaux d'embauche d'une entreprise française, dérivés à la demande…", 'prix': '0,02\xa0€'},
    'v1_entreprise_siren_etablissements': {'chemin': '/v1/entreprise/{siren}/etablissements', 'cle': 'siren', 'libelle': "Tous les établissements (SIRET) d'une entreprise française", 'prix': '0,003\xa0€'},
    'v1_entreprise_siren_trajectoire': {'chemin': '/v1/entreprise/{siren}/trajectoire', 'cle': 'siren', 'libelle': "Trajectoire d'une entreprise française", 'prix': '0,02\xa0€'},
}

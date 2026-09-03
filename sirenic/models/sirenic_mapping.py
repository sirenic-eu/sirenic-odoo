# -*- coding: utf-8 -*-
"""Traduction des réponses Sirenic vers Odoo, fonctions PURES.

Aucune dépendance à Odoo dans ce fichier : c'est délibéré. Le module ne peut
pas être chargé dans un Odoo sur cette machine, donc toute la logique qui
PEUT être éprouvée hors d'Odoo est isolée ici et testée directement.
"""
import re

# Formes juridiques dont le nom commercial suffit : on ne recopie pas la forme
# dans le nom du partenaire, Odoo ayant ses propres champs.
_ETAT_ACTIF = "actif"


def separer_adresse(adresse, code_postal, commune):
    """« 59 RUE LA FAYETTE 75009 PARIS » → « 59 RUE LA FAYETTE ».

    ⚠️ L'API rend l'adresse en UNE chaîne, code postal et commune compris,
    alors qu'Odoo a trois champs distincts. Recopier la chaîne entière dans
    `street` afficherait « 75009 PARIS » deux fois sur l'étiquette d'envoi.
    On retire le suffixe seulement s'il est bien là : une adresse qui ne le
    porte pas doit ressortir intacte, pas tronquée.
    """
    rue = (adresse or "").strip()
    # ⚠️ S'ARRÊTER AU PREMIER SUFFIXE RETIRÉ. Enchaîner les trois coupes
    # mutilait les rues dont le nom contient la commune : « RUE DE PARIS 75009
    # PARIS » devenait « RUE DE », la coupe du code postal + commune était
    # suivie de celle de la commune, qui mordait dans le nom de la voie.
    for suffixe in (
        "%s %s" % (code_postal or "", commune or ""),
        commune or "",
        code_postal or "",
    ):
        suffixe = suffixe.strip()
        if suffixe and rue.upper().endswith(suffixe.upper()):
            return rue[: -len(suffixe)].strip(" ,")
    return rue


def champs_depuis_profil(corps):
    """Les champs Odoo à remplir depuis /v1/entreprise/{siren}.

    Ne rend QUE les champs réellement renseignés : un `None` écraserait une
    saisie manuelle par du vide, ce qui est pire que de ne rien faire.
    """
    siege = corps.get("siege") or {}
    champs = {
        "name": corps.get("denomination"),
        "vat": corps.get("tva_intracommunautaire"),
        "street": separer_adresse(siege.get("adresse"), siege.get("code_postal"), siege.get("commune")),
        "zip": siege.get("code_postal"),
        "city": siege.get("commune"),
        "is_company": True,
    }
    return {k: v for k, v in champs.items() if v not in (None, "", [])}


def avertissement_etat(corps):
    """Un mot si l'entreprise n'est pas active, le silence serait trompeur."""
    etat = corps.get("etat_administratif")
    if etat and etat != _ETAT_ACTIF:
        return "⚠️ Cette entreprise est déclarée « %s » au registre." % etat
    return ""


def _n(bloc, cle):
    v = (bloc or {}).get(cle)
    return len(v) if isinstance(v, list) else (v or 0)


def rapport_kyb_html(corps):
    """Le dossier KYB en HTML lisible, pour le fil de discussion.

    Le JSON brut n'est pas un rapport : personne ne justifie une décision de
    paiement en collant 40 Ko d'accolades. On rend ce qui SERT à décider, et
    on nomme ce qui manque plutôt que de le taire.
    """
    ident = corps.get("identite") or {}
    bodacc = corps.get("alertes_bodacc") or {}
    fin = corps.get("finances") or {}
    sanctions = corps.get("criblage_sanctions") or {}

    procedures = _n(bodacc, "procedures_collectives")
    radiations = _n(bodacc, "radiations")
    statut_sanctions = sanctions.get("statut") or "non consulté"

    # L'en-tête dit d'abord ce qui BLOQUE. Un rapport qui commence par
    # l'adresse du siège fait manquer la procédure collective.
    alarmes = []
    if procedures:
        alarmes.append("%d procédure(s) collective(s) au BODACC" % procedures)
    if radiations:
        alarmes.append("%d radiation(s)" % radiations)
    # ⚠️ NOMMER LA CIBLE ET COMPTER. Mesuré sur un dossier réel : le statut
    # « correspondances_a_verifier » portait sur UN dirigeant homonyme, pas sur
    # l'entreprise. Afficher le statut nu ferait lire « fournisseur sanctionné »
    # là où il faut lire « un homonyme à lever ».
    touchees = [(c.get("cible"), c.get("role"), len(c.get("correspondances") or []))
                for c in (sanctions.get("cibles") or [])
                if c.get("correspondances")]
    if touchees:
        alarmes.append("criblage : %s" % ", ".join(
            "%d correspondance(s) sur %s (%s)" % (n, cible, role)
            for cible, role, n in touchees))
    if (ident.get("etat_administratif") or _ETAT_ACTIF) != _ETAT_ACTIF:
        alarmes.append("entreprise %s au registre" % ident.get("etat_administratif"))

    entete = ("<p style='color:#b00'><b>À vérifier avant de payer :</b> %s</p>" % " · ".join(alarmes)
              if alarmes else "<p style='color:#080'><b>Aucun signal bloquant relevé.</b></p>")

    lignes = [
        ("Dénomination", ident.get("denomination")),
        ("SIREN", corps.get("siren")),
        ("TVA intracommunautaire", corps.get("tva_intracommunautaire")),
        ("Forme juridique", ident.get("nature_juridique")),
        ("Activité principale", ident.get("activite_principale")),
        ("État au registre", ident.get("etat_administratif")),
        ("Annonces BODACC", "%s au total, dont %s procédure(s) collective(s)"
            % (_n(bodacc, "total_annonces"), procedures)),
        ("Exercices comptables publiés", _n(fin, "nombre_exercices")),
        ("Criblage sanctions", "%s, %s liste(s) officielle(s) consultée(s), %s absente(s)"
            % (statut_sanctions, _n(sanctions, "listes_consultees"), _n(sanctions, "listes_absentes"))),
        ("Complétude du dossier", "%s %%" % corps.get("score_completude")),
    ]
    corps_html = "".join(
        "<tr><td style='padding:2px 12px 2px 0'><b>%s</b></td><td>%s</td></tr>" % (k, v)
        for k, v in lignes if v not in (None, "")
    )

    manquants = corps.get("blocs_manquants") or []
    absent = ("<p><i>Blocs absents du dossier : %s.</i></p>" % ", ".join(map(str, manquants))
              if manquants else "")
    fraicheur = corps.get("data_freshness")
    pied = "<p style='font-size:90%%;color:#666'>%s</p>" % fraicheur if fraicheur else ""

    # Une correspondance de criblage est un HOMONYME à lever, pas un verdict.
    # Le taire ferait porter au lecteur une conclusion que la donnée ne permet
    # pas, exactement le faux plausible que ce produit s'interdit.
    note = ("<p><i>Une correspondance de criblage signale un homonyme à lever sur "
            "les listes officielles ; elle n'établit pas qu'une personne ou une "
            "entreprise est sanctionnée.</i></p>" if touchees else "")
    return "<div><h4>Dossier KYB Sirenic</h4>%s<table>%s</table>%s%s%s</div>" % (
        entete, corps_html, note, absent, pied)

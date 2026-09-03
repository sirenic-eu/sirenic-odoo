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


# Classes de risque, de la plus saine a la plus degradee. La couleur suit la
# CLASSE rendue par l API, jamais une interpretation locale du score.
_COULEUR_CLASSE = {
    "sain": "#080", "correct": "#080", "a_surveiller": "#b60",
    "fragile": "#b00", "critique": "#b00", "defaillant": "#b00",
}


def rapport_score_html(corps):
    """Le risque de defaillance d un CLIENT, rendu pour decider d un encours.

    ⚠️ CE N EST PAS UNE NOTE DE CREDIT, et l API le dit dans son propre
    disclaimer : « NI un avis de solvabilite, NI une notation de credit ».
    Le rapport le reprend mot pour mot. Presenter ce score comme une notation
    ferait porter au lecteur une conclusion que la donnee ne permet pas.
    """
    classe = corps.get("classe") or "inconnue"
    couleur = _COULEUR_CLASSE.get(classe, "#666")
    signaux = corps.get("signaux_bodacc") or {}

    # Un signal BODACC prime sur le score : une liquidation en cours ne se
    # discute pas avec un ratio.
    alarmes = [nom.replace("_", " ") for nom, present in signaux.items() if present]
    if alarmes:
        entete = ("<p style='color:#b00'><b>Signal au BODACC :</b> %s. "
                  "Aucun encours ne devrait etre ouvert sans verification.</p>"
                  % ", ".join(alarmes))
    else:
        entete = ("<p style='color:%s'><b>Classe de risque : %s</b> "
                  "(risque a 12 mois : %s)</p>"
                  % (couleur, classe, corps.get("risque_12m") or "non calcule"))

    lignes = [
        ("Denomination", corps.get("denomination")),
        ("Classe de risque", classe),
        ("Risque a 12 mois", corps.get("risque_12m")),
        ("Score", corps.get("score_risque")),
        ("Confiance du modele", corps.get("confiance")),
        ("Exercice de reference", "%s (%s mois d anciennete)"
            % (corps.get("exercice_reference"), corps.get("age_exercice_mois"))
            if corps.get("exercice_reference") else None),
    ]
    table = "".join(
        "<tr><td style='padding:2px 12px 2px 0'><b>%s</b></td><td>%s</td></tr>" % (k, v)
        for k, v in lignes if v not in (None, "")
    )

    # ⚠️ L AGE DE L EXERCICE EST DECISIF et doit se lire sans le chercher : un
    # score bati sur des comptes de vingt mois ne dit rien du trimestre en
    # cours. Le taire rendrait le chiffre plus sur qu il ne l est.
    age = corps.get("age_exercice_mois")
    vieux = ("<p style='color:#b60'><i>Ce score repose sur des comptes vieux de "
             "%s mois : il ne dit rien de la situation recente.</i></p>" % age
             if isinstance(age, int) and age >= 18 else "")

    reserves = []
    for cle in ("avertissement_perimetre", "note_tresorerie"):
        if corps.get(cle):
            reserves.append(str(corps[cle]).split(" / ")[0])
    bloc_reserves = ("<p style='font-size:90%%;color:#666'>%s</p>" % " ".join(reserves)
                     if reserves else "")

    avert = ("<p style='font-size:90%;color:#666'><b>Ce n'est ni un avis de "
             "solvabilite, ni une notation de credit</b>, mais un indicateur "
             "d aide a la decision, non contractuel.</p>")

    return ("<div><h4>Risque de defaillance</h4>%s<table>%s</table>%s%s%s</div>"
            % (entete, table, vieux, bloc_reserves, avert))

# Sirenic pour Odoo

Module Odoo 19 : vérifier un fournisseur avant de le payer, registre officiel,
TVA, IBAN, procédure collective, pour la France et l'Europe.

## Installation

Copier `sirenic/` dans le dossier des addons, redémarrer Odoo, puis
*Applications → Mettre à jour la liste* et installer **Sirenic KYB & risque**.

⚠️ **Odoo Online (SaaS) n'accepte aucun module tiers.** Ce module ne s'installe
que sur **Odoo.sh** et en **on-premise**. Les utilisateurs d'Odoo Online passent
par [notre application Make](https://www.make.com/en/integrations), qui atteint
Odoo par son API externe.

## Configuration

*Paramètres → Sirenic* : lire ce qui est transmis, cocher le consentement, et
coller sa clé d'API (créée sur https://api.sirenic.eu/compte).

Aucun appel n'est émis tant que le consentement n'est pas coché, la garde vit
dans `models/sirenic_client.py`, pas dans les vues, pour qu'une action planifiée
ne puisse pas la contourner.

## Régénérer le catalogue de routes

`sirenic/models/routes.py` est **généré**, jamais édité à la main, depuis deux
surfaces servies par l'API, téléchargées et jamais commitées :

```bash
curl -sSf https://api.sirenic.eu/openapi.json -o openapi.json
curl -sSf https://api.sirenic.eu/index.md -o index.md
curl -sSf https://api.sirenic.eu/.well-known/mcp.json -o mcp.json  # lu par --verifier seulement
python3 generer-routes.py
```

- `openapi.json` donne les chemins, leurs paramètres (en ligne ou en `$ref`),
  leurs formats de réponse et leur prix (`x-price`).
- `index.md`, l'accueil français, donne la description française de chaque
  route : le libellé de la liste déroulante en est la première proposition,
  coupée au mot et signalée par « … » au-delà de 70 caractères.
- Le prix s'affiche en euros, au même nombre que la grille : un crédit vaut un
  euro, et l'utilisateur d'Odoo paie avec sa clé, en crédits. Le générateur
  refuse si ce prix diffère de celui qu'affiche `index.md`.

Une route entre si sa clé de chemin est un SIREN ou un SIRET seul (un geste
évident sur une fiche partenaire), sans paramètre de requête obligatoire (le
geste n'a pas de champ de saisie) et avec une réponse JSON ; les routes de
compte et celles dont la latence dépasse une action synchrone sont écartées.
Les routes écartées malgré une clé SIREN ou SIRET sont nommées, avec leur
raison, en tête de `routes.py`.

Le générateur refuse (code 1) plutôt que d'inventer : une route retenue sans
description française, un prix en désaccord, ou un `index.md` dont le tableau
des routes a changé de forme. Un rouge de ce genre vient alors d'une refonte de
l'accueil de l'API, pas d'Odoo.

## Contrôles

```bash
python3 tester-generateur.py          # le générateur, sur une petite spec de forme servie
python3 generer-routes.py --verifier  # routes.py et la fiche, contre la grille et l'offre servies
python3 controler-module.py           # le module, statiquement
```

Les trois tournent dans la CI publique du dépôt (`.github/workflows/catalogue.yml`),
à chaque poussée et chaque lundi : la dérive ne vient pas d'ici, elle vient d'une
route ajoutée ou changée côté API. `--verifier` régénère en mémoire, refuse
toute différence avec `routes.py`, et relit ce que la fiche boutique dit que le
service peut contredire : « à partir de … € » (le prix de la saisie assistée,
qu'aucune route du catalogue ne passe en dessous), et, contre
`/.well-known/mcp.json` téléchargé en `mcp.json` comme les deux autres entrées,
le nombre d'appels offerts par mois, la valeur d'un crédit et « leur recharge
par carte n'est pas encore ouverte ». Les textes que le module montre (chaînes
Python du manifeste, des messages et des aides, texte et attributs des vues XML,
traductions `.po` s'il y en a ; pas les commentaires) passent les mêmes refus,
fichier par fichier, et deux de plus : aucun ne parle de recharge hors de cette
phrase tant que le service dit la recharge fermée, et aucun ne dit plus
« facturé à l'unité », l'offre d'avant.

`controler-module.py` vérifie le manifeste, la présence des fichiers déclarés, **l'ordre de
chargement** (une action référencée avant d'être définie fait échouer
l'installation), les droits d'accès, la bonne formation des XML et la
compilation Python.

Il ne contrôle **pas** le chargement réel dans Odoo, la validité des `xpath`
d'héritage, ni le comportement à l'exécution : ceux-là demandent une instance.

## Régénérer les fixtures d'essai

`tester-mapping.py` s'appuie sur des réponses **réelles** de l'API, pas sur des
fixtures écrites à la main : une fixture inventée encode l'hypothèse qu'on teste
et ne peut que la confirmer. Ces réponses ne sont pas commitées, un dossier KYB
porte les noms des dirigeants, et les republier serait une publication nouvelle.

```bash
export SIRENIC_API_KEY=srn_live_…
for r in "recherche?q=danone" "entreprise/552032534" "kyb/552032534"; do
  curl -s -H "X-Api-Key: $SIRENIC_API_KEY" "https://api.sirenic.eu/v1/$r" \
    -o "reponse-$(echo "$r" | tr '/?=' '___' | cut -c1-20).json"
done
python3 tester-mapping.py
```

## Banc d'essai local (Odoo 19 réel)

Le module a été chargé et exercé dans un vrai Odoo 19, c'est là qu'ont été
trouvés les défauts que les contrôles statiques ne voient pas (`@fields.depends`
au lieu de `@api.depends`, et le HTML du fil échappé faute de `Markup`).

```bash
uv python install 3.12 && uv venv --python 3.12 .venv-odoo
git clone --depth 1 -b 19.0 https://github.com/odoo/odoo.git odoo-src
# python-ldap et psycopg2 exigent un compilateur : on les écarte ou on prend
# la version pré-compilée. Aucun paquet système n'est requis.
grep -v '^python-ldap' odoo-src/requirements.txt \
  | sed 's/^psycopg2==/psycopg2-binary==/' > requirements-sans-ldap.txt
uv pip install --python .venv-odoo/bin/python -r requirements-sans-ldap.txt
# Odoo REFUSE de tourner sous le superutilisateur PostgreSQL : rôle dédié.
psql -c "CREATE ROLE odoo LOGIN CREATEDB" -c "CREATE DATABASE odoo_essai OWNER odoo"
.venv-odoo/bin/python odoo-src/odoo-bin -d odoo_essai --db_user=odoo \
  --addons-path=odoo-src/addons,. -i sirenic --stop-after-init
```

## Régénérer la bannière

`sirenic/static/description/banner.png` est commité, il n'y a rien à faire pour
installer le module. Pour la refabriquer, il faut les polices du site, extraites
de nos propres woff2 et **non versionnées** (Plus Jakarta Sans et Manrope sont
sous OFL, dont la redistribution exige de joindre le texte de licence) :

```bash
uv pip install --python .venv-odoo/bin/python fonttools brotli
mkdir -p polices
# convertir les woff2 du site en ttf, puis instancier les graisses voulues
# (les deux polices sont variables, axe wght de 200 a 800)
```

## Une étoile pour ce dépôt

Si ce module vous a évité une vérification à la main, une étoile aide d'autres utilisateurs d'Odoo à le trouver.

[![Star History Chart](https://api.star-history.com/svg?repos=sirenic-eu/sirenic-odoo&type=Date)](https://star-history.com/#sirenic-eu/sirenic-odoo&Date)

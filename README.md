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

`sirenic/models/routes.py` est **généré**, jamais édité à la main :

```bash
curl -s https://api.sirenic.eu/openapi.json -o openapi.json
python3 generer-routes.py
```

Le générateur ne retient que les routes dont la clé de chemin est un SIREN ou un
SIRET seul, celles qui ont un geste évident sur une fiche partenaire, et
écarte celles dont la latence dépasse une action synchrone.

## Contrôles

```bash
python3 controler-module.py
```

Vérifie le manifeste, la présence des fichiers déclarés, **l'ordre de
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

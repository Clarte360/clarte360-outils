# AUDIT DE FUSION — RC2-2 / RC2-1_1 — 01/10/2026

## Objet
Construire `clarte360-gestion-actions-v3.0.0-INTERVENANTS-RC2-2-1-RECETTE` sans perdre les évolutions fonctionnelles de RC2-2 et en réintégrant les modifications réellement apparues dans GitHub/VPS après les deux PULL liés à IPIP-NEO-120 et à la correction PIP RIASEC.

## Sources comparées
- Base commune : `clarte360-gestion-actions-v3.0.0-INTERVENANTS-RC2-1-RECETTE.zip`
  - SHA-256 : `d5cbd3d12a89fb9ff5f89c32381febb5c113d242cc6f0310f6d8c4bc694d0f21`
- Branche métier RC2-2 : `clarte360-gestion-actions-v3.0.0-INTERVENANTS-RC2-2-RECETTE.zip`
  - SHA-256 : `2b2ca16cbe2be1b25b06d91b4370335faf170b20a077821ade2f1a255afd9906`
- Photographie GitHub/VPS : `clarte360-gestion-actions-v3.0.0-INTERVENANTS-RC2-1_1-RECETTE.zip`
  - SHA-256 : `75ebeb7fa9b7baddcef5b123825729ff02ee377084e14b287b2d88737c8aea6b`

## Méthode
Le rapprochement a été fait en trois voies avec RC2-1 comme ancêtre commun :
1. RC2-1 -> RC2-2 pour identifier le chantier Intervenants propre à RC2-2 ;
2. RC2-1 -> RC2-1_1 pour isoler les modifications réellement apparues après les deux PULL ;
3. fusion contrôlée dans RC2-2, sans remplacement aveugle de fichiers complets.

Les différences de fins de ligne n'ont pas été considérées comme des différences fonctionnelles.

## Diff réel RC2-1 -> RC2-1_1
RC2-1_1 ne constitue pas une nouvelle branche métier concurrente. Les différences fonctionnelles utiles sont limitées à :
- `app.py` : branche IPIP dans l'espace bénéficiaire et `tool_launch_page`, rafraîchissement du statut connecteur IPIP ;
- `services.py` : connecteur IPIP, lancement signé, outbox, événements, archivage PDF, statut connecteur ; correction de `build_pip_prescription_launch()` ;
- `worker.py` : consommation de l'outbox IPIP et rafraîchissement du connecteur ;
- `config/tool_registry.json` : ajout de `IPIP_NEO120` et date du registre ;
- `tests/test_ipip_rc1_connector.py` : nouveaux tests du contrat IPIP.

RC2-1_1 contient également des fichiers runtime qui ne sont PAS du code source et ne doivent pas être réintégrés :
- `data/professional_documents/*` ;
- `data/signatures/*`.
Ils sont explicitement exclus de RC2-2-1.

## Décisions fichier par fichier

| Fichier / zone | Décision | Justification |
|---|---|---|
| `.gitignore` | A CONSERVER DE RC2-2 | RC2-2 renforce l'exclusion des données persistantes et des documents professionnels. |
| `CHANGELOG.md` | A CONSERVER DE RC2-2 + FUSION | Historique RC2-2 conservé ; ajout d'une entrée RC2-2-1. |
| `app.py` | A FUSIONNER | RC2-2 conserve le nouveau menu Intervenants, identité, purge, IA/Qualifications ; IPIP est ajouté sans supprimer ces changements. Ajout complémentaire : une prescription PIP/IPIP `TERMINE` n'affiche plus un bouton de relance. |
| `.streamlit/secrets.example.toml` | A FUSIONNER / DOCUMENTER | Ajout d'un exemple non sensible `IPIP_CONNECTOR` (clé HMAC factice, répertoire pending à renseigner, `DATA_ROOT`), sans inclure aucun secret réel. |
| `branding.py` | A CONSERVER DE RC2-2 puis VERSIONNER | Seule la version devient `3.0.0-INTERVENANTS-RC2-2-1`. |
| `config/tool_registry.json` | A REINTEGRER DE RC2-1_1 | Ajout IPIP_NEO120 nécessaire. Aucun autre outil n'est modifié sémantiquement. |
| `db.py` | A CONSERVER DE RC2-2 | Contient les évolutions identité / modèle RC2-2 ; aucune modification RC2-1_1. |
| `qualification_ai.py` | A CONSERVER DE RC2-2 | Contient analyse différentielle SHA-256 / PDF scannés / logique RC2-2 ; aucune modification RC2-1_1. |
| `services.py` | A FUSIONNER | Conservation de toutes les fonctions RC2-2 + ajout du connecteur IPIP + correction PIP. Correctifs de cohérence ajoutés : IPIP bloque `TERMINE`, PIP/IPIP autorisent une nouvelle prescription après une précédente `TERMINE`, et `upsert_tool_catalog()` conserve `EXTERNAL_SIGNED` uniquement pour PIP/IPIP. |
| `worker.py` | A REINTEGRER DE RC2-1_1 | Ajout outbox IPIP, sans toucher aux traitements RC2-2. |
| `tests/test_ipip_rc1_connector.py` | A REINTEGRER DE RC2-1_1 | Garde-fous IPIP conservés. |
| `tests/test_j2c_rc7_tools_simple.py` | A FUSIONNER | Hypothèse historique « seul PIP est EXTERNAL_SIGNED » devenue obsolète. Test adapté pour PIP + IPIP tout en conservant le garde-fou : un outil arbitraire reste `HUB_REDIRECT`. |
| Tests RC2-2 de version / tables / identité | A CONSERVER DE RC2-2 | Seule l'assertion de version passe à RC2-2-1. |
| `data/professional_documents/*` de RC2-1_1 | A NE PAS RETENIR | Données runtime réelles/persistantes, interdites dans une recette source. |
| `data/signatures/*` de RC2-1_1 | A NE PAS RETENIR | Signatures runtime, interdites dans une recette source. |

## Corrections de cohérence ajoutées pendant la fusion
### 1. Politique EXTERNAL_SIGNED
Le code historique forçait tout outil autre que PIP en `HUB_REDIRECT`. Cela aurait détruit le contrat IPIP lors d'une mise à jour depuis l'administration.

RC2-2-1 autorise explicitement :
- `PIP_RIASEC_ONET` -> `EXTERNAL_SIGNED` ;
- `IPIP_NEO120` -> `EXTERNAL_SIGNED` ;
- un code arbitraire demandant `EXTERNAL_SIGNED` -> ramené à `HUB_REDIRECT`.

### 2. Règle de reprise PIP / IPIP
- `A_FAIRE`, `CONSULTE`, `EN_COURS` : lancement/reprise autorisés ;
- pas d'expiration métier arbitraire à 168 h pour le lancement spécialisé PIP ;
- IPIP suit la même logique et ne consulte pas `expires_at` pour son lancement spécialisé ;
- `TERMINE` : le même identifiant de prescription ne peut pas relancer une passation ;
- une nouvelle passation est possible uniquement via une nouvelle prescription.

Le garde-fou de doublon a donc été ajusté pour PIP/IPIP : une prescription antérieure `TERMINE` n'empêche plus la création explicite d'une nouvelle prescription.

### 3. Espace bénéficiaire multi-outils
L'ajout IPIP est isolé par type d'outil. Une prescription IPIP ne remplace ni PIP ni les outils HUB génériques. Les branches de lancement sont distinctes et les fonctions correspondantes existent dans `services.py`.

## Fichiers fusionnés / modifiés pour RC2-2-1
- `app.py`
- `services.py`
- `worker.py`
- `.streamlit/secrets.example.toml`
- `config/tool_registry.json`
- `branding.py`
- `tests/test_j2c_rc7_tools_simple.py`
- `tests/test_ipip_rc1_connector.py` (ajout)
- `tests/test_rc2_2_1_consolidation.py` (ajout)
- tests de version RC2-2 mis à jour vers RC2-2-1
- `CHANGELOG.md`

Les autres fichiers fonctionnels RC2-2 sont conservés à l'identique.

## Risque de plantage `build_ipip_prescription_launch`
Le package contient simultanément :
- les appels dans `app.py` ;
- la définition dans `services.py` ;
- l'import global `from services import *` utilisé par `app.py` ;
- les fonctions worker associées ;
- des tests vérifiant la présence des deux côtés.

Le `NameError` observé historiquement après un PULL était lié au processus Streamlit non redémarré et non à une absence dans le package consolidé. Après déploiement, le redémarrage du service web est donc obligatoire.

## État GitHub / VPS attendu
RC2-2-1 n'est PAS déployée par le présent travail.
Après intégration manuelle du ZIP dans GitHub par l'utilisateur et PUSH :
- GitHub doit contenir exactement le code RC2-2-1 ;
- le VPS doit rester inchangé jusqu'au PULL volontaire ;
- lors du PULL VPS, `clarte360-emargements.service` ET `clarte360-emargements-worker.service` doivent être redémarrés après tests/compilation ;
- URL, port, services et emplacement VPS existants restent inchangés.

## Conclusion d'audit
La fusion ne remplace pas RC2-2 par RC2-1_1. RC2-2 reste la base fonctionnelle. Les modifications IPIP/PIP de RC2-1_1 ont été réintégrées de façon ciblée, avec correction du garde-fou de type de lancement et de la règle de nouvelle prescription après `TERMINE`.

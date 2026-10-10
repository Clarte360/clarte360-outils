# P4 - Espace Client / DRH - RC1 locale

**Statut : candidat a valider, non installe.** Base du code : ZIP complet P3-RC1. Livrable complet avec ses tests et modules anterieurs.

## Usage

1. Un administrateur selectionne un CONTACT EXISTANT dans CRM0 (transitoire) puis cree un compte Client **sans autorisation automatique**.
2. Il attribue un role `CLIENT_ADMIN` ou `PRESCRIPTEUR` sur chaque action explicitement autorisee, et coche separement les droits de depot et de telechargement si justifies.
3. Il emet un lien a usage unique, expire (72 h par defaut, 1 a 168 h maximum), le transmet manuellement et le destinataire active un mot de passe d'au moins 12 caracteres.
4. L'utilisateur accede a son espace via `?client_portal=1`. Les controles de droit sont **cote service** et verifies a chaque operation, pas par le seul menu.
5. Pour une formation collective autorisee, l'espace peut restituer references action, planning collectif et indicateurs agreges si l'effectif est d'au moins cinq. Le portail ne fournit aucun questionnaire, avis individuel, score ou document sensible de bilan.
6. Une piece a remettre au Client doit suivre **ENREGISTRER BROUILLON -> VALIDER -> PUBLIER -> PARTAGER EXPLICITEMENT avec un compte autorise**. Une publication seule ne cree aucune remise.
7. Les depots du Client sont des **brouillons prives** associes a son compte et a son action. Un autre compte n'accede pas a ces pieces; elles ne sont pas visibles des beneficiaires.
8. L'admin peut retirer l'habilitation sur une action, revoquer un document ou desactiver un compte. La readmission n'ouvre pas les anciens droits par magie.

## Securite, donnees et migration

- Tables additives `client_portal_accounts`, `client_portal_tokens`, `client_action_grants`, `client_document_shares`, `client_login_attempts`. Aucun nouveau referentiel Clients/Entites/Financement.
- Les contacts archives et les comptes dont l'e-mail ne correspond plus au CRM sont refuses. Un changement d'e-mail doit etre regularise manuellement; droits et sessions precedents sont revoques.
- Signatures, contrats, factures, reponses individuelles, questionnaires BC, pieces de mission intervenant : jamais accessibles automatiquement depuis P4.
- Respecter le PRA central `99 BACKUP VPS CLARTE360`; avant une migration de production, verifier une restauration complete sur environnement isole, y compris coherence SQLite.
- Ne jamais deplacer/effacer le `data/` existant pendant la livraison. Le ZIP n'inclut ni donnees reelles, ni secrets, ni captures de documents, ni images de signatures.

## Contrats non implements / limites

- **CRM17** doit rester proprietaire des Clients, Entites, Prescripteurs et objets financiers. P4 se borne a creer des comptes et habilitations *operationnelles* via CRM0 jusqu'a l'API cible (aucune duplication de fiches entreprise ou de factures).
- **Contractualisation** reste le moteur de documents commerciaux. La restitution directe d'un contrat ou d'une facture sous droits client requiert l'API et le workflow de validation CRM17/Contractualisation. Elle n'est **pas livree** dans cette RC1.
- **Compétences & Projets GO-14** demeure suspendu; aucun code specialise ni droit de divulgation ajoute.
- Une verification en navigateur Streamlit authentifie, des connecteurs Microsoft Teams/Graph/Entra/SMTP et du PRA reste indispensable en recette P5.
- Les durees de conservation/destruction, particulierement pour le bilan de competences, n'ont pas ete devinees ni appliquees automatiquement.

## Recette locale

Installer les dependances de `requirements.txt` dans un environnement distinct, puis executer depuis la racine du code :

```bash
PYTHONPATH=. python -m pytest -q --disable-warnings
python -m compileall -q .
```

Les logs de campagne verifiee figurent dans le dossier de livrables P4, hors du ZIP de code.

**Gouvernance :** Aucun commit/push/fetch GitHub de l'assistant, aucune intervention VPS. Import GitHub Desktop et deploiement exclusivement sur decision du proprietaire.

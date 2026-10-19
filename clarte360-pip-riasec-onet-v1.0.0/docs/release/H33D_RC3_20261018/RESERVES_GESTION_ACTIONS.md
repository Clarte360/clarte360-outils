# Réserves externes — Gestion des actions / formations
Date : 18 octobre 2026. Source récepteur examinée : 75af19d.
**Aucune modification de GDA dans la livraison PIP H3.3-D-RC3.**

## R-GDA-01 — Historique visible des rapports
La clé logique d'un document associe action, bénéficiaire, participant, catégorie, audience et nom affiché normalisé. Elle n'inclut pas la prescription ou la passation. Un rapport ultérieur de même nom peut devenir la version courante, l'ancienne référence passant à `REMPLACE` et n'étant plus affichée dans la liste bénéficiaire.
L'audit local a conservé cinq fichiers sous trois prescriptions mais affiché deux rapports courants. Ce constat ne prouve pas à lui seul la conservation de chaque fichier réel sur le VPS.
**Réserve : afficher plusieurs passations séparément ou rendre leur historique accessible relève d'une évolution GDA.**

## R-GDA-02 — Un rapport de chaque type par prescription
`archive_pip_report_pdf` déduplique par prescription et type PIP_REPORT / ONET_REPORT. Un autre contenu du même type pour la même prescription est refusé. Une nouvelle session navigateur n'est pas une nouvelle prescription. Le correctif PIP réutilise le premier rapport et ne contourne pas cette règle.

## R-GDA-03 — Noms techniques figés
Le récepteur actuel reconnaît uniquement `rapport_pip_riasec_clarte360.pdf` et `rapport_onet_interest_profiler.pdf`. Renommer les PDF côté PIP pour forcer l'affichage de plusieurs versions provoquerait un rejet. Ces noms restent inchangés.

## R-GDA-04 — Notifications et accusé de réception
Les notifications destinées à l'intervenant et celles liées à un téléchargement restent à examiner dans GDA. L'écran PIP confirme l'enregistrement et la demande de transmission, pas la visibilité effective dans GDA.
Aucun nouvel accusé de réception fictif n'est ajouté au protocole.

## R-GDA-05 — Autre appel à contrôler hors PIP
L'audit de services.py a repéré dans le traitement IPIP une référence à l'archivage PIP utilisant `outbox_path`. Ce point doit être examiné par le chantier GDA/IPIP, hors de ce correctif. Il n'est pas modifié ici.

## Réparation historique
Aucun rejeu des anciens événements, aucune remise à zéro du curseur GDA, aucune suppression de prescription ou de PDF. Une éventuelle reprise historique doit être une opération distincte, justifiée et autorisée.

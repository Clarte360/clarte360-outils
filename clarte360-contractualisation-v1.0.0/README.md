# Clarté360 – Contractualisation

Version interne : **1.2.0-VPS-IMPORT-MACRO**.

Application Streamlit administrative installée sur le VPS Clarté360.

## Principe

La base Excel Clarté360 reste sur le poste de travail. Elle est chargée dans l'application uniquement comme référence de lecture. L'application ne réécrit jamais le `.xlsm`.

Workflow :

1. charger la base `.xlsm` de référence ;
2. créer un nouveau contrat depuis une APS JSON **ou** reprendre un `NO_CLAR` déjà renseigné ;
3. compléter les informations contractuelles et les financeurs ;
4. générer le PDF contractuel disponible pour le moteur activé ;
5. préparer éventuellement plusieurs contrats dans la même session ;
6. télécharger en fin de session un fichier Excel d'import `CONV ADM + FINANCEMENTS`, le JSON de session et le ZIP des documents ;
7. injecter ensuite localement ce fichier dans la vraie base via la macro Clarté360 dédiée.

Le moteur PDF actuellement activé est : **Bilan de compétences – particulier bipartite**. Les autres familles de contrats seront ajoutées progressivement dans la même application.

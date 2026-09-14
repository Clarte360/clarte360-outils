# CLARTÉ360 — Gestion des actions — I9-B

Date : 12 septembre 2026
Source : I9-A validée techniquement
Objet : actions, participants, import, modalités, calendrier, communications et contresignature

## Décisions métier appliquées

- La modalité est séparée de l'organisation INTRA/INTER/INDIVIDUEL et du champ libre Lieu / précision.
- Bilan de compétences et Coaching : Présentiel, Distanciel-visioconférence, Hybride.
- Formation : Présentiel, Distanciel-visioconférence, Hybride, E-learning, Blended learning.
- Une date Excel numérique telle que 31364 est normalisée automatiquement avant création de l'identité.
- Un bénéficiaire permanent n'est rattaché automatiquement que sur correspondance exacte Nom + Prénom + Date de naissance.
- Un participant ajouté après activation déclenche une communication de planning dédiée.
- La contresignature devient possible avant la fin du créneau dès que tous les statuts participants sont définitifs.
- Si des statuts restent non finalisés, la demande de contresignature devient exigible à l'heure de fin du créneau.
- Les demandes de contresignature utilisent un lien vers l'espace intervenant ciblant l'action et le créneau.

## Évolutions techniques

### Base de données
- ajout additif de `actions.delivery_mode` ;
- ajout de `communication_events` pour tracer les communications I9 sans remplacer les historiques I8 ;
- index de suivi des communications.

### Modalités
- helpers `allowed_delivery_modes`, `normalize_delivery_mode`, `delivery_mode_label` ;
- UI de création et de modification avec liste contrôlée par type de prestation ;
- champ `Lieu / précision` séparé.

### Import Excel
- `normalize_date_value` accepte date/datetime, date Excel, numéro de série Excel, JJ/MM/AAAA, JJ-MM-AAAA et ISO AAAA-MM-JJ ;
- rejet explicite des formats ambigus/impossibles ;
- conservation de la valeur source dans l'audit participant lorsqu'une conversion a été réalisée.

### Identités
- rattachement automatique exact à un bénéficiaire permanent ;
- aucune fusion automatique sur le seul nom/prénom ;
- correspondances ambiguës journalisées.

### Calendrier
- bornes cohérentes du décalage personnalisé : -1440 à +1440 minutes ;
- durée d'émargement après fin : 0 à 10080 minutes ;
- validation serveur identique à l'UI.

### Communications
- journal générique avec statuts : A_ENVOYER, EN_FILE, ENVOYE, ECHEC, RELANCE, ANNULE ;
- planning d'un participant ajouté après activation mis en file automatiquement ;
- demande de contresignature mise en file automatiquement ;
- affichage du journal I9 dans l'onglet Envois & relances.

### Contresignature
- règle I3 « attendre obligatoirement la fin » remplacée par la décision I9-B validée ;
- tous statuts définitifs => contresignature immédiatement autorisée ;
- statuts en attente => blocage de la signature, mais notification à l'intervenant à l'heure de fin ;
- compteur de tâches de contresignature dans l'espace intervenant ;
- lien de notification prépositionné sur l'action/créneau ;
- cadre manuscrit adapté à une largeur mobile de 320 px.

## Non-régression

La modification des deux tests historiques I3 relatifs au blocage temporel est volontaire et documentée : la décision métier I9-B remplace explicitement cette règle. Toutes les autres exigences I8/I9-A restent inchangées.

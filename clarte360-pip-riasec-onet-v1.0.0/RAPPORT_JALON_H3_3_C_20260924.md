# CLARTÉ360 PIP RIASEC / O*NET — Jalon H3.3-C

## Objet
Refonte de la restitution de l'étude PIP ↔ O*NET conformément au CDC H3.3.

## Base
H3.3-C est construit exclusivement à partir du jalon H3.3-B officiel.

## Évolutions
- séparation explicite des populations : N PIP, N PIP + O*NET, N PIP seul, N avec ressenti exploitable ;
- calcul de la concordance individuelle stricte de 0 à 6 positions identiques ;
- calcul de la moyenne du nombre de positions identiques sur 6 ;
- calcul de la concordance de chaque position 1 à 6 ;
- affichage systématique n/N et pourcentages ;
- synthèse du ressenti à partir des seules questions réellement enregistrées ;
- maintien des indicateurs de qualité des items uniquement dans un espace technique replié ;
- correction de lecture des anciens fichiers : `completed_at` sans ressenti ne signifie plus TERMINE ;
- restitution collective, pseudonymisée, descriptive et exploratoire.

## Architecture
Les données restent produites par PIP dans son stockage pseudonymisé. Le calcul et la restitution collective restent dans l'écran Études de Gestion des Actions I9, conformément à l'architecture existante. Le package contient donc un dossier `integration_gestion_actions_h33c` avec les fichiers concernés.

## Non-modifié
- banque 72 items ;
- scoring PIP ;
- ROME ;
- O*NET ;
- rapports individuels PIP/O*NET ;
- CRM et séparation CRM/étude ;
- mode ACCOMPAGNEMENT ;
- jalon H3.3-B résultats → ressenti → fin → e-mail.

## Niveau d'anglais
Aucun indicateur de maîtrise de l'anglais n'est calculé : cette donnée n'est pas recueillie dans les fichiers H3.3 actuels.

## Déploiement
Aucun déploiement VPS effectué à ce jalon.

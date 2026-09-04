# Clarté360 Émargements — V2.1.4

## Correctifs prioritaires

- Correction des séances qui franchissent minuit : la fin est désormais portée au jour suivant avant calcul des échéances.
- Garde-fou dans le worker : avant tout envoi, l'échéance réelle est recalculée depuis le créneau et le fuseau de l'organisme. Une échéance incohérente est réparée et ne peut plus provoquer un envoi anticipé.
- Affichage des échéances d'émargement en heure locale de l'organisme au lieu de l'UTC brut.
- Libellé clarifié : « Émargement possible après la fin pendant (min) ».

## Espace formateur / accompagnant

- Invitation par email lors de l'ajout au référentiel lorsqu'une adresse email est renseignée.
- Invitation renouvelable depuis les paramètres.
- Création d'un mot de passe personnel via un lien sécurisé et limité dans le temps.
- Connexion à un espace intervenant dédié.
- L'intervenant ne voit que les actions qui lui sont affectées.
- Chaque action ouvre l'espace opérationnel restreint existant : planning, QR, suivi, absences, relances et contresignature.
- Les fonctions et données administratives globales restent hors de cet espace.

## Bases d'import Clarté360 / ADCA

- Lorsqu'un classeur est chargé dans l'application, une copie instantanée est conservée sur le VPS.
- Cette copie peut être réutilisée pour rechercher plusieurs actions successivement sans recharger le classeur.
- Un chemin serveur / volume monté peut également être mémorisé dans Paramètres > Général ; l'application crée alors une copie instantanée avant lecture.
- Un chemin Windows local `C:\...` n'est pas directement accessible au VPS : dans ce cas le chargement navigateur crée la copie de travail persistante.
- Aucune base de production ni secret n'est inclus dans le livrable.

## Qualité

Le fonctionnement V2.1.3 est conservé : les campagnes PENDING suivent la dernière séance réelle et sont recalculées lorsqu'un calendrier actif est modifié. Les campagnes déjà envoyées ou complétées ne sont pas déplacées silencieusement.

# CLARTE360 - Intervenants - J6 Matrice collective / recherche de competences
Date : 2026-09-20

## Objet
Construire la vue collective derivee des adequations individuelles J4/J5 et permettre a l'administrateur de rechercher les intervenants qualifies pour une prestation Clarte360.

## Regles metier
- La matrice collective est derivee des dossiers individuels : aucune seconde source de qualification n'est creee.
- Seule la qualification humaine validee est utilisee pour declarer une adequation ou filtrer les intervenants qualifies.
- Une proposition IA reste visible comme information technique dans les donnees mais ne rend jamais une personne qualifiee.
- Par defaut, seuls les INTERVENANTS actifs sont inclus ; les candidats ne sont pas proposes pour une affectation operationnelle.
- Recherche par prestation, niveau humain minimal, type de collaboration, ville et adequation aux criteres obligatoires.
- Les resultats sont alphabetiques : aucun classement automatique des personnes et aucune decision a la place de l'administrateur.

## UX
Ajout d'un onglet `Matrice & recherche` dans `Parametres > Intervenants & partenaires`, entre Intervenants et Prestations.
La matrice affiche notamment prestation, niveau humain, criteres requis satisfaits, preuves et date de revision.

## Compatibilite
Migration additive : aucune modification destructive de J0-J5. Aucun raccordement au module Actions/Formation a ce jalon.

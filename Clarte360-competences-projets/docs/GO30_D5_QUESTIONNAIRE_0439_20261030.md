# GO30 — génération directe du questionnaire 0.4.39

## Décision de parcours

La génération correspond au processus d'analyse de l'intervenant. Elle ne demande pas un consentement supplémentaire à l'écran et ne pose pas une question pour chaque document.

1. L'intervenant rapproche et valide les pièces dans Documents, une seule fois.
2. Dans « Préparer le questionnaire », il peut ajouter une observation privée facultative et clique sur « Générer le questionnaire ».
3. C&P lit en une passe les pièces déjà retenues (CV, APS et rapports disponibles), prépare les deux parties dans un brouillon et ouvre directement la relecture.
4. L'intervenant modifie le brouillon avant publication. Aucun envoi au bénéficiaire n'est automatique.

L'APS peut fournir des pistes explicites, mais elle n'est plus un écran, un consentement ou un prérequis technique à la génération. Sans APS exploitable, le questionnaire-cadre et les repères disponibles sont tout de même créés; aucune piste n'est inventée. Une analyse interrompue ne crée pas de brouillon vide. Une nouvelle tentative réutilise les pièces déjà enregistrées.

## Changements d'interface

- Suppression du bloc « le brouillon actuel ne contient aucune piste APS » et de sa case de consentement.
- Suppression du consentement requis dans le parcours de génération initiale.
- Un seul bouton « Générer le questionnaire »; le champ « Souhaitez-vous ajouter quelque chose ? » reste facultatif.
- Après réussite, la navigation revient à la première étape de relecture. Le succès indique que le brouillon est enregistré.
- La version vide précédemment créée peut être reprise; la génération produit une nouvelle version du questionnaire sans resélectionner les documents.

## Vérifications locales

- `compileall` réussi.
- Scénario fonctionnel simulé sans APS : analyse terminée, aucune idée inventée, génération non bloquée.
- Contrats d'interface : bouton unique, aucune case de consentement dans le flux de génération.
- Archive contrôlée avec `python -m zipfile -t`; script contrôlé avec `bash -n`.

Le PDF image sans texte sélectionnable reste une limite d'extraction. Dans ce cas, la génération affiche l'erreur et conserve les choix existants.

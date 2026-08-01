# Clarté360 – Recherche de mes valeurs
## V2.1.3.8F – stabilisation finale du module 3

### Panier de gestion des valeurs
- Gestion cohérente des trois états actifs : valeurs validées, valeurs à examiner et sujets à revoir en séance.
- Réouverture complète d’une valeur à examiner ou d’un sujet à revoir en séance.
- Modification possible du nom et de la définition avant reprise du questionnaire.
- Une valeur ouverte depuis son propre panier n’est plus bloquée comme doublon.
- Sorties permanentes sur tous les écrans du module 3 : retour, abandon du réexamen et suppression définitive.
- Lors d’un retour ou d’un abandon, la valeur est restaurée dans sa catégorie d’origine sans perte.

### Suppression définitive
- Confirmation en deux étapes.
- Suppression de toutes les données métier liées : listes actives, définitions, réponses, questionnaires, clarifications, statuts, historiques métier, états de reprise et références utilisées par les rapports.
- Aucun contenu métier de la valeur supprimée n’est conservé dans le JSON de travail.

### Oral
- Un seul clic sur « Transcrire et comparer » suffit désormais : la transcription et la proposition sont mémorisées puis affichées immédiatement au rerun, sans second appel.
- La protection contre le double appel reste active grâce à l’empreinte de l’enregistrement et à la transcription déjà mémorisée.

### Module 4
- Aucun panier spécifique d’hypothèses n’est ajouté dans cette version.
- Le futur module 4 découvrira une hypothèse ; lorsqu’elle sera sélectionnée, elle sera transmise au parcours normal du module 3 à partir de la demande de définition.

### Contrôles
- Compilation Python réussie.
- 52 tests automatisés réussis.

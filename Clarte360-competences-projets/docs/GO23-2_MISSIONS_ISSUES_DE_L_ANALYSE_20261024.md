# GO23-2 — préparer une mission à partir de l’analyse ROME

Candidate : `0.4.5-go23-1-work`, schéma 9  
Statut officiel : GO22, GO23 et GO24 restent ouverts. GO21 RC2 reste le dernier jalon validé.

## Fonction réalisée

- L’écran phase 5 reprend les points « à confirmer » ou « non documenté » de la dernière revue ROME qui correspond encore à la version actuelle du parcours et de la fiche métier.
- L’accompagnateur choisit le point qui justifie une investigation externe et peut préparer une mission associée au métier ROME et au savoir concerné.
- Le brouillon de mission reprend la question de clarification IA lorsqu’elle existe, ou une consigne générale de vérification. L’accompagnateur peut modifier le texte avant transmission.
- La préparation n’envoie rien au bénéficiaire. La transmission reste une action explicite de l’accompagnateur.
- Le bénéficiaire garde son espace de recherche et de réponse : ressource consultée, date, constat, effet sur son projet. Les liens externes sont disponibles même si l’API n’est pas disponible.
- Aucun attendu ROME, fait de parcours ou résultat d’enquête n’est transformé automatiquement en conclusion. Le retour doit être débriefé avant la clôture de la mission.

## Contrôles

- AppTest crée une revue ROME avec un attendu non documenté, choisit ce point, prépare un brouillon, et vérifie que le métier est pré-sélectionné et le texte modifiable.
- Le scénario complet d’investigation vérifie l’association métier, le retour bénéficiaire et l’accès au débrief.
- Suite complète : 259 tests réussis; compilation Python réussie.

## Limites

- Les missions ne sont pas transmises automatiquement et ne sont pas générées pour chaque point à vérifier. L’accompagnateur choisit lesquelles sont pertinentes.
- Les vrais appels API France Travail et IA, le connecteur GDA/Hub et la recette navigateur/VPS restent à effectuer dans les jalons dédiés.
- Ce jalon ne vaut pas recette métier ni validation de GO23.

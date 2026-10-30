# GO30 — diagnostic et affichage de génération 0.4.41

## Retour terrain

La 0.4.40 atteint l'appel IA mais l'interface affiche seulement un message générique en cas d'échec. Pendant l'exécution, Streamlit redessine aussi le formulaire au-dessus de son ancien rendu, ce qui donne l'impression de deux panneaux de génération.

## Correctif

- Le panneau du formulaire est remplacé par l'état de traitement au clic, sans seconde copie du bouton.
- Les erreurs de l'appel IA sont inscrites au journal sans texte de document, référence source ni corps de réponse.
- L'écran indique la classe d'erreur et, si disponible, le statut/code HTTP du fournisseur; le journal serveur conserve le détail technique.
- Les erreurs imprévues de construction du brouillon sont également journalisées et ne masquent plus leur type.
- Aucun document n'est revalidé; les choix restent enregistrés.

## Contrôles

- `compileall` réussi.
- Scénarios manuels simulés : erreur IA explicite, taille de 7 sources et remplacement du formulaire par le traitement.
- ZIP et syntaxe shell contrôlés.

# GO23 RC1 — état de construction et contrôles

**Candidate de travail :** `0.4.1-go23-work-rc1`  
**État :** non validée par Dominique, non installée, non déployée. GO22 reste non validé.  
**Dernier jalon officiellement validé connu :** GO21 RC2.

## Périmètre construit dans cette candidate

- Phase 5 : l'accompagnateur peut rédiger et publier une vérification hors séance ; les retours et leur débrief sont consultables depuis le parcours d'investigation existant.
- Phase 6 : la comparaison accepte jusqu'à trois métiers actifs et six critères définis. Les versions sont historisées. Les brouillons restent internes ; l'accompagnateur partage une version explicitement au bénéficiaire.
- Une comparaison postérieure en brouillon ne masque pas la dernière version publiée au bénéficiaire.
- Aucun score, total, feu global ou classement n'est créé.
- La rubrique diplôme/titre obligatoire demande une source officielle et sa date. Une attente d'employeur ou une offre ne suffit pas à établir une obligation d'exercice ; les éléments incertains restent à vérifier.
- Phase 7 : l'accompagnateur consigne le projet prioritaire et, si utile, une alternative distincte à partir de la décision exprimée par le bénéficiaire en séance. Les motifs sont requis et les deux métiers ne peuvent pas être identiques. Ces éléments sont présentés dans le parcours bénéficiaire.
- Les écritures métier produisent des événements d'audit minimisés.

## Vérifications exécutées

- `python -m compileall -q clarte360_cp` : réussi.
- `python -m pytest -q --disable-warnings` : **240 tests réussis**.
- Scénarios GO23 ajoutés : brouillon non visible, publication visible, décision prioritaire et alternative, refus d'une écriture bénéficiaire, justification trop courte, doublon de cellule, et parcours AppTest de publication puis décision.
- La suite conserve les tests existants sur enquête/débrief et rapprochement ROME.

## Reste à construire ou à prouver

- GO22 n'est pas achevé ni validé ; GO23 est une première tranche de code et pas un GO terminé.
- La recette visuelle dans un navigateur réel n'a pas été exécutée dans cette session.
- Les écrans partagés utilisent encore l'application locale C&P ; aucun raccordement Hub/GDA réel n'est démontré dans cette candidate.
- Les liens de ressources sont présents pour les investigations, mais les API France Travail et IA n'ont pas été appelées ici.
- Les états/validations officiels de phase et la publication documentaire finale restent à raccorder dans leurs jalons.
- Les contrôles Accompagnateur et Bénéficiaire par un professionnel et un bénéficiaire d'essai restent à faire au jalon final de recette.
- La source de travail de cette session est une extraction locale sans répertoire `.git`. Aucun commit, push, VPS, ZIP de recette, ou changement de statut de validation n'a été effectué.

## Contraintes métier conservées

Le bénéficiaire reste décisionnaire. L'accompagnateur prépare, vérifie les sources et formalise ce qui a été décidé ensemble. Une compétence peut venir d'une expérience, d'études sans diplôme, d'une formation ou d'un apprentissage personnel. Le diplôme n'est considéré obligatoire que si une source officielle l'établit pour l'exercice considéré.

Les documents restent dans l'espace partagé de l'application de base : chaque dépôt éventuel doit être rattaché manuellement par l'accompagnateur au besoin de C&P, sans copie binaire, reconnaissance de contenu ou classement automatique. Ce connecteur n'est pas actif dans la présente candidate.

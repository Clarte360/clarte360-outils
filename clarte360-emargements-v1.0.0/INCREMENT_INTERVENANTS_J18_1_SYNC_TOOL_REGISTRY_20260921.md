# CLARTE360 - Gestion des Actions - Intervenants J18.1

## Objet
Synchronisation de la recette finale J18 avec le `config/tool_registry.json` actuellement utilisé dans GitHub afin d'eviter toute regression lors du futur deploiement.

## Correction appliquee
La J18 contenait bien `config/tool_registry.json`, mais avec la version du 18/09/2026. La version courante du 21/09/2026 a ete integree sans modification de son contenu.

Evolution principale constatee : `MOTEURS_PROFESSIONNELS` est desormais actif, prescriptible et configure en production avec le connecteur HUB generique et son profil de lancement.

## Securite de deploiement
Le fichier est maintenant present dans le package final au chemin exact :
`config/tool_registry.json`.

Le futur remplacement du code depuis GitHub ne doit donc pas ramener l'ancien registre contenu dans J18.

## Tests
Les tests historiques qui attendaient encore MOTEURS_PROFESSIONNELS comme outil planifie/inactif ont ete mis a jour pour verifier le nouvel etat officiel du registre.

Suite complete : 440/440 tests reussis.

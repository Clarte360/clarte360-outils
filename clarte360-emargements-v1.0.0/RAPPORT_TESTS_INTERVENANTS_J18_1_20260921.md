# RAPPORT DE TESTS - J18.1 - 21/09/2026

Objet : synchronisation de `config/tool_registry.json` avec la version courante GitHub.

## Controle cible
- Registre JSON valide et charge par le socle.
- MOTEURS_PROFESSIONNELS actif et prescriptible.
- URL Moteurs professionnels conforme.
- `connector_status = LAUNCH_ONLY`.
- Profil HUB actuel conserve.

Tests cibles registre/HUB/outils : 28/28 reussis.

## Non-regression complete
Execution par lots pour eviter la limite de duree :
- lot 1 : 147/147
- lot 2 : 81/81
- lot 3 : 94/94
- lot 4 : 118/118

TOTAL : 440/440 tests reussis - 0 echec.

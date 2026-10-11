# P5-RC2 / J11 — Programmation libre des rappels Teams

**GO :** demande utilisateur du 11/10/2026 : deux délais modifiables dans Administration > Paramètres > Général, essais à 5 et 2 minutes, remise manuelle à 120 et 15 minutes. J11 est le livrable réel pour la recette sur VPS après autorisation de déploiement.

## Réalisation
- Deux colonnes additives par organisation, `online_reminder_first_minutes` (120) et `online_reminder_second_minutes` (15), modifiables uniquement par l'administrateur dans le formulaire des paramètres régionaux. Valeurs 1..10080 minutes, premier strictement avant le second.
- Réglages persistants et sans retour automatique ; l'ancien appel du service ne les efface pas.
- Programmation automatique autonome du worker, fenêtre de préparation tenant compte du délai le plus long et libellés des emails correspondant au réglage réel.
- Changement de paramètres : files anciennes neutralisées, nouvelles échéances préparées sans SMTP direct ; contrôles au moment de l'envoi, y compris report, annulation, révocation et périmé.
- Une communication déjà envoyée ne repart pas uniquement après changement de durée ; un créneau réellement déplacé peut être notifié de nouveau.
- Historique Teams H2/H15 conservé sous ces identifiants techniques stables pour compatibilité ancienne base.

## Livrable et limites
- ZIP complet J11 `clarte360-gestion-actions-v3.0.0-P5-RECETTE-RC2.zip`, dossier code stable `clarte360-emargements-v1.0.0`.
- Tests et intégrité dans dossier de recette J11, manifeste SHA-256 et guide Framework VPS V1.4.
- **Aucun GitHub ni VPS modifié par l'assistant.** Seul le propriétaire assure l'import/push GitHub et le futur GO VPS.
- SMTP, Teams/Graph, interfaces 13/17, écrans navigateur, fichiers persistants et restauration PRA complète à recetter ultérieurement sur environnement autorisé.
- **Registre COR/AME édition 0.9 inchangé.**

# Changelog

## 1.0.0
- Socle graphique Clarté360 vert canard #008080.
- Logo officiel et mentions légales Clarté360.
- Administrateur et mise en service sécurisée.
- Actions INTRA / INTER / INDIVIDUEL.
- Nombre prévu de stagiaires.
- Import réel GESTION OF CLARTE360 et CSV.
- Participants, créneaux illimités, duplication et modification journalisée.
- Calcul prévu/planifié.
- Liens individuels et QR de créneau.
- Signature graphique tactile/souris.
- Fenêtre temporelle d'émargement.
- Envois et relances automatiques via worker.
- Relance manuelle.
- Tableau de suivi et heures justifiées.
- PDF collectif, individuel, certificat.
- JSON + ZIP portable et piste d'audit.

## 1.1.0 — développement 2026-09-02
- migration additive des données (preuves existantes conservées)
- blocage de la réécriture d'un créneau contenant une preuve
- statuts de présence/absence
- rattrapages reliés au créneau d'origine, y compris collectifs
- régularisation de signature a posteriori explicitement tracée
- espace intervenant restreint : QR, suivi, absence, relance, contresignature
- contresignature unique par créneau
- dates de naissance JJ/MM/AAAA et détection initiale des doublons
- affichage des horodatages en Europe/Paris
- certificat définitif bloqué tant que le dossier n'est pas complet
- signature alternative « nom et prénom + certification »
- report d'un créneau futur avec conservation de l'ancien créneau au statut REPORTE
- réinitialisation administrateur du code personnel QR
- certificat calculé sur les dates effectivement émargées
- sauvegarde SQLite + signatures/documents avec rotation de 30 archives et timer systemd fourni
- tests V1.1 portés à 7 scénarios automatisés

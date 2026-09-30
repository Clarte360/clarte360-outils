# RC2 PROVISOIRE — Tableaux vivants — 22/09/2026

Base : J18.1 déployée.

Correctifs intégrés pendant la recette utilisateur :
- version affichée alignée sur `3.0.0-INTERVENANTS-RC2-PROVISOIRE` ;
- listes Intervenants et Candidats rendues actionnables : ouvrir/modifier, inactiver/réactiver, suppression physique seulement sans dépendance ;
- suppression protégée par confirmation et contrôle serveur des dépendances ; un dossier utilisé reste historisé et ne peut être qu'inactivé ;
- accès direct depuis Candidats au dossier sélectionné ; suppression du principe « aller chercher le dossier ailleurs » ;
- tableaux Expériences, Spécialités, Diplômes/Formations, Langues, Certifications/Habilitations rendus modifiables et supprimables depuis le tableau ;
- Documents : accès direct au fichier, modification des métadonnées, archivage conservé ;
- audit des mutations ajouté côté services.

Références : CDC directeur V1.5 §13 et CDC correctif V1.1 §§2, 13, 20.

Statut : PROVISOIRE. Ne pas déployer tant que la recette utilisateur J18.1 continue et que les autres retours ne sont pas consolidés.

## Synchronisation IA globale -> Qualification / Adéquation
Constat recette `ANALYSE 18.1 RC1.docx` : l'analyse globale lancée depuis Documents produisait des prestations potentielles mais n'alimentait pas directement l'écran Qualification/Adéquation, ce qui conduisait à un second appel IA prestation par prestation.

Correction RC2_PROVISOIRE :
- une seule analyse IA globale est désormais la source des propositions de qualification ;
- le payload global transporte le catalogue des prestations ET leurs critères actifs ;
- pour chaque prestation potentiellement recevable, la même réponse IA fournit niveau proposé, confiance, critères, preuves et points manquants ;
- ces éléments sont immédiatement matérialisés dans `person_service_qualifications`, `ai_criterion_proposals` et `ai_qualification_evidence_proposals` ;
- l'onglet Qualifications/Adéquation exploite donc la même analyse, sans second appel IA obligatoire ;
- si de nouvelles pièces sont ajoutées, on relance l'analyse globale depuis Documents ;
- l'analyse ciblée prestation par prestation est retirée du parcours normal.

## Images JPG/PNG/WEBP
Les documents image (notamment diplôme photographié/scanné) sont désormais sélectionnables dans l'analyse globale et transmis au modèle comme entrée image multimodale dans le même appel IA.

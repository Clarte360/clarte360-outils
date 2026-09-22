# J14 - Dossier candidat/intervenant, documents et IA globale

Base: J13 OneDrive. CDC: directeur V1.5 + correctif V1.1.

## Réalisé
- Après création candidat/intervenant, parcours explicitement orienté vers Documents.
- Documents professionnels persistants conservés dans le dossier (stockage serveur existant, métadonnées en base).
- Analyse IA globale du dossier ajoutée, distincte de l'analyse prestation par prestation historique.
- Analyse globale fondée sur les documents sélectionnés et le catalogue actif, sans coordonnées personnelles envoyées au modèle.
- Détection et restitution des incohérences d'identité / points à vérifier.
- Préremplissage sous forme de PROPOSITIONS: profil, spécialités, expériences, formations/diplômes, certifications/habilitations, langues et prestations candidates.
- Aucune proposition IA ne modifie silencieusement le dossier: acceptation/rejet humain requis.
- Historisation des analyses globales et des décisions sur propositions.
- Une anomalie d'identité reste une alerte à traiter et n'est pas transformée en preuve validée.

## Limites volontaires du J14
- Les critères détaillés par prestation et la matérialisation complète des preuves IA sont traités aux J15/J16 conformément au plan validé.
- Les JPG/PNG sont acceptés et persistés, mais l'analyse multimodale image complète reste à consolider dans la chaîne IA; aucun OCR silencieux n'est utilisé.
- DOCX reste compatible avec l'existant; le socle minimal demandé PDF/JPG/PNG est conservé.

## Non-régression
426 tests automatisés passés en deux lots: 271 + 155, 0 échec.
Compilation app.py/services.py/db.py/qualification_ai.py OK.

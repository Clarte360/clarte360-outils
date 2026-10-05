# INCREMENT — INTERVENANTS RC2-2-2 P2 — IA — 02/10/2026

## Base de départ
- Checkpoint validé : `3.0.0-INTERVENANTS-RC2-2-2-P1`.
- Périmètre : P2 du CDC `CDC_CLARTE360_GESTION_INTERVENANTS_RC2_2_2_V1_0_20261002.docx`.
- Aucun déploiement GitHub/VPS réalisé pendant ce jalon.

## Réalisations P2
1. **Correction du faux 0/4 IA**
   - `service_level=0` est conservé uniquement lorsqu'aucun critère ni aucune preuve ne porte d'élément positif.
   - Si l'IA renvoie 0 alors que des éléments positifs existent, la normalisation relève prudemment l'indicateur global à 1/4.
   - Cette correction ne crée aucune décision humaine : `human_value` reste la seule valeur effective pour l'affectation.

2. **Séparation niveau / complétude des critères obligatoires**
   - Calcul explicite de `required_criteria_total`, `required_criteria_positive` et `required_criteria_below_min`.
   - Les critères obligatoires insuffisamment étayés ne mettent plus artificiellement à zéro toute la lecture IA.

3. **PDF texte / scanné / hybride**
   - Inspection page par page sans OCR.
   - PDF texte : extraction texte.
   - PDF scanné : envoi multimodal du PDF.
   - PDF hybride : conservation du texte extrait + envoi du PDF multimodal afin que les pages visuelles ne soient pas perdues.
   - En cas d'échec de lecture : comportement prudent et contrôle humain requis.

4. **Observabilité IA**
   - Mesure de la durée totale.
   - Comptage des appels API réels.
   - Comptage des retries.
   - Tokens entrée / sortie / total.
   - Coût estimatif uniquement si les tarifs par million de tokens sont explicitement configurés.
   - Persistance additive dans `professional_global_ai_runs`.

5. **Retry observable**
   - Le client SDK OpenAI est configuré avec `max_retries=0` pour éviter les retries cachés.
   - Le gateway global gère explicitement un retry applicatif maximum et l'inclut dans les compteurs.

6. **Points IA structurés**
   - Les nouveaux `missing_points` d'une analyse globale sont immédiatement matérialisés dans `qualification_review_points` avec source `IA`.
   - Ils sont donc actionnables via le mécanisme P1 `OUVERT / LEVE / CONFIRME / NON_PERTINENT`.

7. **Lecture UI de l'analyse globale**
   - Le tableau principal privilégie désormais critères avec éléments, critères obligatoires à vérifier, preuves et points ouverts.
   - Le niveau IA global et la confiance restent visibles comme informations secondaires.
   - Les métriques techniques de la dernière analyse sont affichées lorsque disponibles.

## Fichiers modifiés
- `qualification_ai.py`
- `db.py`
- `services.py`
- `app.py`
- `branding.py`
- `CHANGELOG.md`
- `tests/test_intervenants_rc2_2_2_p2_ai.py` (nouveau)

## Non réalisé dans P2
- Pas encore de refonte complète du cockpit / navigation dossier : P3.
- Pas encore de refonte générale des tableaux : P4.
- Pas encore de nouveau deep-link Action -> Qualification -> Retour Action : P5.
- Pas de PUSH GitHub ni de PULL VPS.

## Conclusion
P2 fournit le moteur IA et la couche de persistance nécessaires au futur parcours DRH sans transformer les propositions IA en décisions humaines. La base est prête pour P3 — Dossier UX.

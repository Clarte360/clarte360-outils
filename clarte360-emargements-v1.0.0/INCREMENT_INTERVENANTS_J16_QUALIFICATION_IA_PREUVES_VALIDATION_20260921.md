# J16 — Qualification IA, preuves proposées et décision humaine

Base : J15.

## Livré
- Les sorties IA par prestation sont matérialisées en propositions distinctes : elles ne deviennent jamais silencieusement des preuves ou validations humaines.
- Proposition IA par critère : niveau 0–4, confiance, justification, rattachement aux preuves.
- Proposition de preuve : source, fait, document du dossier lorsqu'identifiable, critère(s), niveau soutenu et état de cohérence d'identité.
- États de décision : PROPOSEE / ACCEPTEE / REJETEE.
- Une preuve IA acceptée devient alors seulement une preuve vérifiée ; une preuve rejetée reste historisée sans compter dans l'adéquation.
- Une pièce marquée INCOHERENT sur l'identité ne peut pas être acceptée comme preuve.
- L'acceptation d'une proposition de critère constitue une décision humaine explicite et verrouillée ; l'IA ne modifie jamais un champ human_*.
- L'écran d'instruction affiche les propositions IA avant la grille humaine et permet accepter/rejeter sans quitter la prestation.
- Double validation identique rendue idempotente : pas de nouvel événement historique si niveau/commentaire/verrou/date de révision n'ont pas changé.

## Limite volontaire
Le parcours global multi-prestations (tableau « à étudier / validé / non validé » et orchestration dossier global → instruction) appartient à J16/J17 selon l'enchaînement métier ; J16 livre le moteur de décision fiable au niveau personne × prestation × critère × preuve.

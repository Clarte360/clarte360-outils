# Contrat de lecture des résultats GO22 RC3B (proposition non normative)

## Règles de sécurité métier

Une source `authorized=true` + `source_ref` explicite peut, si les résultats
ont déjà été lus/vérifiés par l'application d'origine/Hub, fournir
`result_summary`. Il s'agit d'un extrait descriptif, pas d'une re-passation.
GO22 ne calcule ni ne transforme les mesures source, et conserve la précision
exacte `score_display` (`9/10`, `54,6 %`, `77/100`, etc.). Le texte `scale`
rappelle la nature de chaque mesure ; aucune note n'est convertie pour
comparer plusieurs outils.

La structure autorisée :

```
result_summary: {
  scale: string, note: string, profile_code: string,
  rows: [{key: string, label: string, explanation: string, score_display: string}]
}
```

La validation ajoute `status=REEL|FICTIF` à partir de la source autorisée.
La source est référencée dans Q avec version et statut ; les références
internes sont masquées au bénéficiaire, tandis que les explications utiles
lui sont présentées. La source d'origine n'est jamais réécrite ni imputée à
l'utilisateur.

Pour `PIP_REPORT`, `profile_code` n'est présent que si le rapport d'origine
le fournit. Trois ou cinq lettres sont acceptées techniquement ; ce n'est
pas une instruction de fabriquer deux lettres. Dans la recette le code
fictif est `RSC` (trois lettres), conformément au modèle utilisé.

## Ce qui n'est pas livré ici

- Pas de connecteur opérationnel APS/GDA/5 outils : pas de véritable import
  de chiffres dans un dossier réel ; aucune duplication des documents.
- Pas d'IA réelle C-AV3 ni de rapprochement ROME ; aucun score ne décide.
- Pas d'ouverture PDF Hub depuis C-AV2 (la navigation documentaire reste
  selon les droits existants).
- Pas de diffusion de rapports ou de réponses à un employeur financeur.

Avant une mise en exploitation, la structure sera raccordée aux APIs
versionnées des outils, avec vérification d'origine, consentement, droits,
minimisation, tests d'échelles et provenance. Les caractères personnels ne
doivent pas être exportés dans les archives de développement.

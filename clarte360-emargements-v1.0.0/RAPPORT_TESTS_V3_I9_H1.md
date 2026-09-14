# Rapport de tests — I9-H1 Validation des saisies

Date : 2026-09-12

## Résultat
- **263 tests réussis / 263**
- compilation Python : **OK**
- imports principaux : **OK**
- `release_check.py` : **CANDIDATE TECHNIQUE OK**

## Nouveaux contrôles testés
77 tests supplémentaires par rapport à I9-H (185 -> 262), plus un scénario de résistance groupé aux chaînes malveillantes (263 total).

Les cas couvrent notamment :
- chiffres/symboles/HTML/emoji dans noms et prénoms ;
- e-mails sans domaine, doubles @, espaces, CR/LF, domaines invalides ;
- téléphones trop courts/longs, lettres et symboles interdits ;
- dates impossibles, futures, valeurs numériques brutes ;
- dates de fin antérieures au début ;
- heures impossibles ou créneau de durée nulle ;
- numéros d'action avec espaces, #, `..`, `;` ;
- SIRET/NDA/NAF/TVA incorrects ;
- URL non HTTP(S), fuseau IANA invalide ;
- JSON invalide ou tableau à la place d'un objet ;
- validation au niveau des services Action, Participant, Intervenant, CRM, Organisme, Agence, Contacts client, Microsoft/Teams et profils d'import.

## Conclusion
Aucune régression détectée. Les champs structurés sont désormais protégés à la frontière métier, même en dehors de l'interface Streamlit.

# Rapport d'audit fonctionnel - Clarté360 Recherche de mes valeurs V2.1.3.5

## Périmètre contrôlé
- démarrage et compilation ;
- secrets Streamlit et code d'activation ;
- consentement RGPD ;
- état de session et reprise JSON ;
- navigation et dépendances ;
- questions ouvertes ;
- clavier, voix, transcription et validation ;
- reformulation ;
- exploration RVC360 ;
- exports JSON/PDF ;
- clôture et sécurité.

## Appels OpenAI

| Fonction | Déclencheur | Appels attendus | Protection |
|---|---|---:|---|
| `transcribe_audio` | clic `Transcrire et comparer les versions` | 1 | empreinte audio + cache session + bouton protégé |
| `clean_spoken_text` | après transcription | 1 maximum | identifiant déterministe du texte + cache session |
| `reformulate_text` | clic `Générer une proposition` | 1 | identifiant déterministe + cache session |
| `project_hypotheses` via `response_json` | validation d'une réponse d'exploration | 1 | identifiant de soumission + identifiant IA + cache session |

Les reprises automatiques imbriquées ont été supprimées. Le SDK OpenAI est configuré avec `max_retries=0` afin qu'une action utilisateur ne soit pas multipliée silencieusement.

## Traçabilité
Chaque traitement conserve dans `ai_request_log` :
- type d'appel ;
- date et heure ;
- identifiant ;
- statut ;
- nombre de tentatives ;
- modèle ;
- erreur éventuelle ;
- tokens lorsqu'ils sont fournis par l'API.

Aucune clé API, code d'activation ou donnée audio binaire n'est stocké dans les exports.

## Questions ouvertes contrôlées
- présentation du bénéficiaire ;
- valeurs déjà identifiées ;
- valeurs découvertes entre les séances ;
- exploration guidée ;
- clarification des hypothèses ;
- commentaires de validation ;
- contrôle de complétude.

Les champs purement administratifs restent volontairement hors du composant réflexif complet.

## Anomalie principale corrigée
La transcription changeait la clé du composant audio puis exécutait immédiatement `st.rerun()`. Le résultat pouvait ne devenir visible qu'après une nouvelle interaction et le même audio pouvait être retraité. La version 2.1.3.5 conserve la clé pendant le traitement, mémorise immédiatement les résultats et bloque un second traitement du même audio.

## Tests exécutés
- `python -m py_compile app.py` : réussi ;
- `pytest -q` : 13 réussis ;
- recherche des appels OpenAI : contrôlée ;
- recherche des retries imbriqués : aucun bloc restant ;
- contrôle des secrets dans les sources et exports : réussi ;
- contrôle d'absence d'audio binaire dans le JSON : réussi par architecture et tests statiques.

## Limites de vérification
Les appels réels OpenAI, le microphone navigateur, Streamlit Cloud, SMTP et le parcours complet avec un compte de production ne peuvent pas être exécutés hors de l'environnement réel du bénéficiaire. La version est donc une version de préproduction destinée au test réel avant officialisation en V2.1.4.

## Confirmation
- le programme part exclusivement de la V2.1.3 fournie ;
- le ZIP livré est compilé ;
- les tests automatisés sont réussis ;
- aucun secret réel n'est inclus ;
- aucun audio binaire n'est inclus dans les exports.

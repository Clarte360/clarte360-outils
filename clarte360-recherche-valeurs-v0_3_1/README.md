# Clarté360 – Recherche de mes valeurs

Version applicative : **1.4.0 préproduction**  
Socle Clarté360 : **1.8**  
Framework : **4.0**  
Référentiel métier : **RVC360 V1.3**

Application Streamlit mettant en œuvre l’exercice inter-séance RVC360 : exploration, clarification et validation des valeurs fondamentales, sans interprétation et sans remplacement de l’accompagnateur.

## Architecture métier V1.3

Le moteur fonctionne désormais en deux niveaux indépendants :

1. **IA-550 – Analyse structurée** : organisation des faits, mots, émotions déclarées, attentes exprimées, actions, expressions fortes, critères personnels, contradictions explicites et thèmes descriptifs. Ce niveau ne recherche et ne nomme aucune valeur.
2. **IA-600 / IA-650 – Projection RVC360** : rapprochement de la fiche structurée avec un sous-ensemble pertinent du référentiel officiel, classement interne des hypothèses, puis présentation au bénéficiaire.

Aucune règle spécifique du type « expression X = valeur Y » n’est utilisée. Le préfiltrage est générique et s’appuie sur le contenu du référentiel complet.

## Parcours des hypothèses

- toutes les hypothèses détectées sont inscrites dans le dialogue ;
- elles sont ensuite examinées une par une ;
- une hypothèse peut être validée, abandonnée ou rouverte ;
- si toutes les hypothèses sont refusées, l’exploration reprend avec un autre angle ;
- aucune valeur n’est validée sans le questionnaire spécifique HEC : importante, très importante, fondamentale.

## Données et documents

- le JSON de reprise conserve l’état nécessaire pour continuer le travail, notamment la fiche d’analyse et l’historique technique du parcours ;
- le JSON final et le rapport PDF ne restituent que les valeurs fondamentales validées et les informations utiles qui en découlent ;
- aucun fichier audio n’est conservé.

## Secrets Streamlit

Le bloc `[email]` reste identique aux autres applications Clarté360. Le bloc `[openai]` doit contenir :

```toml
[openai]
api_key = "..."
model = "gpt-5.6-terra"
transcription_model = "gpt-4o-mini-transcribe"
```

Ne jamais publier `.streamlit/secrets.toml`.

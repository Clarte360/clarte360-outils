# Clarté360 – Recherche de mes valeurs

Version applicative : **1.3.0 préproduction**  
Socle Clarté360 : **1.8**  
Référentiel métier : **RVC360 V1.2**

Application Streamlit mettant en œuvre l'exercice inter-séance RVC360 : exploration, clarification et validation des valeurs fondamentales, sans interprétation et sans remplacement de l'accompagnateur.

## Correctifs principaux de cette version

- lecture vocale ponctuelle : un clic déclenche une seule lecture, sans boucle ;
- arrêt de toute lecture précédente avant une nouvelle écoute ;
- cycle vocal fiabilisé : enregistrement, arrêt avec le carré, transcription, relecture, validation ou réenregistrement ;
- nouvel enregistrement réellement recréé après échec ou demande de reprise ;
- aucun audio conservé dans le JSON ou dans l'application ;
- message clair lorsque l'audio est vide ou que la transcription échoue ;
- enregistreur présenté dans une zone plus courte ;
- relances IA moins orientées et diversification des situations ;
- approfondissement prioritaire de la situation racontée avant changement d'exemple ;
- hypothèses examinées une par une jusqu'à validation ou abandon ;
- référentiel des valeurs synchronisé avec le ZIP officiel RVC360 V1.2.

## Secrets Streamlit

Le bloc `[email]` reste identique aux autres applications Clarté360. Le bloc `[openai]` doit contenir :

```toml
[openai]
api_key = "..."
model = "gpt-5.6-terra"
transcription_model = "gpt-4o-mini-transcribe"
```

Ne jamais publier `.streamlit/secrets.toml`.

# Recette VPS obligatoire avant RCF

La RC1 automatisée ne remplace pas la vérification d'installation réelle. Avant RCF, exécuter et consigner :

- registre VPS : tool_id `ipip-neo120`, port 8515, URL `https://ipip-neo120.clarte360.com` ;
- `ss -lntp` : absence de conflit port 8515 avant installation, puis écoute attendue après démarrage ;
- service `clarte360-ipip-neo120.service` actif et redémarrage propre ;
- Nginx : vhost vers 127.0.0.1:8515, certificat HTTPS valide ;
- lien secrets vers `/opt/clarte360/secrets/secrets.toml` et section contractuelle `IPIP_CONNECTOR` ;
- création d'une prescription IPIP réelle dans Gestion des Actions ;
- ouverture du lien signé ; aucune identité métier en clair dans l'URL ;
- début de passation, fermeture navigateur, reconnexion : reprise exacte ;
- terminaison complète avec ressenti et PDF ;
- remontée TERMINE et import du PDF dans le dossier documentaire du bénéficiaire ;
- contrôle SHA-256 et absence de doublon après rejeu worker ;
- reconnexion sur la prescription terminée : consultation seule, aucune modification possible ;
- nouvelle prescription : nouvelle passation distincte ;
- arrêt/redémarrage application et worker : aucune perte de progression ni d'événement ;
- inspection logs : aucune réponse brute, aucun secret, aucun traceback présenté au bénéficiaire.

# Historique

## V0.3.0 - 26/07/2026

- Integration complete du moteur IA RVC360 niveau 2.
- Conversation progressive, une question ouverte a la fois.
- Preselection locale du referentiel avant appel IA.
- Sorties structurees JSON Schema.
- Controle deterministe des formulations interpretatives.
- Rejet automatique des mots absents du referentiel autorise.
- Justification et preuve textuelle obligatoires pour chaque hypothese.
- Configuration OpenAI et SMTP dans les Secrets.
- Conservation du commentaire fondamental dans le code.

## V0.2.0

- Premiere structure fonctionnelle sans moteur conversationnel complet.

## V0.3.1 - Audit pre-deploiement

- ajout d'un timeout reseau et de tentatives limitees pour l'API OpenAI ;
- ajout d'un plafond de sortie IA ;
- controle explicite du statut et du contenu de la reponse OpenAI ;
- comptage des tokens d'entree et de sortie dans l'export JSON ;
- clarification de l'information relative a `store=False` ;
- renforcement du `.gitignore` ;
- validation du referentiel : 240 valeurs sans doublon ;
- ajout du rapport `AUDIT_PREDEPLOIEMENT.md`.

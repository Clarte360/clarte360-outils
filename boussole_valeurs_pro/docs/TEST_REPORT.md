# Rapport de tests — v1.8.6

Source v1.8.2 : aucun test automatisé fourni.

Version v1.8.3 : 36 tests ajoutés pour validation métier et contrat Hub.

Version v1.8.4 : 43 tests automatisés réussis au total. Ajout des tests du garde-fou anti-perte de travail : beforeunload, réarmement après nouvelle saisie, empreinte métier, téléchargement JSON comme point sauvegardé et reprise JSON comme baseline propre.

Version v1.8.5 : 44 tests automatisés réussis ; intégration VPS/Mail/Hub registry.

Version v1.8.6 : 49 tests automatisés réussis sur la copie de travail avant publication GitHub. Régression JSON couverte : suppression du cache `exit_json_bytes`, recalcul du JSON sidebar depuis l'état courant, empreinte du contenu téléchargé, sérialisation centralisée et aller-retour JSON valide.

Compilation contrôlée sur la copie de travail : `python -m py_compile app.py validation.py hub_contract.py` : OK.

Après mise à jour du VPS, la même campagne doit être rejouée sur le serveur avant validation de production.

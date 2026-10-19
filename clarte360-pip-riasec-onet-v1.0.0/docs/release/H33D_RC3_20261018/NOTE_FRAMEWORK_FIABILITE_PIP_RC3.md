# Retour technique transverse — fiabilité PIP RC3
Statut : note de maintenance associée à PIP, à intégrer au référentiel commun lors de sa prochaine révision. Pas de propagation automatique aux autres applications.

1. Une erreur de restauration doit interrompre la création d'une nouvelle session persistante. Une erreur de lecture n'est pas une absence de sauvegarde.
2. Les écritures atomiques doivent préserver les permissions et le propriétaire d'un fichier existant. Une injection administrative sous sudo ne doit jamais remplacer une donnée applicative par un fichier root/0600 inaccessible au service.
3. Une livraison multi-documents se suit par type/nom et empreinte dans le périmètre de la passation. Un booléen unique ne suffit pas pour un rapport complémentaire.
4. Réémission technique : figer l'intention avant transmission, conserver une identité stable au rejeu, ne jamais avancer fictivement l'accusé de réception du destinataire.
5. Un booléen « e-mail vérifié » dans un JSON importé n'est pas une preuve serveur. Une adresse modifiée n'hérite pas d'une ancienne validation.
6. Un envoi interrompu ne peut pas être garanti « exactement une fois » sans protocole spécifique du serveur de messagerie. PIP suspend la répétition automatique et limite les relances explicites ; l'utilisateur doit vérifier sa boîte avant de relancer un envoi ambigu.
7. Les erreurs sont journalisées par catégorie, sans mots de passe, jetons, identités, réponses ou contenu PDF.
8. Les secrets restent exclusivement dans le coffre central existant. Aucun renommage de section ni nouvelle valeur secrète requis par RC3.

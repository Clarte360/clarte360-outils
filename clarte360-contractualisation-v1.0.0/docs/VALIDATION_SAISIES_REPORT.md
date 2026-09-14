# Audit validation des saisies — Contractualisation 1.2.2

Entrées couvertes : authentification admin, XLSM, APS JSON, NO_CLAR, identité bénéficiaire (dossier), coordonnées, dates, horaires, durée, séances, textes contractuels, montants/TVA, tableau financeurs, données reprises de la base, exports XLSX/JSON/PDF.

Règles ajoutées au niveau métier : noms internationaux réalistes ; e-mail unique sans CR/LF ; téléphone international plausible ; naissance plausible ; chronologie contrat/début/fin ; horaires cohérents ; nombres finis et bornés ; identifiant CLA strict ; contrôle APS ; contrôle fichier ; longueurs maximales et caractères de contrôle ; neutralisation des préfixes de formule Excel dans les textes exportés ; équilibre des financements.

Le bénéficiaire n'est pas un utilisateur de cette application : ses données sont des données administratives de contractualisation.

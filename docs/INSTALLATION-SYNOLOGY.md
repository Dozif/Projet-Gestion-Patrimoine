# Installer l'application sur le Synology

Durée : environ 30 minutes. Prérequis : DSM 7.2 avec **Container Manager** et **Éditeur de texte** installés
(Centre de paquets), un nom de domaine déjà utilisé pour une autre application, et l'accès au panneau de
configuration de DSM.

## 1. Préparer le sous-domaine

Chez votre fournisseur de nom de domaine, créez un enregistrement **CNAME** `patrimoine` qui pointe vers
le nom déjà utilisé par votre autre application (ou un enregistrement **A** vers la même adresse IP).
Le port 443 est déjà ouvert sur votre box pour l'autre application. Pour obtenir et renouveler le
certificat Let's Encrypt (étape 6), DSM a aussi besoin du port **80** redirigé vers le NAS ; c'est inutile
si vous avez déjà un certificat générique `*.votredomaine.fr`.

## 2. Copier le projet sur le NAS

1. Sur le PC, l'archive `dist/patrimoine-….zip` a été préparée (sinon : `bash scripts/creer_archive.sh`).
2. Dans **File Station**, ouvrez le dossier partagé `docker` (créez-le s'il n'existe pas) et téléversez-y l'archive.
3. Clic droit sur l'archive → **Extraire** → **Extraire ici**. L'archive crée le dossier `docker/patrimoine` :
   on doit y voir `docker-compose.yml`, `Dockerfile`, `manage.py`… Vous pouvez ensuite supprimer l'archive.

## 3. Créer le fichier .env

1. Sur le PC, générez deux valeurs aléatoires :
   - la clé secrète : `py -c "import secrets; print(secrets.token_urlsafe(50))"` ;
   - le code d'installation : `py -c "import secrets; print(secrets.token_urlsafe(16))"`.
2. Dans File Station, copiez `.env.example` en `.env` (dans `docker/patrimoine`), puis ouvrez `.env` avec
   **Éditeur de texte** de DSM (clic droit → Ouvrir avec) et remplacez :
   - `DJANGO_SECRET_KEY` par la clé générée ;
   - `patrimoine.votredomaine.fr` (deux fois) par votre sous-domaine ;
   - `PATRIMOINE_ADMIN_UTILISATEUR` par un identifiant **peu devinable** (5 erreurs de mot de passe bloquent
     cet identifiant pendant une heure : un identifiant évident permettrait à n'importe qui de vous bloquer) ;
   - `PATRIMOINE_ADMIN_MOT_DE_PASSE` par un mot de passe d'au moins 12 caractères ;
   - `PATRIMOINE_CODE_INSTALLATION` par le code généré (16 caractères minimum ; il sera demandé à la première connexion).

   N'utilisez dans les valeurs **ni `$`, ni `#`, ni guillemets, ni espaces** : Container Manager les interpréterait.
   L'application refuse de démarrer si la clé secrète est restée `a-remplacer`.

   Évitez le Bloc-notes de Windows pour ce fichier : il peut ajouter des fins de ligne Windows.
3. Le `.env` contient des secrets : si d'autres comptes DSM ont accès au dossier partagé `docker`, clic droit
   sur `.env` → **Propriétés** → **Autorisation** et ne laissez l'accès qu'aux administrateurs.

## 4. Construire et démarrer le conteneur

1. Ouvrez **Container Manager** → **Projet** → **Créer**.
2. Nom du projet : `patrimoine` ; chemin : `/docker/patrimoine` ; source : **Utiliser le docker-compose.yml existant**.
3. Cliquez sur **Suivant** (pas de portail Web Station), puis **Terminé**. La construction de l'image prend
   quelques minutes ; le projet passe ensuite à l'état « En cours d'exécution ».
4. Dans **Conteneur** → `patrimoine` → **Journal**, vous devez lire « Compte « … » créé » puis les
   lignes de démarrage de Gunicorn. Si le journal indique « unable to open database file », le dossier
   `docker/patrimoine/data` n'est pas accessible en écriture au conteneur (utilisateur n° 1000). Ne l'ouvrez
   **jamais** à tous les comptes : la base contient de quoi entrer dans l'application sans mot de passe.
   Donnez-le au seul utilisateur du conteneur, en SSH (voir « Secours » pour activer SSH) :
   `sudo chown -R 1000:1000 /volume1/docker/patrimoine/data && sudo chmod -R u+rwX,go-rwx /volume1/docker/patrimoine/data`
   (adaptez `volume1` si votre dossier `docker` est sur un autre volume), puis redémarrez le projet.

## 5. Publier l'application en HTTPS (proxy inversé)

1. **Panneau de configuration** → **Portail de connexion** → **Avancé** → **Proxy inversé** → **Créer**.
2. Nom : `patrimoine`. Source : protocole **HTTPS**, nom d'hôte `patrimoine.votredomaine.fr`, port **443**,
   cochez **Activer HSTS**. Destination : protocole **HTTP**, nom d'hôte **127.0.0.1**, port **8085**.
3. Onglet **En-tête personnalisé** → **Créer** → **En-tête personnalisé** : nom `X-Forwarded-Proto`, valeur `https`.
4. **Enregistrer**.
5. Vérification conseillée (SSH) : `sudo grep -rn -E 'client_max_body_size|proxy_request_buffering' /etc/nginx/`.
   L'application refuse d'elle-même les envois de plus de 12 Mo (64 Ko avant connexion) ; si une ligne
   `proxy_request_buffering off` concerne ce proxy, un envoi très lent peut occuper le serveur jusqu'à 30 s.

## 6. Certificat HTTPS

1. **Panneau de configuration** → **Sécurité** → **Certificat** → **Ajouter** → **Ajouter un nouveau certificat**
   → **Obtenir un certificat auprès de Let's Encrypt** → nom de domaine `patrimoine.votredomaine.fr`.
   (Si votre certificat existant couvre déjà `*.votredomaine.fr`, cette étape est inutile.)
2. Bouton **Paramètres** (même écran) : pour le service `patrimoine` (proxy inversé), choisissez ce certificat.

## 7. Première connexion

1. Ouvrez `https://patrimoine.votredomaine.fr` : connectez-vous avec l'identifiant et le mot de passe du `.env`.
2. Saisissez le **code d'installation**, scannez le QR code avec votre application d'authentification,
   puis saisissez le code à 6 chiffres.
3. Changez votre mot de passe : **Paramètres** → **Utilisateurs** → votre compte → bouton
   **Réinitialiser le mot de passe**. Effacez ensuite la valeur de `PATRIMOINE_ADMIN_MOT_DE_PASSE` dans `.env`.
4. Par sécurité, effacez ensuite la valeur de `PATRIMOINE_CODE_INSTALLATION` dans `.env` puis, dans
   Container Manager, **Projet** → `patrimoine` → **Arrêter**, puis **Démarrer** (l'enrôlement d'un nouveau
   téléphone sera alors fermé). Vérifiez dans **Conteneur** → `patrimoine` → **Détails** → **Environnement**
   que les deux variables (mot de passe et code) sont bien vides ; sinon, utilisez **Action** → **Construire**
   pour recréer le conteneur. Un mot de passe resté dans l'environnement recréerait le compte avec cet ancien
   mot de passe si la base venait à être vidée.

### Changer de téléphone

1. Connecté avec l'ancien téléphone : **Paramètres** → **TOTP devices** → votre appareil → **Supprimer**
   (ne vous contentez pas de décocher « confirmed » : l'ancien téléphone resterait valable).
2. Remettez un code d'installation dans `.env`, recréez le conteneur (**Action** → **Construire**), reconnectez-vous
   et scannez le nouveau QR code avec le nouveau téléphone. Effacez ensuite le code comme à l'étape 4.
3. Téléphone perdu ou volé : suivez « Secours » ci-dessous, et changez aussi le mot de passe.

## 8. Sauvegardes

1. **Panneau de configuration** → **Planificateur de tâches** → **Créer** → **Tâche planifiée** → **Script défini
   par l'utilisateur**. Utilisateur : `root`. Planification : tous les jours à 3 h. Script :
   `/usr/local/bin/docker exec -u patrimoine patrimoine python manage.py sauvegarder`
   Dans **Paramètres de tâche**, cochez l'envoi des détails par e-mail **uniquement en cas d'arrêt anormal**.
   Puis sélectionnez la tâche → **Exécuter**, et vérifiez qu'un fichier est apparu dans `docker/patrimoine/data/sauvegardes`.
2. **Hyper Backup** : créez une tâche qui sauvegarde le dossier `docker/patrimoine` (base, justificatifs,
   sauvegardes et `.env`) vers un disque externe ou un service cloud, avec **chiffrement côté client**.
3. Restaurer une sauvegarde remet aussi l'ancien mot de passe et l'ancienne double authentification qu'elle
   contient : si vous aviez changé l'un ou l'autre après cette sauvegarde (par exemple après une fuite),
   refaites ce changement juste après la restauration.

## Secours

À utiliser si la double authentification est bloquée (« Trop de codes incorrects » alors que vous n'avez pas
fait d'erreur : quelqu'un connaît votre mot de passe), si votre mot de passe a fuité ou si vous avez perdu
votre téléphone. Tout se fait depuis le NAS, sans passer par l'application.

1. Activez SSH : **Panneau de configuration** → **Terminal et SNMP** → **Activer le service SSH**. Depuis le PC :
   `ssh votre-compte-admin@adresse-du-nas` (désactivez SSH une fois terminé).
2. Changez le mot de passe (toutes les sessions ouvertes avec l'ancien sont fermées) :
   `sudo /usr/local/bin/docker exec -it -u patrimoine patrimoine python manage.py changepassword <identifiant>`
3. Débloquez la double authentification :
   `sudo /usr/local/bin/docker exec -u patrimoine patrimoine python manage.py debloquer_2fa`
4. Téléphone perdu : supprimez l'appareil avec
   `sudo /usr/local/bin/docker exec -u patrimoine patrimoine python manage.py debloquer_2fa --supprimer-appareil`,
   puis enrôlez le nouveau téléphone comme dans « Changer de téléphone » (étape 2).

## Mettre à jour l'application

1. Sur le PC : `bash scripts/creer_archive.sh`.
2. Sur le NAS : téléversez la nouvelle archive dans le dossier `docker` et extrayez-la au même endroit en
   choisissant **Écraser** (le dossier `data` et le fichier `.env` ne sont pas dans l'archive et restent intacts).
3. Container Manager → **Projet** → `patrimoine` → **Arrêter**, puis **Action** → **Construire** (Build) et **Démarrer**.
   Les migrations de la base s'appliquent automatiquement au démarrage.

## Recommandé

Pare-feu de DSM (**Panneau de configuration** → **Sécurité** → **Pare-feu**) : n'autoriser le port 443 que
depuis la France. Le **blocage automatique** de DSM (**Sécurité** → **Protection**) protège la connexion à DSM
lui-même, pas cette application : celle-ci a son propre blocage (5 erreurs de mot de passe).

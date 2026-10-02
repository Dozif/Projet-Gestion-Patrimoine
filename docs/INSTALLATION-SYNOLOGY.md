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

## 4. Construire et démarrer le conteneur

1. Ouvrez **Container Manager** → **Projet** → **Créer**.
2. Nom du projet : `patrimoine` ; chemin : `/docker/patrimoine` ; source : **Utiliser le docker-compose.yml existant**.
3. Cliquez sur **Suivant** (pas de portail Web Station), puis **Terminé**. La construction de l'image prend
   quelques minutes ; le projet passe ensuite à l'état « En cours d'exécution ».
4. Dans **Conteneur** → `patrimoine` → **Journal**, vous devez lire « Compte « … » créé » puis les
   lignes de démarrage de Gunicorn. Si le journal indique « unable to open database file », le dossier
   `docker/patrimoine/data` n'est pas accessible en écriture : dans File Station, clic droit sur `data` →
   **Propriétés** → **Autorisation**, donnez le contrôle total à « Everyone » sur ce seul dossier, puis
   redémarrez le projet.

## 5. Publier l'application en HTTPS (proxy inversé)

1. **Panneau de configuration** → **Portail de connexion** → **Avancé** → **Proxy inversé** → **Créer**.
2. Nom : `patrimoine`. Source : protocole **HTTPS**, nom d'hôte `patrimoine.votredomaine.fr`, port **443**,
   cochez **Activer HSTS**. Destination : protocole **HTTP**, nom d'hôte **127.0.0.1**, port **8085**.
3. Onglet **En-tête personnalisé** → **Créer** → **En-tête personnalisé** : nom `X-Forwarded-Proto`, valeur `https`.
4. **Enregistrer**.

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
   téléphone sera alors fermé ; remettez un code le jour où vous changez de téléphone). Vérifiez dans
   **Conteneur** → `patrimoine` → **Détails** → **Environnement** que la variable est bien vide ; sinon,
   utilisez **Action** → **Construire** pour recréer le conteneur.

## 8. Sauvegardes

1. **Panneau de configuration** → **Planificateur de tâches** → **Créer** → **Tâche planifiée** → **Script défini
   par l'utilisateur**. Utilisateur : `root`. Planification : tous les jours à 3 h. Script :
   `/usr/local/bin/docker exec -u patrimoine patrimoine python manage.py sauvegarder`
   Dans **Paramètres de tâche**, cochez l'envoi des détails par e-mail **uniquement en cas d'arrêt anormal**.
   Puis sélectionnez la tâche → **Exécuter**, et vérifiez qu'un fichier est apparu dans `docker/patrimoine/data/sauvegardes`.
2. **Hyper Backup** : créez une tâche qui sauvegarde le dossier `docker/patrimoine` (base, justificatifs,
   sauvegardes et `.env`) vers un disque externe ou un service cloud, avec **chiffrement côté client**.

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

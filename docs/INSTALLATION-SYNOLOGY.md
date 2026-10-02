# Installer l'application sur le Synology

Durée : environ 30 minutes. Prérequis : DSM 7.2 avec **Container Manager** et **Éditeur de texte** installés
(Centre de paquets), un nom de domaine déjà utilisé pour une autre application, et l'accès au panneau de
configuration de DSM.

## 1. Préparer le sous-domaine

Chez votre fournisseur de nom de domaine, créez un enregistrement **CNAME** `patrimoine` qui pointe vers
le nom déjà utilisé par votre autre application (ou un enregistrement **A** vers la même adresse IP).
Le port 443 étant déjà ouvert sur votre box pour l'autre application, rien d'autre n'est à ouvrir.

## 2. Copier le projet sur le NAS

1. Sur le PC, l'archive `dist/patrimoine-….zip` a été préparée (sinon : `bash scripts/creer_archive.sh`).
2. Dans **File Station**, ouvrez le dossier partagé `docker` (créez-le s'il n'existe pas), créez le dossier
   `patrimoine`, puis téléversez-y l'archive.
3. Clic droit sur l'archive → **Extraire** → **Extraire ici**. Déplacez le contenu du sous-dossier `patrimoine`
   extrait directement dans `docker/patrimoine` : on doit y voir `docker-compose.yml`, `Dockerfile`, `manage.py`…

## 3. Créer le fichier .env

1. Sur le PC, générez une clé secrète : `py -c "import secrets; print(secrets.token_urlsafe(50))"`.
2. Dans File Station, copiez `.env.example` en `.env` (dans `docker/patrimoine`), puis ouvrez `.env` avec
   **Éditeur de texte** de DSM (clic droit → Ouvrir avec) et remplacez :
   - `DJANGO_SECRET_KEY` par la clé générée ;
   - `patrimoine.votredomaine.fr` (deux fois) par votre sous-domaine ;
   - `PATRIMOINE_ADMIN_MOT_DE_PASSE` par un mot de passe d'au moins 12 caractères ;
   - `PATRIMOINE_CODE_INSTALLATION` par un code de votre choix (il sera demandé à la première connexion).

   Évitez le Bloc-notes de Windows pour ce fichier : il peut ajouter des fins de ligne Windows.

## 4. Construire et démarrer le conteneur

1. Ouvrez **Container Manager** → **Projet** → **Créer**.
2. Nom du projet : `patrimoine` ; chemin : `/docker/patrimoine` ; source : **Utiliser le docker-compose.yml existant**.
3. Cliquez sur **Suivant** (pas de portail Web Station), puis **Terminé**. La construction de l'image prend
   quelques minutes ; le projet passe ensuite à l'état « En cours d'exécution ».
4. Dans **Conteneur** → `patrimoine` → **Journal**, vous devez lire « Compte « franck » créé » puis les
   lignes de démarrage de Gunicorn.

## 5. Publier l'application en HTTPS (proxy inversé)

1. **Panneau de configuration** → **Portail de connexion** → **Avancé** → **Proxy inversé** → **Créer**.
2. Nom : `patrimoine`. Source : protocole **HTTPS**, nom d'hôte `patrimoine.votredomaine.fr`, port **443**,
   cochez **Activer HSTS**. Destination : protocole **HTTP**, nom d'hôte **localhost**, port **8085**.
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
3. Changez votre mot de passe : **Paramètres** → **Utilisateurs** → votre compte → lien « ce formulaire »
   sous le champ Mot de passe.
4. Par sécurité, effacez ensuite la valeur de `PATRIMOINE_CODE_INSTALLATION` dans `.env` puis, dans
   Container Manager, **Projet** → `patrimoine` → **Arrêter**, puis **Démarrer** (l'enrôlement d'un nouveau
   téléphone sera alors fermé ; remettez un code le jour où vous changez de téléphone).

## 8. Sauvegardes

1. **Panneau de configuration** → **Planificateur de tâches** → **Créer** → **Tâche planifiée** → **Script défini
   par l'utilisateur**. Utilisateur : `root`. Planification : tous les jours à 3 h. Script :
   `docker exec -u patrimoine patrimoine python manage.py sauvegarder`
2. **Hyper Backup** : créez une tâche qui sauvegarde le dossier `docker/patrimoine` (base, justificatifs,
   sauvegardes et `.env`) vers un disque externe ou un service cloud, avec **chiffrement côté client**.

## Mettre à jour l'application

1. Sur le PC : `bash scripts/creer_archive.sh`.
2. Sur le NAS : extrayez la nouvelle archive dans `docker/patrimoine` en remplaçant les fichiers
   (le dossier `data` et le fichier `.env` ne sont pas dans l'archive et restent intacts).
3. Container Manager → **Projet** → `patrimoine` → **Arrêter**, puis **Action** → **Construire** (Build) et **Démarrer**.
   Les migrations de la base s'appliquent automatiquement au démarrage.

## Recommandé

Pare-feu de DSM (**Panneau de configuration** → **Sécurité** → **Pare-feu**) : n'autoriser le port 443 que
depuis la France ; activer le **blocage automatique** des adresses IP (**Sécurité** → **Protection**).

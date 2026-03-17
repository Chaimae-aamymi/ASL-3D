# ASL-3D : Restauration Numerique Intelligente

ASL-3D est une plateforme web complete dediee a la preservation du patrimoine historique. Elle combine **Vision par Ordinateur**, **Deep Learning (YOLOv8)**, et **Photogrammetrie (SfM)** pour detecter les degradations structurelles, generer des modeles 3D, et produire des rapports de restauration professionnels.

![ASL-3D Dashboard](app/screenshots/asl3d_login_page_1772904583526.png)

## Nouvelles Fonctionnalites (V2 - 2026)

L'architecture a ete entierement repensee pour etre robuste, securisee, et generee cote serveur (SSR) :

- **Architecture SSR (Zero JavaScript)** : 100% du rendu est gere par Flask (Jinja2) avec un rafraichissement natif HTML pour les taches en arriere-plan.
- **Base de Donnees PostgreSQL** : Sauvegarde des utilisateurs, projets, analyses, historique des taches (`TaskStatus`) et rapports professionnels via `SQLAlchemy`.
- **Traitement Asynchrone Local** : Execution native de l'IA et de la modelisation 3D en arriere-plan (`threading.Thread`) sans bloquer l'interface utilisateur.
- **Authentification OAuth2 & Profil** : Connexion securisee avec email/mot de passe, **Google**, ou **GitHub** (`Authlib`). Gestion de profil utilisateur avec upload d'avatar dynamique.
- **Detection IA Avancee** : Utilisation de **YOLOv8** pour la detection fine des **fissures** (boites de delimitation), avec logique de diagnostic automatisee (Seuils de Tolerance) pour evaluer la severite du risque.
- **Approche Hybride 2D/3D** : Integration experimentale permettant la visualisation combinee des resultats d'analyse 2D (YOLOv8) interactifs associes directement au jumeau numerique 3D spatial (via `model-viewer`).
- **Gestion Stricte du Stockage** : Nettoyage physique intelligent du serveur (photos, `.glb`, PDFs, images annotees) lors de la suppression d'un projet (`shutil.rmtree`).
- **Reconstruction 3D Native** : Moteur Structure-from-Motion (SfM) en Python (OpenCV SIFT + trimesh) exportant des fichiers `.glb` affiches via `<model-viewer>`.
- **Interface Utilisateur Premium** : Tableau de bord repense avec un design interactif, moderne et immersif (Glassmorphism, indicateurs visuels de risques).
- **Generation de Rapports PDF** : Creation de dossiers de restauration complets (`fpdf2`) integrant le comptage des fissures détectees par YOLOv8 et des recommandations d'ingenierie dynamiques.

## Stack Technique

- **Backend** : Python 3.9+, Flask, SQLAlchemy, Authlib, Threading
- **Base de Donnees** : PostgreSQL + psycopg2-binary
- **Intelligence Artificielle** : Ultralytics (YOLOv8), TensorFlow/Keras, OpenCV
- **Traitement 3D** : Trimesh, OpenCV (SIFT/BFMatcher)
- **Frontend** : HTML5, CSS3, Jinja2, Phosphor Icons, `<model-viewer>`
- **Visualisation de donnees** : Matplotlib

---

## Installation et Lancement

### 1. Prerequis
- **Python 3.9+**
- **PostgreSQL** (ex: pgAdmin)
- Git

### 2. Cloner le projet
```bash
git clone https://github.com/Chaimae-aamymi/ASL-3D.git
cd ASL-3D/app
```

### 3. Configurer l'environnement Python
```bash
python -m venv venv_asl3d
# Sur Windows :
.\venv_asl3d\Scripts\activate
# Sur Mac/Linux :
# source venv_asl3d/bin/activate

pip install -r requirements.txt
```

### 4. Configurer la Base de Donnees
1. Lancez **PostgreSQL** et creez une base de donnees locale (ex: `asl3d_db`).
2. Copiez le fichier d'environnement :
   ```bash
   cp .env.example .env
   ```
3. Modifiez le fichier `.env` avec vos identifiants PostgreSQL (ex: `DB_URI=postgresql://postgres:votre_mdp@localhost:5432/asl3d_db`) et vos cles d'API (Google/GitHub) si vous souhaitez utiliser l'authentification sociale.
4. Executez le script d'initialisation pour creer les tables et le compte administrateur par defaut :
   ```bash
   python create_db.py
   ```

### 5. Demarrer l'application
```bash
python run.py
```
Ouvrez votre navigateur et allez sur : **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## Structure du Repertoire `app/`

- **`app.py`** : Coeur de l'application (Routes, Auth, Uploads, PDFs).
- **`models.py`** : Schema de base de donnees SQLAlchemy (Users, Projects, Analyses...).
- **`degradation_detector.py`** : Pipeline d'inference YAML/YOLOv8 et Keras.
- **`sfm_engine.py`** : Photogrammetrie et export 3D `.glb`.
- **`report_generator.py`** : Creation de PDF d'expertise.
- **`templates/`** : Vues Jinja2 (login, index, scanner, analysis...).
- **`static/`** : Fichiers CSS et assets (icones, modeles 3D generes, images uploadees).

## Auteur
**AAMYMI Chaimae**  
*Projet de Fin d'Etudes (PFE)*

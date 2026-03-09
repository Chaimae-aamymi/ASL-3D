# 🏛️ ASL-3D : Restauration Numérique Intelligente

ASL-3D est une plateforme web complète dédiée à la préservation du patrimoine historique. Elle combine **Vision par Ordinateur**, **Deep Learning (YOLOv8)**, et **Photogrammétrie (SfM)** pour détecter les dégradations structurelles, générer des modèles 3D, et produire des rapports de restauration professionnels.

![ASL-3D Dashboard](app/screenshots/asl3d_login_page_1772904583526.png)

## ✨ Nouvelles Fonctionnalités (V2 - 2026)

L'architecture a été entièrement repensée pour être robuste, sécurisée, et générée côté serveur (SSR) :

- **Architecture SSR (Zéro JavaScript)** : 100% du rendu est géré par Flask (Jinja2) avec un rafraîchissement natif HTML pour les tâches en arrière-plan.
- **Base de Données PostgreSQL** : Sauvegarde des utilisateurs, projets, analyses, historique des tâches (`TaskStatus`) et rapports professionnels via `SQLAlchemy`.
- **Traitement Asynchrone Local** : Exécution native de l'IA et de la modélisation 3D en arrière-plan (`threading.Thread`) sans bloquer l'interface utilisateur.
- **Authentification OAuth2** : Connexion sécurisée avec email/mot de passe, **Google**, ou **GitHub** (`Authlib`).
- **Détection IA Avancée** : Utilisation de **YOLOv8** pour la détection fine des **fissures** (boîtes de délimitation), avec logique de diagnostic automatisée (Seuils de Tolérance) pour évaluer la sévérité du risque.
- **Gestion Stricte du Stockage** : Nettoyage physique intelligent du serveur (photos, `.glb`, PDFs, images annotées) lors de la suppression d'un projet (`shutil.rmtree`).
- **Reconstruction 3D Native** : Moteur Structure-from-Motion (SfM) en Python (OpenCV SIFT + trimesh) exportant des fichiers `.glb` affichés via `<model-viewer>`.
- **Génération de Rapports PDF** : Création de dossiers de restauration complets (`fpdf2`) intégrant le comptage des fissures détectées par YOLOv8 et des recommandations d'ingénierie dynamiques.

## 🛠️ Stack Technique

- **Backend** : Python 3.9+, Flask, SQLAlchemy, Authlib, Threading
- **Base de Données** : PostgreSQL + psycopg2-binary
- **Intelligence Artificielle** : Ultralytics (YOLOv8), TensorFlow/Keras, OpenCV
- **Traitement 3D** : Trimesh, OpenCV (SIFT/BFMatcher)
- **Frontend** : HTML5, CSS3, Jinja2, Phosphor Icons, `<model-viewer>`
- **Visualisation de données** : Matplotlib

---

## 🚀 Installation et Lancement

### 1. Prérequis
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

### 4. Configurer la Base de Données
1. Lancez **PostgreSQL** et créez une base de données locale (ex: `asl3d_db`).
2. Copiez le fichier d'environnement :
   ```bash
   cp .env.example .env
   ```
3. Modifiez le fichier `.env` avec vos identifiants PostgreSQL (ex: `DB_URI=postgresql://postgres:votre_mdp@localhost:5432/asl3d_db`) et vos clés d'API (Google/GitHub) si vous souhaitez utiliser l'authentification sociale.
4. Exécutez le script d'initialisation pour créer les tables et le compte administrateur par défaut :
   ```bash
   python create_db.py
   ```

### 5. Démarrer l'application
```bash
python run.py
```
Ouvrez votre navigateur et allez sur : **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 📂 Structure du Répertoire `app/`

- **`app.py`** : Cœur de l'application (Routes, Auth, Uploads, PDFs).
- **`models.py`** : Schéma de base de données SQLAlchemy (Users, Projects, Analyses...).
- **`degradation_detector.py`** : Pipeline d'inférence YAML/YOLOv8 et Keras.
- **`sfm_engine.py`** : Photogrammétrie et export 3D `.glb`.
- **`report_generator.py`** : Création de PDF d'expertise.
- **`templates/`** : Vues Jinja2 (login, index, scanner, analysis...).
- **`static/`** : Fichiers CSS et assets (icônes, modèles 3D générés, images uploadées).

## 👨‍💻 Auteur
**AAMYMI Chaimae**  
*Projet de Fin d'Études (PFE)*

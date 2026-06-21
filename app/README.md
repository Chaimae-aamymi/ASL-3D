---
title: ASL-3D Restauration Numerique
emoji: 🏛️
colorFrom: purple
colorTo: blue
sdk: docker
pinned: true
app_port: 7860
---

# ASL-3D — Restauration Numérique Intelligente de Bâtiments Historiques

> **Projet de Fin d'Études** — AAMYMI Chaimae | 2025–2026

[![Python](https://img.shields.io/badge/Python-3.10-blue?logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-black?logo=flask)](https://flask.palletsprojects.com)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Detection-purple)](https://ultralytics.com)
[![COLMAP](https://img.shields.io/badge/COLMAP-SfM-orange)](https://colmap.github.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue?logo=postgresql)](https://postgresql.org)

---

## 🎯 Description

**ASL-3D** est une plateforme web intelligente de restauration numérique de bâtiments historiques. Elle combine la photogrammétrie, le Deep Learning et la modélisation 3D pour permettre aux ingénieurs du patrimoine de :

- 📸 **Scanner** un bâtiment à partir de photos ordinaires
- 🤖 **Détecter automatiquement** les dégradations (fissures, humidité, corrosion, érosion)
- 🏗️ **Reconstruire** un modèle 3D interactif (fichier `.glb`) exportable
- 📋 **Générer** un rapport de restauration complet et priorisé

---

## 🚀 Lien Public (Démonstration Live)

> **[https://asl3d.loca.lt](https://asl3d.loca.lt)**
>
> *(Si une page de sécurité s'affiche, entrez l'IP : `105.66.4.35` et cliquez sur "Submit")*

---

## 🛠️ Stack Technique

| Composant | Technologie |
|-----------|-------------|
| **Backend** | Flask 3.x (Python 3.10) |
| **Base de données** | PostgreSQL 15 + SQLAlchemy |
| **Détection IA** | YOLOv8 (Ultralytics) |
| **Reconstruction 3D** | COLMAP (SfM) + Open3D |
| **Export 3D** | Format GLB / GLTF |
| **Authentification** | Sessions Flask + OAuth2 (Google, GitHub) |
| **Vérification email** | SMTP Gmail (mot de passe d'application) |
| **Monitoring** | Prometheus + Grafana + Loki |
| **Déploiement** | Docker + Docker Compose + Tunnel sécurisé |

---

## ✨ Fonctionnalités

- ✅ **Authentification complète** : inscription locale avec vérification email, connexion Google OAuth, connexion GitHub OAuth
- ✅ **Gestion de projets** : création, suivi, archivage de projets de restauration
- ✅ **Scanner IA** : upload de photos → détection de dégradations par YOLOv8
- ✅ **Reconstruction 3D** : pipeline COLMAP → Open3D → export GLB interactif
- ✅ **Visionneuse 3D intégrée** : rotation, zoom, fullscreen dans le navigateur
- ✅ **Rapport PDF** : génération automatique de plans de restauration
- ✅ **Dashboard** : statistiques, activité récente, état des projets
- ✅ **Monitoring** : métriques Prometheus, logs Loki, dashboards Grafana
- ✅ **Accès public** : tunnel sécurisé sans serveur payant

---

## ⚙️ Installation Locale

### Prérequis
- Python 3.10+
- PostgreSQL 15
- COLMAP (`C:/colmap-x64-windows-nocuda/COLMAP.bat`)
- Node.js 20+ (pour le tunnel)

### Démarrage rapide

```bash
# 1. Cloner le projet
git clone https://github.com/Chaimae-aamymi/ASL-3D.git
cd ASL-3D/app

# 2. Créer l'environnement virtuel
python -m venv venv_asl3d
venv_asl3d\Scripts\activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer les variables d'environnement
cp .env.example .env
# Remplir les valeurs dans .env (DB_URI, MAIL_*, GOOGLE_*, etc.)

# 5. Initialiser la base de données
python create_db.py

# 6. Lancer l'application
python run.py
```

L'application sera disponible sur **http://127.0.0.1:5000**

### Lancement avec tunnel public

```bash
# Dans un second terminal
npx localtunnel --port 5050 --subdomain asl3d
# → Lien : https://asl3d.loca.lt
```

---

## 🐳 Déploiement Docker

```bash
docker-compose up -d --build
```

---

## 📁 Structure du Projet

```
app/
├── app.py                  # Application Flask principale
├── models.py               # Modèles SQLAlchemy
├── sfm_engine.py           # Moteur COLMAP SfM
├── reconstruction_engine.py # Pipeline Open3D
├── degradation_detector.py  # Détection YOLOv8
├── report_generator.py     # Génération de rapports
├── colab_api.py            # API GPU distant (optionnel)
├── templates/              # Pages HTML Jinja2
├── static/                 # CSS, JS, images
├── docker-compose.yml      # Configuration Docker
└── requirements.txt        # Dépendances Python
```

---

## 👩‍💻 Auteur

**AAMYMI Chaimae** — Étudiante en Génie Informatique  
Projet de Fin d'Études — 2025–2026

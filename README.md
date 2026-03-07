# ASL-3D: Restauration Numérique de Bâtiments Historiques

ASL-3D est une application web innovante dédiée à la détection de dégradations structurelles et à la planification de la restauration des bâtiments historiques, utilisant la vision par ordinateur et le Machine Learning.

## Fonctionnalités Principales

- **Détection Automatique avec IA :** Analyse d'images pour détecter diverses dégradations (fissures, humidité, érosion, champignons, etc.) grâce à des modèles CNN (MobileNetV2 pour la classification et U-Net pour la segmentation).
- **Rapport de Sévérité :** Évaluation de la gravité globale et génération de recommandations d'interventions ciblées pour chaque dégradation.
- **Modélisation 3D (Simulation) :** Reconstruction virtuelle du bâtiment pour aider les experts à visualiser les dégâts et la structure.
- **Guide de Restauration :** Génération d'un plan d'action détaillé (phases de réparation, durée, matériaux, précautions de sécurité).
- **Interface Moderne :** Thème sombre élégant, expérience utilisateur optimisée avec Phosphor Icons, et un enchaînement fluide entre les étapes d'analyse.

## Technologies Utilisées

- **Backend :** Python, Flask, OpenCV, TensorFlow/Keras
- **Frontend :** HTML5, Vanilla CSS, JavaScript (en cours de migration vers Server-Side Rendering avec Jinja2)
- **Design :** Phosphor Icons

## Installation et Lancement

1. **Cloner le projet**
   ```bash
   git clone https://github.com/Chaimae-aamymi/ASL-3D.git
   cd ASL-3D
   ```

2. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```
   *(Assurez-vous d'avoir Python 3.8+ installé)*

3. **Lancer le serveur local**
   ```bash
   cd app
   python run.py
   ```

4. **Accéder à l'application**
   Ouvrez votre navigateur sur `http://127.0.0.1:5000`

## Structure du Projet

- `/app/app.py` : Serveur Flask principal et contrôleurs backend.
- `/app/degradation_detector.py` : Pipeline d'Intelligence Artificielle (Deep Learning et Fallback OpenCV) pour l'analyse d'images.
- `/app/reconstruction_engine.py` : Logique de la génération de plans de restauration et estimation des coûts.
- `/app/templates/` : Vues HTML/Jinja2 de l'application.
- `/app/static/css/` : Feuilles de style, incluant le thème sombre moderne de l'application.

## Auteur
**AAMYMI Chaimae**
Projet de Fin d'Études (PFE)

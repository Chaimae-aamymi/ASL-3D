#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
EXEMPLES D'UTILISATION - ASL-3D

Démonstration des principales fonctionnalités de l'application
"""

# ============================================================================
# EXEMPLE 1: Utiliser le module de détection des dégradations
# ============================================================================

from degradation_detector import DegradationDetector
import numpy as np
from PIL import Image

# Créer une instance du détecteur
detector = DegradationDetector()

# Charger une image
image = Image.open('uploads/mon_batiment.jpg')
image_array = np.array(image)

# Détecter les dégradations
print("🔍 Analyse en cours...")
degradations = detector.detect(image_array)

# Afficher les résultats
print(f"✅ {len(degradations)} dégradations trouvées:")
for i, deg in enumerate(degradations, 1):
    print(f"  {i}. {deg['type'].upper()}")
    print(f"     - Sévérité: {deg['severity']}")
    print(f"     - Confiance: {int(deg['confidence']*100)}%")
    print(f"     - Zone: {deg['location']['width']}x{deg['location']['height']} pixels\n")

# Obtenir la sévérité globale
severity = detector.calculate_severity(degradations)
print(f"Sévérité globale: {severity.upper()}")

# Obtenir les recommandations
recommendations = detector.get_recommendations(degradations)
print("\n📋 Recommandations:")
for deg_type, recommendation in recommendations.items():
    print(f"  • {deg_type}: {recommendation}")

# Créer une visualisation
visualization = detector.visualize(image_array, degradations)
Image.fromarray(visualization).save('outputs/degradations_marked.png')
print("\n✅ Visualisation sauvegardée: outputs/degradations_marked.png")

# ============================================================================
# EXEMPLE 2: Utiliser le moteur de reconstruction 3D
# ============================================================================

from reconstruction_engine import ReconstructionEngine

# Créer une instance du reconstructor
reconstructor = ReconstructionEngine()

# Paramètres de reconstruction
params = {
    'quality': 'high',
    'scale': 1.5,
    'smoothness': 3.0,
    'detail': 7
}

# Reconstruire le modèle 3D
print("\n🏗️ Reconstruction 3D en cours...")
model_data = reconstructor.reconstruct('uploads/mon_batiment.jpg', params)

print(f"✅ Modèle créé:")
print(f"   - Vertices: {len(model_data['vertices'])}")
print(f"   - Faces: {len(model_data['faces'])}")

# Sauvegarder le modèle
reconstructor.save_model(model_data, 'outputs/batiment_3d.obj')
print(f"✅ Modèle sauvegardé: outputs/batiment_3d.obj")

# ============================================================================
# EXEMPLE 3: Générer un plan de restauration
# ============================================================================

print("\n📋 Génération du plan de restauration...")

# Supposons qu'on a les dégradations de l'exemple 1
plan = reconstructor.generate_restoration_plan(degradations)

print(f"\n📊 Plan de Restauration:")
print(f"   Total d'enjeux: {plan['summary']['total_issues']}")
print(f"   Durée estimée: {plan['summary']['estimated_duration']}")
print(f"   Facteur coût: {plan['summary']['estimated_cost_factor']}x")

print(f"\n📅 Phases ({len(plan['phases'])}):")
for phase in plan['phases']:
    print(f"   Phase {phase['phase']}: {phase['type'].upper()}")
    print(f"     - Durée: {phase['duration']}")
    print(f"     - Zones affectées: {phase['affected_areas']}")
    print(f"     - Étapes:")
    for step in phase['steps'][:2]:  # Afficher 2 premières étapes
        print(f"       • {step}")
    if len(phase['steps']) > 2:
        print(f"       ... et {len(phase['steps'])-2} autres étapes")

print(f"\n🛡️ Mesures de sécurité:")
for measure in plan['safety_measures'][:3]:
    print(f"   ✓ {measure}")
if len(plan['safety_measures']) > 3:
    print(f"   ... et {len(plan['safety_measures'])-3} autres")

# Sauvegarder le plan en JSON
import json
with open('outputs/plan_restoration.json', 'w', encoding='utf-8') as f:
    json.dump(plan, f, ensure_ascii=False, indent=2)
print("\n✅ Plan sauvegardé: outputs/plan_restoration.json")

# ============================================================================
# EXEMPLE 4: Utilisation via l'API Flask
# ============================================================================

"""
# Exemples de requêtes HTTP vers l'API ASL-3D:

# 1. Upload d'une image
POST http://127.0.0.1:5000/api/upload
Content-Type: multipart/form-data
Body: file=mon_batiment.jpg

# 2. Détection de dégradations
POST http://127.0.0.1:5000/api/detect-degradation/mon_batiment.jpg
Content-Type: application/json

# 3. Reconstruction 3D
POST http://127.0.0.1:5000/api/reconstruct-3d/mon_batiment.jpg
Content-Type: application/json
Body: {
  "params": {
    "quality": "high",
    "scale": 1.0,
    "smoothness": 2.5
  }
}

# 4. Plan de restauration
POST http://127.0.0.1:5000/api/restoration-plan/mon_batiment.jpg
Content-Type: application/json
Body: {
  "degradations": [...array de dégradations...]
}

# 5. Lister les fichiers
GET http://127.0.0.1:5000/api/files

# 6. Télécharger un résultat
GET http://127.0.0.1:5000/api/download/degradation_mon_batiment.jpg
"""

# ============================================================================
# EXEMPLE 5: Traitement par lot
# ============================================================================

import os
from pathlib import Path

print("\n\n🔄 Traitement par lot - Analyser tous les fichiers du dossier uploads:")

uploads_dir = 'uploads'
detector = DegradationDetector()
reconstructor = ReconstructionEngine()

image_files = [f for f in os.listdir(uploads_dir) 
               if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp'))]

for filename in image_files[:2]:  # Traiter les 2 premiers (exemple)
    filepath = os.path.join(uploads_dir, filename)
    print(f"\n📷 Traitement: {filename}")
    
    try:
        # Charger et analyser
        image = Image.open(filepath)
        image_array = np.array(image)
        
        # Détection
        degradations = detector.detect(image_array)
        print(f"   ✓ Dégradations détectées: {len(degradations)}")
        
        # Reconstruction
        model = reconstructor.reconstruct(filepath)
        print(f"   ✓ Modèle 3D créé: {len(model['vertices'])} vertices")
        
        # Plan
        plan = reconstructor.generate_restoration_plan(degradations)
        print(f"   ✓ Plan généré: {len(plan['phases'])} phases")
        
    except Exception as e:
        print(f"   ✗ Erreur: {e}")

# ============================================================================
# EXEMPLE 6: Configuration personnalisée
# ============================================================================

print("\n\n⚙️ Configuration personnalisée:")

from config import Config

print(f"Max file size: {Config.MAX_CONTENT_LENGTH / (1024*1024)}MB")
print(f"Upload folder: {Config.UPLOAD_FOLDER}")
print(f"Output folder: {Config.OUTPUT_FOLDER}")
print(f"Allowed extensions: {Config.ALLOWED_EXTENSIONS}")
print(f"Min area for detection: {Config.MIN_DEGRADATION_AREA} pixels²")
print(f"Confidence threshold: {Config.CONFIDENCE_THRESHOLD}")

# ============================================================================
# RÉSUMÉ
# ============================================================================

print("""

╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║        🏛️  ASL-3D - EXEMPLES D'UTILISATION                   ║
║                                                                    ║
║  ✅ Exemple 1: Détection des dégradations                         ║
║  ✅ Exemple 2: Reconstruction 3D                                  ║
║  ✅ Exemple 3: Plan de restauration                               ║
║  ✅ Exemple 4: API REST                                           ║
║  ✅ Exemple 5: Traitement par lot                                 ║
║  ✅ Exemple 6: Configuration                                      ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝

Pour plus d'informations:
  • README.md - Documentation technique
  • GUIDE_DEMARRAGE.txt - Guide d'installation
  • Code source - Docstrings détaillés

Créé avec ❤️ par AAMYMI Chaimae
""")

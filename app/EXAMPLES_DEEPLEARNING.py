# ============================================================================
# ASL-3D - Exemples d'utilisation du module Deep Learning
# Détection de dégradations avec modèles CNN (MobileNetV2 + U-Net)
# ============================================================================

import numpy as np
from PIL import Image
import cv2
from degradation_detector import DegradationDetector

print("="*70)
print("ASL-3D - Exemples de Deep Learning pour Détection de Dégradations")
print("="*70)

# ============================================================================
# EXEMPLE 1: Initialiser le détecteur avec modèles Deep Learning
# ============================================================================
print("\n[EXEMPLE 1] Initialisation du détecteur Deep Learning")
print("-" * 70)

detector = DegradationDetector()

# Afficher les informations sur les modèles
model_info = detector.get_model_info()
print(f"Modèle de classification: {model_info['classification_model']}")
print(f"Modèle de segmentation: {model_info['segmentation_model']}")
print(f"Framework: {model_info['framework']}")
print(f"Types de dégradation: {', '.join(model_info['degradation_types'])}")
print(f"Nombre de classes: {model_info['num_classes']}")


# ============================================================================
# EXEMPLE 2: Détecter les dégradations dans une image
# ============================================================================
print("\n[EXEMPLE 2] Détection de dégradations (avec fallback si non entraîné)")
print("-" * 70)

# Créer une image de test
test_image = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)

# Détecter les dégradations
degradations = detector.detect(test_image)

print(f"Nombre de dégradations détectées: {len(degradations)}")
for i, deg in enumerate(degradations, 1):
    print(f"\nDégradation {i}:")
    print(f"  Type: {deg['type']}")
    print(f"  Confidence: {deg['confidence']:.2%}")
    print(f"  Sévérité: {deg['severity']}")
    print(f"  Surface: {deg['area']:.0f} pixels²")


# ============================================================================
# EXEMPLE 3: Calculer le niveau de sévérité global
# ============================================================================
print("\n[EXEMPLE 3] Calcul de la sévérité globale")
print("-" * 70)

if degradations:
    severity = detector.calculate_severity(degradations)
    print(f"Niveau de sévérité global: {severity.upper()}")
    
    # Obtenir les recommandations
    recommendations = detector.get_recommendations(degradations)
    print("\nRecommandations de restauration:")
    for deg_type, recommendation in recommendations.items():
        print(f"  • {deg_type.upper()}: {recommendation}")


# ============================================================================
# EXEMPLE 4: Visualiser les dégradations détectées
# ============================================================================
print("\n[EXEMPLE 4] Génération de visualisation")
print("-" * 70)

if degradations:
    visualization = detector.visualize(test_image, degradations)
    print(f"Visualisation créée: {visualization.shape}")
    print("✓ Les dégradations sont annotées avec des rectangles colorés")
    print("✓ Chaque zone indique le type et le niveau de confiance")


# ============================================================================
# EXEMPLE 5: Informations détaillées sur les modèles
# ============================================================================
print("\n[EXEMPLE 5] Informations détaillées des modèles")
print("-" * 70)

info = detector.get_model_info()
print("Architecture de classification:")
print(f"  - Base: MobileNetV2 pré-entraîné (ImageNet)")
print(f"  - Couches supplémentaires: Dense(256), Dense(128), Dense(6)")
print(f"  - Optimiseur: Adam (learning_rate=1e-4)")
print(f"  - Loss: Categorical Crossentropy")

print("\nArchitecture de segmentation:")
print(f"  - Type: U-Net complète")
print(f"  - Résolution: 256x256 pixels")
print(f"  - Optimiseur: Adam (learning_rate=1e-3)")
print(f"  - Loss: Binary Crossentropy")


# ============================================================================
# EXEMPLE 6: Entraînement des modèles (Optionnel)
# ============================================================================
print("\n[EXEMPLE 6] Entraînement des modèles (structure)")
print("-" * 70)

print("Pour entraîner les modèles avec vos données:")
print("""
# Préparer vos données d'entraînement
training_images = np.load('training_data.npy')  # Shape: (N, 224, 224, 3)
training_labels = np.load('training_labels.npy')  # Shape: (N, 6) - one-hot encoded

# Normaliser les images
training_images = training_images.astype('float32') / 255.0

# Entraîner le modèle
detector.train_models(training_images, training_labels, epochs=50)

# Sauvegarder les modèles
detector.save_models('models/')

# Plus tard, charger les modèles pré-entraînés
detector.load_models('models/')
""")

print("✓ Les modèles MobileNetV2 et U-Net peuvent être entraînés")
print("✓ Transfer learning accélère considérablement l'apprentissage")
print("✓ Support de batch processing et GPU (si disponible)")


# ============================================================================
# EXEMPLE 7: Prédictions avec confiance variable
# ============================================================================
print("\n[EXEMPLE 7] Interprétation des niveaux de confiance")
print("-" * 70)

confidence_levels = {
    'Très haute (>80%)': '[HAUTE CONFIANCE] Recommandation urgente',
    'Haute (60-80%)': '[CONFIANCE MOYENNE] Recommandation importante',
    'Moyenne (30-60%)': '[À VALIDER] Recommandation suggérée',
    'Basse (<30%)': '[À VALIDER] Nécessite validation humaine'
}

for level, interpretation in confidence_levels.items():
    print(f"  • {level}: {interpretation}")

print("\n✓ Chaque prédiction inclut un score de confiance")
print("✓ Les seuils peuvent être ajustés selon les besoins")


print("\n" + "="*70)
print("FIN DES EXEMPLES - ASL-3D Deep Learning Ready!")
print("="*70)

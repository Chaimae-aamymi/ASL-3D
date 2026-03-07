import numpy as np
from PIL import Image
import cv2
import tensorflow as tf
try:
    from tensorflow import keras
    from tensorflow.keras import layers, models
except ImportError:
    try:
        import keras
        from keras import layers, models
    except ImportError:
        keras = None
        layers = None
        models = None
import json
from pathlib import Path
from icons import Icons, IconColors, IconText

class DegradationDetector:
    """
    Détecteur de dégradations utilisant Deep Learning (CNN)
    Modèle basé sur transfer learning avec MobileNetV2 et U-Net
    """
    
    def __init__(self):
        self.degradation_types = {
            'fissures': {'icon': Icons.FISSURES, 'color': IconColors.CRITICAL, 'severity': 'haute'},
            'humidite': {'icon': Icons.HUMIDITY, 'color': IconColors.MEDIUM, 'severity': 'moyenne'},
            'erosion': {'icon': Icons.EROSION, 'color': IconColors.HIGH, 'severity': 'moyenne'},
            'champignons': {'icon': Icons.FUNGI, 'color': IconColors.CRITICAL, 'severity': 'haute'},
            'decoloration': {'icon': Icons.DISCOLORATION, 'color': IconColors.LOW, 'severity': 'basse'},
            'effritement': {'icon': Icons.CRUMBLING, 'color': IconColors.MEDIUM, 'severity': 'moyenne'}
        }
        
        self.model = None
        self.segmentation_model = None
        self.class_names = list(self.degradation_types.keys())
    
    def build_models(self):
        """Construire les modèles de deep learning"""
        if self.model is None:
            self.model = self._build_classification_model()
        if self.segmentation_model is None:
            self.segmentation_model = self._build_segmentation_model()
    
    def _build_classification_model(self):
        """
        Construire un modèle de classification avec MobileNetV2
        Transfer Learning pour détecter les types de dégradations
        """
        base_model = keras.applications.MobileNetV2(
            input_shape=(224, 224, 3),
            include_top=False,
            weights='imagenet'
        )
        
        base_model.trainable = False
        
        model = models.Sequential([
            keras.Input(shape=(224, 224, 3)),
            layers.Lambda(keras.applications.mobilenet_v2.preprocess_input),
            base_model,
            layers.GlobalAveragePooling2D(),
            layers.Dense(256, activation='relu', name='dense_1'),
            layers.BatchNormalization(),
            layers.Dropout(0.5),
            layers.Dense(128, activation='relu', name='dense_2'),
            layers.BatchNormalization(),
            layers.Dropout(0.3),
            layers.Dense(len(self.class_names), activation='softmax', name='predictions')
        ])
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=1e-4),
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def _build_segmentation_model(self):
        """
        Construire un modèle U-Net pour la segmentation sémantique
        Localiser précisément les zones de dégradation
        """
        inputs = keras.Input(shape=(256, 256, 3))
        
        # Encodeur
        x = layers.Conv2D(32, 3, activation='relu', padding='same')(inputs)
        x = layers.BatchNormalization()(x)
        skip1 = x
        x = layers.MaxPooling2D(2)(x)
        
        x = layers.Conv2D(64, 3, activation='relu', padding='same')(x)
        x = layers.BatchNormalization()(x)
        skip2 = x
        x = layers.MaxPooling2D(2)(x)
        
        x = layers.Conv2D(128, 3, activation='relu', padding='same')(x)
        x = layers.BatchNormalization()(x)
        skip3 = x
        x = layers.MaxPooling2D(2)(x)
        
        # Goulot
        x = layers.Conv2D(256, 3, activation='relu', padding='same')(x)
        x = layers.BatchNormalization()(x)
        
        # Décodeur
        x = layers.UpSampling2D(2)(x)
        x = layers.Concatenate()([x, skip3])
        x = layers.Conv2D(128, 3, activation='relu', padding='same')(x)
        x = layers.BatchNormalization()(x)
        
        x = layers.UpSampling2D(2)(x)
        x = layers.Concatenate()([x, skip2])
        x = layers.Conv2D(64, 3, activation='relu', padding='same')(x)
        x = layers.BatchNormalization()(x)
        
        x = layers.UpSampling2D(2)(x)
        x = layers.Concatenate()([x, skip1])
        x = layers.Conv2D(32, 3, activation='relu', padding='same')(x)
        x = layers.BatchNormalization()(x)
        
        # Couche de sortie
        outputs = layers.Conv2D(1, 1, activation='sigmoid')(x)
        
        model = keras.Model(inputs=inputs, outputs=outputs)
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=1e-3),
            loss='binary_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def detect(self, image_array):
        """
        Détecter les dégradations dans l'image avec Deep Learning
        Utilise classification + segmentation sémantique
        """
        if self.model is None or self.segmentation_model is None:
            self.build_models()
        
        degradations = []
        
        # Pré-traiter l'image
        processed_image = self._preprocess_image(image_array)
        
        # Classification: Identifier quels types de dégradations sont présents
        class_predictions = self._classify_degradations(processed_image)
        
        # Segmentation: Localiser les zones affectées
        segmentation_mask = self._segment_degradations(processed_image)
        
        # Fusion des résultats
        degradations = self._merge_predictions(
            image_array,
            class_predictions,
            segmentation_mask
        )
        
        return degradations
    
    def _preprocess_image(self, image_array):
        """Pré-traiter l'image pour les modèles de Deep Learning"""
        if len(image_array.shape) == 2:
            # Convertir grayscale en RGB
            image_array = np.stack([image_array] * 3, axis=-1)
        
        # Redimensionner pour le modèle
        if image_array.shape[:2] != (224, 224):
            image_resized = cv2.resize(image_array, (224, 224))
        else:
            image_resized = image_array
        
        # Normaliser
        image_normalized = image_resized.astype('float32') / 255.0
        
        return np.expand_dims(image_normalized, axis=0)
    
    def _classify_degradations(self, processed_image):
        """Utiliser le modèle CNN pour classifier les types de dégradation"""
        try:
            predictions = self.model.predict(processed_image, verbose=0)
        except Exception as e:
            print(f"Avertissement: Les modèles doivent être entraînés d'abord. {e}")
            # Fallback avec détection traditionnelle
            return self._fallback_detection(processed_image)
        
        class_predictions = {}
        for idx, class_name in enumerate(self.class_names):
            confidence = float(predictions[0][idx])
            if confidence > 0.3:  # Seuil de confiance
                class_predictions[class_name] = confidence
        
        return class_predictions if class_predictions else self._fallback_detection(processed_image)
    
    def _segment_degradations(self, processed_image):
        """Utiliser U-Net pour segmenter les zones de dégradation"""
        try:
            # Redimensionner pour la segmentation
            seg_input = cv2.resize(processed_image[0], (256, 256))
            seg_input = np.expand_dims(seg_input, axis=0)
            
            # Prédire le masque de segmentation
            mask = self.segmentation_model.predict(seg_input, verbose=0)
            return mask[0, :, :, 0]
        except Exception as e:
            print(f"Avertissement: Segmentation non disponible. {e}")
            # Retourner un masque par défaut
            return np.ones((256, 256))
    
    def _fallback_detection(self, processed_image):
        """Détection de secours basée sur des filtres traditionnels"""
        # Décompresser l'image
        image = (processed_image[0] * 255).astype(np.uint8)
        if image.shape[2] == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        degradations = {}
        
        # Détection basée sur les contours
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            if len(contours) > 5:
                degradations['fissures'] = 0.7
            if cv2.countNonZero(edges) > image.size * 0.1:
                degradations['erosion'] = 0.65
        
        return degradations
    
    def _merge_predictions(self, image_array, class_predictions, segmentation_mask):
        """Fusionner les prédictions de classification et segmentation"""
        degradations = []
        
        if not class_predictions:
            return degradations
        
        # Redimensionner le masque à la taille de l'image originale
        h, w = image_array.shape[:2]
        mask_resized = cv2.resize(segmentation_mask, (w, h))
        
        # Appliquer un seuil au masque
        _, binary_mask = cv2.threshold(mask_resized, 0.5, 255, cv2.THRESH_BINARY)
        
        # Trouver les contours
        contours, _ = cv2.findContours(
            binary_mask.astype(np.uint8),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Pour chaque contour, créer une dégradation
        for idx, (deg_type, confidence) in enumerate(class_predictions.items()):
            if contours and idx < len(contours):
                contour = contours[idx]
                x, y, bw, bh = cv2.boundingRect(contour)
                area = cv2.contourArea(contour)
                
                degradations.append({
                    'type': deg_type,
                    'location': {
                        'x': int(x),
                        'y': int(y),
                        'width': int(bw),
                        'height': int(bh)
                    },
                    'severity': self.degradation_types[deg_type]['severity'],
                    'confidence': float(confidence),
                    'area': float(area)
                })
            else:
                # Si pas de contours, ajouter une dégradation sans localisation précise
                degradations.append({
                    'type': deg_type,
                    'location': {
                        'x': 0,
                        'y': 0,
                        'width': w,
                        'height': h
                    },
                    'severity': self.degradation_types[deg_type]['severity'],
                    'confidence': float(confidence),
                    'area': float(w * h)
                })
        
        return degradations
    
    def visualize(self, image_array, degradations):
        """Créer une visualisation des dégradations détectées"""
        visualization = image_array.copy()
        
        # Redimensionner si nécessaire
        if visualization.shape[:2] != (256, 256):
            visualization = cv2.resize(visualization, (256, 256))
        
        for degradation in degradations:
            loc = degradation['location']
            color = self.degradation_types[degradation['type']]['color']
            
            # Dessiner un rectangle autour de la zone
            cv2.rectangle(
                visualization,
                (loc['x'], loc['y']),
                (loc['x'] + loc['width'], loc['y'] + loc['height']),
                color, 3
            )
            
            # Ajouter un texte avec confidence
            text = self.get_degradation_display(degradation['type'], degradation['confidence'])
            cv2.putText(
                visualization,
                text,
                (loc['x'], max(loc['y'] - 10, 25)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2
            )
        
        return visualization.astype(np.uint8)
    
    def calculate_severity(self, degradations):
        """Calculer le niveau de sévérité global basé sur Deep Learning"""
        if not degradations:
            return 'faible'
        
        # Calculer sévérité basée sur confiance et type
        severity_scores = {
            'critique': 1.0,
            'haute': 0.8,
            'moyenne': 0.5,
            'basse': 0.2
        }
        
        total_score = 0
        for d in degradations:
            severity_score = severity_scores.get(d['severity'], 0.5)
            confidence = d['confidence']
            total_score += severity_score * confidence
        
        avg_score = total_score / len(degradations)
        
        if avg_score > 0.75:
            return 'critique'
        elif avg_score > 0.6:
            return 'haute'
        elif avg_score > 0.35:
            return 'moyenne'
        else:
            return 'faible'
    
    def get_recommendations(self, degradations):
        """Obtenir des recommandations de restauration basées sur Deep Learning"""
        recommendations = {
            'fissures': 'Remplissage avec mortier spécialisé, évaluation structurelle urgente recommandée',
            'humidite': 'Traitement imperméabilisant, drainage, ventilation forcée',
            'erosion': 'Retraitement de surface, application de revêtement protecteur haute performance',
            'champignons': 'Nettoyage biocide professionnel, traitement anti-fongique spécialisé',
            'decoloration': 'Nettoyage doux contrôlé, vernis protecteur UV',
            'effritement': 'Remplissage consolidation avancée, rejointoiement spécialisé'
        }
        
        result = {}
        for degradation in degradations:
            deg_type = degradation['type']
            confidence = degradation['confidence']
            
            # Adapter la recommandation selon la confiance
            base_rec = recommendations.get(deg_type, 'Évaluation personnalisée recommandée')
            
            if confidence > 0.8:
                result[deg_type] = f"[HAUTE CONFIANCE] {base_rec}"
            elif confidence > 0.6:
                result[deg_type] = f"[CONFIANCE MOYENNE] {base_rec}"
            else:
                result[deg_type] = f"[À VALIDER] {base_rec}"
        
        return result
    
    def train_models(self, training_data, labels, epochs=10, batch_size=32):
        """
        Entraîner les modèles de deep learning
        training_data: images (N, 224, 224, 3) normalisées
        labels: one-hot encoded labels (N, 6)
        """
        if self.model is None or self.segmentation_model is None:
            self.build_models()
        
        print("Entraînement du modèle de classification...")
        self.model.fit(
            training_data, labels,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=0.2,
            verbose=1
        )
        
        print("Modèle de classification entraîné avec succès!")
    
    def save_models(self, path='models'):
        """Sauvegarder les modèles entraînés"""
        Path(path).mkdir(exist_ok=True)
        
        if self.model:
            self.model.save(f'{path}/degradation_classifier.h5')
        if self.segmentation_model:
            self.segmentation_model.save(f'{path}/degradation_segmenter.h5')
        
        print(f"Modèles sauvegardés dans {path}/")
    
    def load_models(self, path='models'):
        """Charger les modèles pré-entraînés"""
        try:
            self.model = keras.models.load_model(f'{path}/degradation_classifier.h5')
            self.segmentation_model = keras.models.load_model(f'{path}/degradation_segmenter.h5')
            print("Modèles chargés avec succès!")
        except Exception as e:
            print(f"Impossible de charger les modèles: {e}")
    
    def get_model_info(self):
        """Retourner les informations sur les modèles utilisés"""
        return {
            'classification_model': 'MobileNetV2 + Couches personnalisées (Transfer Learning)',
            'segmentation_model': 'U-Net (256x256)',
            'framework': 'TensorFlow/Keras',
            'input_shape': '224x224 ou 256x256 RGB',
            'num_classes': len(self.class_names),
            'degradation_types': self.class_names,
            'architecture': 'Ensemble de 2 modèles CNN spécialisés',
            'status': 'Prêt pour apprentissage et inférence'
        }

    def get_degradation_display(self, deg_type, confidence):
        """Get professional display text for degradation"""
        # OpenCV doesn't support HTML elements (Phosphor icons), so we just return the text
        return f"{deg_type.capitalize()} ({int(confidence*100)}%)"

    def get_severity_display(self, severity):
        """Get professional display text for severity level"""
        return IconText.SEVERITY_LEVELS.get(severity, severity)

import numpy as np
from PIL import Image
import cv2

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers, models
    TENSORFLOW_AVAILABLE = True
except ImportError:
    try:
        import keras
        from keras import layers, models
        TENSORFLOW_AVAILABLE = True
    except ImportError:
        keras = None
        layers = None
        models = None
        TENSORFLOW_AVAILABLE = False

import json
from pathlib import Path
from datetime import datetime
try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None
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
            'effritement': {'icon': Icons.CRUMBLING, 'color': IconColors.MEDIUM, 'severity': 'moyenne'}
        }
        
        self.model = None
        self.segmentation_model = None
        self.class_names = list(self.degradation_types.keys())
    
    def build_models(self):
        """Construire les modèles de deep learning"""
        if not TENSORFLOW_AVAILABLE:
            print("[WARNING] TensorFlow/Keras not available. Using traditional detection only.")
            return
        
        if self.model is None:
            self.model = self._build_classification_model()
        if self.segmentation_model is None:
            self.segmentation_model = self._build_segmentation_model()
    
    def _build_classification_model(self):
        """
        Construire un modèle de classification avec MobileNetV2
        Transfer Learning pour détecter les types de dégradations
        """
        if not TENSORFLOW_AVAILABLE:
            return None
        
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
        if not TENSORFLOW_AVAILABLE:
            return None
        
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
    
    # ── YOLOv8 model cache (loaded once) ──────────────────────────────
    _yolo_model = None

    @classmethod
    def _get_yolo(cls):
        if cls._yolo_model is None:
            if YOLO is None:
                cls._yolo_model = False
                return None
            try:
                import os
                # Vérification des fichiers de poids locaux
                local_weights = ['yolov8n.pt', 'models/yolov8n.pt', 'best.pt', 'models/best.pt']
                found_weights = None
                for w in local_weights:
                    if os.path.exists(w):
                        found_weights = w
                        break
                
                if not found_weights:
                    local_onnx = ['yolov8n.onnx', 'models/yolov8n.onnx', 'best.onnx', 'models/best.onnx']
                    for w_onnx in local_onnx:
                        if os.path.exists(w_onnx):
                            found_weights = w_onnx
                            break
                
                if not found_weights:
                    print("[YOLOv8] Aucun fichier de poids YOLOv8 ('yolov8n.pt' ou 'best.pt') trouve localement.")
                    print("[YOLOv8] Utilisation immediate du traitement traditionnel de secours pour eviter le blocage de telechargement.")
                    cls._yolo_model = False
                    return None
                
                # Proposer une conversion automatique du modèle au format ONNX pour accélérer l'inférence locale sur CPU
                if found_weights.endswith('.pt'):
                    onnx_path = found_weights.replace('.pt', '.onnx')
                    if not os.path.exists(onnx_path):
                        print(f"[YOLOv8] Exportation du modele {found_weights} au format ONNX pour accelerer l'inference CPU...")
                        try:
                            pt_model = YOLO(found_weights)
                            pt_model.export(format='onnx')
                            print(f"[YOLOv8] Exportation reussie : {onnx_path}")
                        except Exception as ex:
                            print(f"[YOLOv8] Echec de l'exportation ONNX (utilisation du modele PT standard) : {ex}")
                    
                    if os.path.exists(onnx_path):
                        found_weights = onnx_path
                
                print(f"[YOLOv8] Chargement du modele local : {found_weights}")
                if found_weights.endswith('.onnx'):
                    cls._yolo_model = YOLO(found_weights, task='detect')
                else:
                    cls._yolo_model = YOLO(found_weights)
            except Exception as e:
                print(f"[YOLOv8] Could not load: {e}")
                cls._yolo_model = False  # sentinel: unavailable
        return cls._yolo_model if cls._yolo_model is not False else None

    # Mapping from COCO class names → degradation types
    _YOLO_CLASS_MAP = {
        'crack': 'fissures', 'fissure': 'fissures',
        'water': 'humidite', 'moisture': 'humidite', 'damp': 'humidite',
        'erosion': 'effritement', 'wear': 'effritement',
        'mold': 'humidite', 'fungus': 'humidite', 'moss': 'humidite',
        'stain': 'effritement', 'discoloration': 'effritement',
        'crumble': 'effritement', 'spall': 'effritement',
    }

    def _create_monument_mask(self, image_array):
        """Crée un masque pour ignorer le ciel (bleu/gris/blanc) et la végétation (vert/jaunâtre)"""
        hsv = cv2.cvtColor(image_array, cv2.COLOR_RGB2HSV)
        
        # Masque élargi pour le vert (arbres, feuilles, herbe sous ombre et soleil)
        lower_green = np.array([25, 20, 20])
        upper_green = np.array([95, 255, 255])
        mask_green = cv2.inRange(hsv, lower_green, upper_green)
        
        # Masque pour le bleu (ciel clair)
        lower_blue = np.array([85, 20, 50])
        upper_blue = np.array([140, 255, 255])
        mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
        
        # Masque pour le blanc/gris clair/brume (ciel couvert désaturé et lumineux)
        # Élargi (lower_white de 180->150, upper_white de 45->60 en saturation)
        # pour rejeter totalement les nuages plus sombres ou grisâtres
        lower_white = np.array([0, 0, 150])
        upper_white = np.array([180, 60, 255])
        mask_white = cv2.inRange(hsv, lower_white, upper_white)
        
        # Combiner et inverser pour ne garder que le monument/bâtiment
        mask_env = cv2.bitwise_or(mask_green, mask_blue)
        mask_env = cv2.bitwise_or(mask_env, mask_white)
        mask_monument = cv2.bitwise_not(mask_env)
        
        # Nettoyage morphologique pour boucher les petits trous dans le monument
        kernel = np.ones((5,5), np.uint8)
        mask_monument = cv2.morphologyEx(mask_monument, cv2.MORPH_CLOSE, kernel)
        mask_monument = cv2.morphologyEx(mask_monument, cv2.MORPH_OPEN, kernel)
        
        return mask_monument

    def detect_facade_bbox(self, image_array):
        """
        ÉTAPE 1 du pipeline : Localiser la zone principale de la façade/mur du bâtiment.
        
        Stratégie :
        - On supprime d'abord l'environnement via le masque HSV (ciel, arbres).
        - On supprime le sol/terre en s'appuyant sur la POSITION verticale :
          la terre est toujours dans la moitié BASSE de l'image.
        - On cherche ensuite la plus grande composante connexe verticale qui
          s'étend depuis le haut du bâtiment jusqu'à sa base.
        
        Retourne (x, y, w, h) ou None si aucune façade détectable.
        """
        h_img, w_img = image_array.shape[:2]
        
        # 1. Masque de base : exclure ciel, végétation, ciel blanc
        monument_mask = self._create_monument_mask(image_array)
        
        # 2. CLEF ANTI-SOL : Suppression agressive du sol.
        #    Le sol est TOUJOURS dans les ~25% inférieurs de l'image de rue.
        #    Un mur commence toujours AVANT les 70% de l'image en hauteur.
        #    On efface tout le bas pour ne conserver que la structure verticale.
        ground_cut = int(h_img * 0.75)  # On efface tout sous 75% de la hauteur
        monument_mask[ground_cut:, :] = 0
        
        # 3. Analyse des composantes connexes pour trouver la plus grande
        #    région continue = la façade principale
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            monument_mask, connectivity=8
        )
        
        if num_labels <= 1:
            # Aucune région détectée → retourner les 80% centraux par défaut
            margin_y = int(h_img * 0.12)
            margin_x = int(w_img * 0.05)
            return (margin_x, margin_y,
                    w_img - 2 * margin_x,
                    int(h_img * 0.80) - margin_y)
        
        # 4. Trouver la composante la plus haute ET la plus grande (= le mur)
        #    On pénalise les composantes dont le barycentre est trop bas
        #    (indice que c'est du sol plutôt qu'un mur)
        best_label = -1
        best_score = -1
        for lbl in range(1, num_labels):
            area = stats[lbl, cv2.CC_STAT_AREA]
            top_y = stats[lbl, cv2.CC_STAT_TOP]
            comp_h = stats[lbl, cv2.CC_STAT_HEIGHT]
            
            # Ignorer les petites composantes (bruit)
            if area < (w_img * h_img * 0.05):
                continue
            
            # Score = aire × bonus si la composante commence haut dans l'image
            # Une composante qui commence tôt (petit top_y) est probablement un mur
            height_bonus = 1.0 + max(0.0, (0.5 - top_y / h_img))
            score = area * height_bonus
            
            if score > best_score:
                best_score = score
                best_label = lbl
        
        if best_label < 0:
            # Fallback : zone centrale de l'image
            margin_y = int(h_img * 0.12)
            margin_x = int(w_img * 0.05)
            return (margin_x, margin_y,
                    w_img - 2 * margin_x,
                    int(h_img * 0.80) - margin_y)
        
        # 5. Extraire la bounding box de la façade sélectionnée
        fx  = int(stats[best_label, cv2.CC_STAT_LEFT])
        fy  = int(stats[best_label, cv2.CC_STAT_TOP])
        fw  = int(stats[best_label, cv2.CC_STAT_WIDTH])
        fh  = int(stats[best_label, cv2.CC_STAT_HEIGHT])
        
        # 6. Étendre légèrement la boîte vers le bas pour inclure la base du mur
        #    (parfois la jonction mur/sol est coupée par le masque)
        extension = int(h_img * 0.10)  # +10% vers le bas
        fy2 = min(h_img, fy + fh + extension)
        fh  = fy2 - fy
        
        # 7. Sécurité minimale : la façade doit couvrir au moins 20% de l'image
        if (fw * fh) < (w_img * h_img * 0.20):
            # Fallback sur la zone centrale large
            margin_y = int(h_img * 0.12)
            margin_x = int(w_img * 0.05)
            return (margin_x, margin_y,
                    w_img - 2 * margin_x,
                    int(h_img * 0.82) - margin_y)
        
        print(f"[FAÇADE] Zone détectée : x={fx} y={fy} w={fw} h={fh} "
              f"({fw*fh*100//(w_img*h_img)}% de l'image)")
        return (fx, fy, fw, fh)


    def detect_yolo(self, image_array: np.ndarray, facade_bbox=None) -> list:
        """
        ÉTAPE 2 — Détection YOLOv8 restreinte à la zone de façade.
        
        Si facade_bbox (x, y, w, h) est fourni, l'analyse ne porte que
        sur ce rectangle. Les coordonnées sont automatiquement réajustées
        vers le repère de l'image originale.
        """
        model = self._get_yolo()
        h_orig, w_orig = image_array.shape[:2]
        
        # ── Recadrage sur la façade ────────────────────────────────────
        if facade_bbox is not None:
            fx, fy, fw, fh = facade_bbox
            # Clamp pour rester dans l'image
            fx  = max(0, fx)
            fy  = max(0, fy)
            fx2 = min(w_orig, fx + fw)
            fy2 = min(h_orig, fy + fh)
            cropped = image_array[fy:fy2, fx:fx2]
            if cropped.size == 0:
                cropped = image_array
                fx, fy = 0, 0
        else:
            cropped = image_array
            fx, fy = 0, 0

        # Scale down for inference if too large
        h, w = cropped.shape[:2]
        if max(h, w) > 1024:
            scale = 1024 / max(h, w)
            proc_img = cv2.resize(cropped, (int(w * scale), int(h * scale)))
        else:
            proc_img = cropped
            scale = 1.0

        if model is None:
            result = self._traditional_detection(proc_img, facade_bbox=facade_bbox)
            return result

        try:
            # Masque monument sur le crop uniquement
            monument_mask = self._create_monument_mask(proc_img)
            
            # Sensibilité augmentée pour le PFE : imgsz=800 et conf=0.10
            results = model.predict(proc_img, imgsz=800, verbose=False, conf=0.10, device='cpu')
            degradations = []
            for r in results:
                for box in r.boxes:
                    cls_name = model.names[int(box.cls[0])].lower()
                    deg_type = self._YOLO_CLASS_MAP.get(cls_name)
                    if deg_type is None:
                        deg_type = 'fissures'
                    conf = float(box.conf[0])
                    info = self.degradation_types.get(deg_type, {})
                    
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                    
                    # Ignorer le bas du crop (jonction sol/mur résiduels)
                    if cy > proc_img.shape[0] * 0.90:
                        continue

                    # FILTRE ENVIRONNEMENT dans le crop
                    ix1 = max(0, int(x1))
                    iy1 = max(0, int(y1))
                    ix2 = min(proc_img.shape[1], int(x2))
                    iy2 = min(proc_img.shape[0], int(y2))
                    box_mask = monument_mask[iy1:iy2, ix1:ix2]
                    if box_mask.size > 0:
                        monument_pct = np.mean(box_mask) / 255.0
                        # Seuil moins agressif pour accepter plus de détections
                        if monument_pct < 0.15:
                            continue

                    # Réajuster les coordonnées vers l'image ORIGINALE
                    # (inverse du crop + inverse du scale)
                    ox1 = int(x1 / scale) + fx
                    oy1 = int(y1 / scale) + fy
                    ox2 = int(x2 / scale) + fx
                    oy2 = int(y2 / scale) + fy
                    
                    degradations.append({
                        'type': deg_type,
                        'severity': info.get('severity', 'moyenne'),
                        'confidence': round(conf, 3),
                        'location': {
                            'x': ox1,
                            'y': oy1,
                            'width': ox2 - ox1,
                            'height': oy2 - oy1
                        },
                        'area': float((ox2 - ox1) * (oy2 - oy1))
                    })
            return degradations if degradations else self._traditional_detection(image_array, facade_bbox=facade_bbox)
        except Exception as e:
            print(f"[YOLOv8] Inference error: {e}")
            return self._traditional_detection(image_array, facade_bbox=facade_bbox)

    def _traditional_detection(self, image_array, facade_bbox=None):
        """
        Détection de secours par vision classique (Canny + contours).
        Si facade_bbox est fourni, l'analyse est restreinte à cette zone.
        """
        h_orig, w_orig = image_array.shape[:2]
        offset_x, offset_y = 0, 0
        
        # ── Recadrage sur la façade ────────────────────────────────────
        if facade_bbox is not None:
            fx, fy, fw, fh = facade_bbox
            fx  = max(0, fx)
            fy  = max(0, fy)
            fx2 = min(w_orig, fx + fw)
            fy2 = min(h_orig, fy + fh)
            work_img = image_array[fy:fy2, fx:fx2]
            if work_img.size == 0:
                work_img = image_array
            else:
                offset_x, offset_y = fx, fy
        else:
            work_img = image_array

        h, w = work_img.shape[:2]
        
        if len(work_img.shape) == 3:
            gray = cv2.cvtColor(work_img, cv2.COLOR_RGB2GRAY)
        else:
            gray = work_img
            
        # Détection de fissures par Canny - Seuils baissés pour détecter plus de dégradations
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100)
        
        # Amélioration: détection par gradient Sobel pour capturer plus d'arêtes
        sobelx = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=5)
        sobely = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=5)
        gradient = cv2.magnitude(sobelx, sobely)
        gradient = cv2.normalize(gradient, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        _, gradient_edges = cv2.threshold(gradient, 30, 255, cv2.THRESH_BINARY)
        
        # Combiner Canny et Sobel pour meilleure couverture
        edges = cv2.bitwise_or(edges, gradient_edges)
        
        # FILTRE STRUCTUREL : exclure bas du crop (sol résiduel) et très haut (ciel)
        mask = np.ones((h, w), dtype=np.uint8) * 255
        margin_t = int(h * 0.05)   # haut : 5% (réduit)
        
        # FILTRE DYNAMIQUE DU SOL : si la boîte de la façade touche presque le bas de l'image d'origine,
        # on augmente la marge de sécurité au bas du crop pour éliminer la route/chaussée.
        if (offset_y + h) > (h_orig * 0.90):
            margin_b = int(h * 0.12)   # Marge de sol à 12% (réduit)
        else:
            margin_b = int(h * 0.05)   # Marge standard à 5% (réduit)
            
        mask[0:margin_t, :] = 0
        mask[h - margin_b:h, :] = 0
        
        # FILTRE ENVIRONNEMENT : masque monument sur le crop
        monument_mask_crop = self._create_monument_mask(work_img)
        combined_mask = cv2.bitwise_and(mask, monument_mask_crop)
        
        # FILTRE ANTI-FENÊTRES/PORTES & OMBRES (Dark Masking) :
        # Les cadres de fenêtres, les vitres, les portes ouvertes ou les ombres
        # créent de forts contrastes. En masquant les pixels très sombres, on évite les fausses détections.
        # Seuil augmenté pour être moins agressif
        mask_dark = cv2.inRange(gray, 0, 20)
        mask_not_dark = cv2.bitwise_not(mask_dark)
        combined_mask = cv2.bitwise_and(combined_mask, mask_not_dark)
        
        edges = cv2.bitwise_and(edges, edges, mask=combined_mask)
        
        kernel = np.ones((3,3), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=2)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5,5), np.uint8))
        
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        degradations = []
        
        # Seuil d'aire adaptatif proportionnel à la taille de l'image de travail
        # Réduit pour détecter les petites dégradations
        min_area = max(50, int((w * h) * 0.00005))
        
        # ── Analyse couleur HSV pour la détection multi-classes ──────────────
        if len(work_img.shape) == 3:
            hsv = cv2.cvtColor(work_img, cv2.COLOR_RGB2HSV)
        else:
            hsv = cv2.cvtColor(cv2.cvtColor(work_img, cv2.COLOR_GRAY2RGB), cv2.COLOR_RGB2HSV)
        
        # Détection humidité : zones sombres et désaturées (taches d'eau, auréoles)
        # Plage TRÈS restrictive pour éviter les faux positifs
        lower_damp = np.array([0, 0, 0])
        upper_damp = np.array([180, 40, 105])  # Saturation MAX 40 (très basse)
        mask_humid = cv2.inRange(hsv, lower_damp, upper_damp)
        humid_ratio = cv2.countNonZero(mask_humid) / max(1, h * w)
        
        # Détection moisissures/champignons : zones VERTES VIVES sur la pierre
        # Plage verte spécifique (teinte 25-95, saturation élevée)
        lower_moss = np.array([25, 30, 20])   # Teinte verte, saturation >= 30
        upper_moss = np.array([95, 255, 200])
        mask_moss = cv2.inRange(hsv, lower_moss, upper_moss)
        moss_ratio = cv2.countNonZero(mask_moss) / max(1, h * w)
        
        # Détection décoloration : zones ROUGE/ORANGE (rouille)
        # Deux plages: rouge foncé (0-20) et orange (150-180)
        lower_rust1 = np.array([0, 50, 70])    # Rouge avec saturation élevée
        upper_rust1 = np.array([20, 255, 255])
        lower_rust2 = np.array([150, 50, 70])  # Orange avec saturation élevée
        upper_rust2 = np.array([180, 255, 255])
        mask_rust1 = cv2.inRange(hsv, lower_rust1, upper_rust1)
        mask_rust2 = cv2.inRange(hsv, lower_rust2, upper_rust2)
        mask_rust = cv2.bitwise_or(mask_rust1, mask_rust2)
        rust_ratio = cv2.countNonZero(mask_rust) / max(1, h * w)
        
        # Analyse des contours
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            
            x, y, bw, bh = cv2.boundingRect(cnt)
            
            # FILTRE MAÇONNERIE : joints de mortier rectilignes (mais moins agressif)
            # Ignorer uniquement les joints très rectilignes (rapport d'aspect extrême)
            if (bw > 80 and bh < 3) or (bh > 80 and bw < 3):
                continue
            
            aspect_ratio = float(bw) / bh if bh > 0 else 1.0
            
            # ── Analyse locale de la zone du contour ────────────────────
            roi_hsv = hsv[y:y+bh, x:x+bw]
            roi_gray = gray[y:y+bh, x:x+bw]
            
            if roi_hsv.size == 0 or roi_gray.size == 0:
                continue
            
            # Caractéristiques locales
            local_sat = float(roi_hsv[:, :, 1].mean())   # saturation moyenne
            local_val = float(roi_hsv[:, :, 2].mean())   # luminosité moyenne
            local_hue = float(roi_hsv[:, :, 0].mean())   # teinte moyenne
            local_lap = cv2.Laplacian(roi_gray, cv2.CV_64F).var()  # rugosité locale
            
            # Périmètre et circularité
            perimeter = cv2.arcLength(cnt, True)
            circularity = (4 * np.pi * area / (perimeter ** 2)) if perimeter > 0 else 0
            
            # ── Classification multi-critères AMÉLIORÉE ─────────────────────────────
            
            # Calcul de caractéristiques supplémentaires pour meilleure discrimination
            local_hue_std = float(roi_hsv[:, :, 0].std())      # variance de teinte
            local_sat_std = float(roi_hsv[:, :, 1].std())      # variance de saturation
            local_val_std = float(roi_hsv[:, :, 2].std())      # variance de luminosité
            
            # Ratio de pixels très sombres (noirs)
            dark_pixels = np.sum(roi_gray < 30)
            dark_ratio = dark_pixels / max(1, roi_gray.size)
            
            # Contraste local (écart max-min)
            local_contrast = float(roi_gray.max() - roi_gray.min())
            
            # ── ORDRE DE PRIORITÉ (du plus spécifique au moins spécifique) ──
            # IMPORTANT: Utiliser AUSSI les critères globaux (humid_ratio, moss_ratio, rust_ratio)
            
            # 1. FISSURES : allongées ET rugueuses (TRÈS SPÉCIFIQUE)
            # Relâcher légèrement les critères pour détecter les fissures fines
            if ((aspect_ratio > 2.5 or aspect_ratio < 0.4) and 
                (local_lap > 30)):
                deg_type = 'fissures'
                conf = min(0.96, 0.65 + (min(local_lap / 300.0, 0.31)))
            
            # 2. HUMIDITÉ : zones très sombres, peu saturées ou biologiquement actives
            elif (humid_ratio > 0.01 or moss_ratio > 0.008 or
                  (local_val < 105 and 
                   local_sat < 45 and 
                   local_sat_std < 25)):
                deg_type = 'humidite'
                conf = min(0.92, 0.68 + (min((1 - local_sat/50) * 0.24, 0.24)))
            
            # 3. EFFRITEMENT : PAR DÉFAUT (dernière option, inclut érosion et altérations)
            else:
                deg_type = 'effritement'
                conf = 0.70
            
            # Réajuster les coordonnées vers l'image ORIGINALE
            degradations.append({
                'type': deg_type,
                'location': {
                    'x': int(x) + offset_x,
                    'y': int(y) + offset_y,
                    'width': int(bw),
                    'height': int(bh)
                },
                'severity': self.degradation_types[deg_type]['severity'],
                'confidence': conf,
                'area': float(area)
            })

        
        # ── DÉTECTION BASÉE SUR LES MASQUES GLOBAUX DE COULEUR ──────────────────
        # Détecte les zones colorées qui n'ont pas assez de bords (zones uniformes)
        
        # EFFRITEMENT (Décoloration/Rouille/Altération): détecter si ratio élevé et pas déjà détecté
        if rust_ratio > 0.01 and not any(d['type'] == 'effritement' for d in degradations):
            # Trouver la bounding box des pixels orange/rouges
            rust_contours, _ = cv2.findContours(mask_rust, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if rust_contours:
                # Prendre le plus grand contour rouge/orange
                largest_rust = max(rust_contours, key=cv2.contourArea)
                x_r, y_r, w_r, h_r = cv2.boundingRect(largest_rust)
                if w_r > 10 and h_r > 10:  # Au moins 10x10 pixels
                    degradations.append({
                        'type': 'effritement',
                        'location': {
                            'x': int(x_r) + offset_x,
                            'y': int(y_r) + offset_y,
                            'width': int(w_r),
                            'height': int(h_r)
                        },
                        'severity': self.degradation_types['effritement']['severity'],
                        'confidence': min(0.82, 0.58 + rust_ratio * 3.0),
                        'area': float(cv2.contourArea(largest_rust))
                    })
        
        # HUMIDITÉ (Moisissures/Champignons): détecter si ratio élevé mais pas d'autres contours
        if moss_ratio > 0.02 and not any(d['type'] == 'humidite' for d in degradations):
            # Trouver la bounding box des pixels verts
            moss_contours, _ = cv2.findContours(mask_moss, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if moss_contours:
                # Prendre le plus grand contour vert
                largest_moss = max(moss_contours, key=cv2.contourArea)
                x_m, y_m, w_m, h_m = cv2.boundingRect(largest_moss)
                if w_m > 10 and h_m > 10:  # Au moins 10x10 pixels
                    degradations.append({
                        'type': 'humidite',
                        'location': {
                            'x': int(x_m) + offset_x,
                            'y': int(y_m) + offset_y,
                            'width': int(w_m),
                            'height': int(h_m)
                        },
                        'severity': self.degradation_types['humidite']['severity'],
                        'confidence': min(0.85, 0.60 + moss_ratio * 3.0),
                        'area': float(cv2.contourArea(largest_moss))
                    })

        # Retourner jusqu'à 50 dégradations (augmenté pour meilleure couverture)
        # mais garder les plus grandes (plus significatives) en priorité
        return sorted(degradations, key=lambda x: x['area'], reverse=True)[:50]

    def detect(self, image_array):
        """
        Pipeline en 2 étapes :
          1. Localiser la façade/mur principal du bâtiment (detect_facade_bbox)
          2. Détecter les dégradations UNIQUEMENT dans cette zone
        """
        # ── ÉTAPE 1 : Localisation de la façade ───────────────────────
        facade_bbox = self.detect_facade_bbox(image_array)
        
        # ── ÉTAPE 2a : YOLOv8 (zone façade seulement) ─────────────────
        yolo_result = self.detect_yolo(image_array, facade_bbox=facade_bbox)
        # Retourner les résultats YOLOv8 s'ils sont significatifs (au moins 1 détection)
        if yolo_result and len(yolo_result) > 0:
            return yolo_result
        
        # ── ÉTAPE 2b : Détection traditionnelle (failsafe) ─────────────────────────────
        # Toujours utiliser cette méthode comme fallback car elle est plus fiable
        traditional_result = self._traditional_detection(image_array, facade_bbox=facade_bbox)
        if traditional_result and len(traditional_result) > 0:
            return traditional_result
        
        # ── ÉTAPE 2c : Keras CNN fallback (ultime recours) ─────────────────────────────
        if self.model is None or self.segmentation_model is None:
            self.build_models()

        processed_image = self._preprocess_image(image_array)
        class_predictions = self._classify_degradations(processed_image)
        segmentation_mask = self._segment_degradations(processed_image)
        degradations = self._merge_predictions(
            image_array, class_predictions, segmentation_mask
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
                degradations['effritement'] = 0.65
        
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
        # Optimized visualization: use a reasonably sized canvas
        h, w = image_array.shape[:2]
        target_size = 640
        if max(h, w) > target_size:
            scale = target_size / max(h, w)
            visualization = cv2.resize(image_array, (int(w * scale), int(h * scale)))
            # Adjust degradation coordinates to new scale
            display_degradations = []
            for d in degradations:
                new_d = d.copy()
                new_d['location'] = {
                    'x': int(d['location']['x'] * scale),
                    'y': int(d['location']['y'] * scale),
                    'width': int(d['location']['width'] * scale),
                    'height': int(d['location']['height'] * scale)
                }
                display_degradations.append(new_d)
        else:
            visualization = image_array.copy()
            display_degradations = degradations
        
        for degradation in display_degradations:
            loc = degradation['location']
            hex_color = self.degradation_types[degradation['type']]['color']
            # Convert hex string (e.g. '#ff6b6b') to BGR tuple for OpenCV
            if isinstance(hex_color, str) and hex_color.startswith('#'):
                h = hex_color.lstrip('#')
                if len(h) == 6:
                    color = tuple(int(h[i:i+2], 16) for i in (4, 2, 0))
                else:
                    color = (0, 0, 255)
            else:
                color = hex_color
            
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

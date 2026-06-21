# -*- coding: utf-8 -*-
"""
ASL-3D - API GPU Déportée pour Google Colab (GPU T4)
Auteur : AAMYMI Chaimae / Expert Cloud & Vision par Ordinateur
Usage :
1. Importer ce script dans un bloc-notes Google Colab.
2. Installer les dépendances : !pip install flask ultralytics open3d trimesh opencv-python-headless Pillow pyngrok
3. Installer COLMAP sur Colab : !apt-get update && apt-get install -y colmap
4. Lancer le tunnel ngrok pour exposer le port 5000.
5. Exécuter l'application avec : python colab_api.py
"""

import os
import io
import sys
import zipfile
import shutil
import tempfile
import subprocess
import numpy as np
from PIL import Image
import cv2
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from ultralytics import YOLO

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB max

# ==========================================
# CONFIGURATION & CACHE DES MODÈLES YOLO
# ==========================================
YOLO_MODEL = None

def get_yolo_model():
    global YOLO_MODEL
    if YOLO_MODEL is None:
        # Si un fichier 'best.pt' est importé sur Colab, on le charge, sinon yolov8n.pt
        weights = 'best.pt' if os.path.exists('best.pt') else 'yolov8n.pt'
        print(f"[*] Chargement de YOLOv8 avec les poids {weights} sur GPU...")
        YOLO_MODEL = YOLO(weights)
    return YOLO_MODEL

YOLO_CLASS_MAP = {
    'crack': 'fissures', 'fissure': 'fissures',
    'water': 'humidite', 'moisture': 'humidite', 'damp': 'humidite',
    'erosion': 'effritement', 'wear': 'effritement',
    'mold': 'humidite', 'fungus': 'humidite', 'moss': 'humidite',
    'stain': 'effritement', 'discoloration': 'effritement',
    'crumble': 'effritement', 'spall': 'effritement',
}

DEGRADATION_TYPES = {
    'fissures': {'severity': 'haute'},
    'humidite': {'severity': 'moyenne'},
    'effritement': {'severity': 'moyenne'}
}

# ==========================================
# HELPERS DE TRAITEMENT D'IMAGE & FAÇADE
# ==========================================
def create_monument_mask(image_array):
    hsv = cv2.cvtColor(image_array, cv2.COLOR_RGB2HSV)
    mask_green = cv2.inRange(hsv, np.array([25, 20, 20]), np.array([95, 255, 255]))
    mask_blue = cv2.inRange(hsv, np.array([85, 20, 50]), np.array([140, 255, 255]))
    mask_white = cv2.inRange(hsv, np.array([0, 0, 150]), np.array([180, 60, 255]))
    
    mask_env = cv2.bitwise_or(mask_green, mask_blue)
    mask_env = cv2.bitwise_or(mask_env, mask_white)
    mask_monument = cv2.bitwise_not(mask_env)
    
    kernel = np.ones((5,5), np.uint8)
    mask_monument = cv2.morphologyEx(mask_monument, cv2.MORPH_CLOSE, kernel)
    mask_monument = cv2.morphologyEx(mask_monument, cv2.MORPH_OPEN, kernel)
    return mask_monument

def detect_facade_bbox(image_array):
    h_img, w_img = image_array.shape[:2]
    monument_mask = create_monument_mask(image_array)
    
    # Éliminer le sol (bas 25%)
    ground_cut = int(h_img * 0.75)
    monument_mask[ground_cut:, :] = 0
    
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(monument_mask, connectivity=8)
    if num_labels <= 1:
        return (int(w_img * 0.05), int(h_img * 0.12), int(w_img * 0.9), int(h_img * 0.68))
    
    best_label = -1
    best_score = -1
    for lbl in range(1, num_labels):
        area = stats[lbl, cv2.CC_STAT_AREA]
        top_y = stats[lbl, cv2.CC_STAT_TOP]
        if area < (w_img * h_img * 0.05):
            continue
        height_bonus = 1.0 + max(0.0, (0.5 - top_y / h_img))
        score = area * height_bonus
        if score > best_score:
            best_score = score
            best_label = lbl
            
    if best_label < 0:
        return (int(w_img * 0.05), int(h_img * 0.12), int(w_img * 0.9), int(h_img * 0.68))
        
    fx  = int(stats[best_label, cv2.CC_STAT_LEFT])
    fy  = int(stats[best_label, cv2.CC_STAT_TOP])
    fw  = int(stats[best_label, cv2.CC_STAT_WIDTH])
    fh  = int(stats[best_label, cv2.CC_STAT_HEIGHT])
    
    # Étendre de 10% vers le bas
    fy2 = min(h_img, fy + fh + int(h_img * 0.10))
    fh  = fy2 - fy
    return (fx, fy, fw, fh)

# ==========================================
# ACCUEIL / DASHBOARD DE L'API
# ==========================================
@app.route('/')
def home():
    device = "CUDA (GPU Activé)" if YOLO is not None else "CPU uniquement"
    return f"""
    <html>
        <head>
            <title>ASL-3D GPU Remote API</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #121824; color: #e2e8f0; text-align: center; padding: 50px; }}
                .container {{ background-color: #1e293b; padding: 40px; border-radius: 12px; display: inline-block; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
                h1 {{ color: #38bdf8; margin-bottom: 10px; }}
                .status {{ font-weight: bold; color: #4ade80; font-size: 1.2em; margin: 15px 0; }}
                .info {{ font-size: 0.95em; color: #94a3b8; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🏛️ ASL-3D GPU API</h1>
                <p>Serveur d'inférence déporté en cours d'exécution sur Google Colab.</p>
                <div class="status">Statut : Prêt à recevoir les calculs GPU</div>
                <div class="info">Matériel : T4 GPU | Cadre de traitement : {device}</div>
                <div class="info" style="margin-top: 15px;">Routes disponibles : <code>/api/process_yolo</code> | <code>/api/process_colmap</code></div>
            </div>
        </body>
    </html>
    """

# ==========================================
# ROUTE 1 : DÉTECTION IA AVEC GPU (YOLOv8)
# ==========================================
@app.route('/api/process_yolo', methods=['POST'])
def process_yolo():
    if 'file' not in request.files:
        return jsonify({"error": "Aucun fichier envoye (champ 'file' requis)"}), 400
        
    file = request.files['file']
    if not file.filename.endswith('.zip'):
        return jsonify({"error": "Le fichier doit etre un ZIP d'images"}), 400

    # Création du dossier temporaire
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, 'images.zip')
    file.save(zip_path)

    # Extraction des images
    extract_dir = os.path.join(temp_dir, 'images')
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    try:
        model = get_yolo_model()
        images = [f for f in os.listdir(extract_dir) if f.lower().endswith(('.jpg', '.png', '.jpeg', '.jfif', '.bmp'))]
        
        if not images:
            return jsonify({"error": "Aucune image valide trouvee dans le ZIP"}), 400

        all_degradations = []
        counts = {k: 0 for k in DEGRADATION_TYPES.keys()}

        for image_name in images:
            image_path = os.path.join(extract_dir, image_name)
            image_arr = np.array(Image.open(image_path).convert('RGB'))
            
            # Détection de la façade
            facade_bbox = detect_facade_bbox(image_arr)
            h_orig, w_orig = image_arr.shape[:2]
            
            # Recadrage
            fx, fy, fw, fh = facade_bbox
            fx = max(0, fx)
            fy = max(0, fy)
            fx2 = min(w_orig, fx + fw)
            fy2 = min(h_orig, fy + fh)
            cropped = image_arr[fy:fy2, fx:fx2]
            
            if cropped.size == 0:
                cropped = image_arr
                fx, fy = 0, 0
                
            h, w = cropped.shape[:2]
            scale = 1.0
            if max(h, w) > 1024:
                scale = 1024 / max(h, w)
                proc_img = cv2.resize(cropped, (int(w * scale), int(h * scale)))
            else:
                proc_img = cropped

            # Inférence GPU YOLOv8
            monument_mask = create_monument_mask(proc_img)
            results = model.predict(proc_img, imgsz=640, verbose=False, conf=0.25, device='cuda')

            for r in results:
                for box in r.boxes:
                    cls_name = model.names[int(box.cls[0])].lower()
                    deg_type = YOLO_CLASS_MAP.get(cls_name, 'fissures')
                    conf = float(box.conf[0])
                    
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                    
                    if cy > proc_img.shape[0] * 0.90:
                        continue

                    # Filtre d'environnement
                    ix1, iy1 = max(0, int(x1)), max(0, int(y1))
                    ix2, iy2 = min(proc_img.shape[1], int(x2)), min(proc_img.shape[0], int(y2))
                    box_mask = monument_mask[iy1:iy2, ix1:ix2]
                    if box_mask.size > 0:
                        if (np.mean(box_mask) / 255.0) < 0.15:
                            continue

                    # Coordonnées globales
                    ox1 = int(x1 / scale) + fx
                    oy1 = int(y1 / scale) + fy
                    ox2 = int(x2 / scale) + fx
                    oy2 = int(y2 / scale) + fy
                    
                    counts[deg_type] += 1
                    all_degradations.append({
                        'type': deg_type,
                        'severity': DEGRADATION_TYPES[deg_type]['severity'],
                        'confidence': round(conf, 3),
                        'location': {
                            'x': ox1,
                            'y': oy1,
                            'width': ox2 - ox1,
                            'height': oy2 - oy1
                        },
                        'area': float((ox2 - ox1) * (oy2 - oy1)),
                        'source_image': image_name
                    })

        # Calcul expert du score de risque
        total_defauts = sum(counts.values())
        score_structurel = (counts['fissures'] * 15) + (counts['effritement'] * 12)
        score_chimique = (counts['humidite'] * 8)
        
        score_brut = (score_structurel + score_chimique) / len(images) if images else 0
        score_final = min(100, round(score_brut, 2))

        # Recommandations
        recommandations_list = []
        if counts['fissures'] > 0 or counts['effritement'] > 0:
            recommandations_list.append("Risque structurel détecté : Planifier une inspection des maçonneries.")
        if counts['humidite'] > 0:
            recommandations_list.append("Problème d'étanchéité : Traiter les infiltrations.")

        if score_final < 35:
            severity, status_update = 'faible', 'Sain'
            rec_text = "Entretien normal. " + " ".join(recommandations_list) if recommandations_list else "Aucune anomalie majeure."
        elif score_final <= 65:
            severity, status_update = 'moyenne', 'Attention'
            rec_text = "Surveillance recommandée. " + " ".join(recommandations_list)
        else:
            severity, status_update = 'critique', 'Danger'
            rec_text = "Alerte : Intervention urgente requise ! " + " ".join(recommandations_list)

        return jsonify({
            "degradations": all_degradations,
            "risk_score": score_final,
            "severity": severity,
            "status_update": status_update,
            "recommendations": rec_text
        })

    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"error": f"Erreur lors du traitement YOLO : {str(e)}"}), 500
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

# ==========================================
# ROUTE 2 : RECONSTRUCTION 3D (COLMAP GPU)
# ==========================================
@app.route('/api/process_colmap', methods=['POST'])
def process_colmap():
    if 'file' not in request.files:
        return jsonify({"error": "Aucun fichier envoye (champ 'file' requis)"}), 400
        
    file = request.files['file']
    if not file.filename.endswith('.zip'):
        return jsonify({"error": "Le fichier doit etre un ZIP d'images"}), 400

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, 'images.zip')
    file.save(zip_path)

    extract_dir = os.path.join(temp_dir, 'images')
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    # Déclaration des dossiers COLMAP
    db_path = os.path.join(temp_dir, 'database.db')
    sparse_path = os.path.join(temp_dir, 'sparse')
    dense_path = os.path.join(temp_dir, 'dense')
    os.makedirs(sparse_path, exist_ok=True)
    os.makedirs(dense_path, exist_ok=True)

    try:
        # 1. Feature Extraction (GPU)
        print("[*] COLMAP - SIFT Feature Extraction (GPU)...")
        subprocess.run([
            "colmap", "feature_extractor",
            "--database_path", db_path,
            "--image_path", extract_dir,
            "--ImageReader.single_camera", "1",
            "--SiftExtraction.use_gpu", "1"
        ], check=True)

        # 2. Matcher (GPU)
        print("[*] COLMAP - Feature Matching (GPU)...")
        subprocess.run([
            "colmap", "exhaustive_matcher",
            "--database_path", db_path,
            "--FeatureMatching.use_gpu", "1"
        ], check=True)

        # 3. Mapper (CPU)
        print("[*] COLMAP - Sparse Mapper...")
        subprocess.run([
            "colmap", "mapper",
            "--database_path", db_path,
            "--image_path", extract_dir,
            "--output_path", sparse_path
        ], check=True)

        model_dir = os.path.join(sparse_path, "0")
        if not os.path.exists(model_dir):
            if os.path.exists(os.path.join(sparse_path, "cameras.bin")):
                model_dir = sparse_path
            else:
                return jsonify({"error": "Le mapper COLMAP n'a généré aucun modèle 3D éparse."}), 500

        # 4. Undistorter (CPU)
        print("[*] COLMAP - Image Undistortion...")
        subprocess.run([
            "colmap", "image_undistorter",
            "--image_path", extract_dir,
            "--input_path", model_dir,
            "--output_path", dense_path,
            "--output_type", "COLMAP"
        ], check=True)

        # 5. Patch Match Stereo (GPU/CUDA - L'étape gourmande !)
        print("[*] COLMAP - Patch Match Stereo (GPU/CUDA)...")
        subprocess.run([
            "colmap", "patch_match_stereo",
            "--workspace_path", dense_path,
            "--PatchMatchStereo.geom_consistency", "0"
        ], check=True)

        # 6. Stereo Fusion
        print("[*] COLMAP - Stereo Fusion...")
        fused_ply = os.path.join(temp_dir, 'fused.ply')
        subprocess.run([
            "colmap", "stereo_fusion",
            "--workspace_path", dense_path,
            "--output_path", fused_ply
        ], check=True)

        # 7. Poisson Mesher
        print("[*] COLMAP - Poisson Mesher...")
        raw_ply = os.path.join(temp_dir, 'raw_model.ply')
        subprocess.run([
            "colmap", "poisson_mesher",
            "--input_path", fused_ply,
            "--output_path", raw_ply
        ], check=True)

        # 8. Conversion en GLB via Open3D / Trimesh avec nettoyage
        glb_output = os.path.join(temp_dir, 'model.glb')
        print("[*] Optimisation et exportation en GLB...")
        
        # Open3D pipeline pour nettoyer le modèle Poisson
        import trimesh
        try:
            import open3d as o3d
            pcd = o3d.io.read_point_cloud(raw_ply)
            
            # Filtre statistique des points aberrants
            pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=25, std_ratio=1.0)
            # Filtre par rayon
            pcd, _ = pcd.remove_radius_outlier(nb_points=15, radius=0.07)
            # Downsampling
            pcd = pcd.voxel_downsample(voxel_size=0.015)
            # Normales
            pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.12, max_nn=30))
            pcd.orient_normals_consistent_tangent_plane(k=120)
            
            # Poisson avec haute résolution (Depth 10)
            mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=10)
            
            # Filtrer agressivement la bulle Poisson (on élimine les 85% des sommets fantômes les moins denses)
            densities = np.asarray(densities)
            density_threshold = np.percentile(densities, 85)
            mesh.remove_vertices_by_mask(densities < density_threshold)
            
            # Lissage et décimation
            mesh = mesh.filter_smooth_taubin(number_of_iterations=5)
            target_triangles = int(len(mesh.triangles) * 0.6)
            if target_triangles > 0:
                mesh = mesh.simplify_quadric_error(target_number_of_triangles=target_triangles)
                
            mesh.compute_vertex_normals()
            o3d.io.write_triangle_mesh(glb_output, mesh)
            print("[*] Conversion Open3D reussie !")
        except Exception as o3d_err:
            print(f"[!] Erreur Open3D ({o3d_err}), fallback Trimesh standard...")
            tmesh = trimesh.load(raw_ply)
            tmesh.export(glb_output)

        if not os.path.exists(glb_output) or os.path.getsize(glb_output) < 500:
            return jsonify({"error": "La generation du fichier GLB a echoue."}), 500

        # Envoi du fichier généré
        return send_file(glb_output, as_attachment=True, download_name='model.glb')

    except Exception as e:
        print(f"[ERROR] Reconstruction COLMAP echouee : {e}")
        return jsonify({"error": f"Erreur de reconstruction COLMAP : {str(e)}"}), 500
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

# ==========================================
# DÉMARRAGE DU SERVEUR
# ==========================================
if __name__ == '__main__':
    # Initialisation de YOLOv8 au démarrage
    get_yolo_model()
    # Lancement sur 0.0.0.0:5000
    app.run(host='0.0.0.0', port=5000, debug=False)

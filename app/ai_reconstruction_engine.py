
import numpy as np
from PIL import Image
import tensorflow as tf
import trimesh
import os
import requests

MODEL_URL = "https://storage.googleapis.com/tfhub-lite-models/intel/lite-model/midas/v2_1_small/1/lite/1.tflite"
MODEL_PATH = "static/models/midas_small.tflite"

def download_model():
    if not os.path.exists(MODEL_PATH):
        print(f"Téléchargement du modèle IA MiDaS ({MODEL_URL})...")
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        r = requests.get(MODEL_URL, stream=True)
        with open(MODEL_PATH, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Modèle téléchargé avec succès.")

def ai_reconstruct(image_path, output_path):
    download_model()
    
    # Charger le modèle TFLite
    interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    
    # Préparer l'image
    img = Image.open(image_path).convert('RGB')
    input_size = input_details[0]['shape'][1:3]
    img_resized = img.resize(input_size)
    input_data = np.array(img_resized, dtype=np.float32) / 255.0
    input_data = np.expand_dims(input_data, axis=0)
    
    # Exécuter l'IA (Estimation de profondeur)
    interpreter.set_tensor(input_details[0]['index'], input_data)
    interpreter.invoke()
    depth_map = interpreter.get_tensor(output_details[0]['index'])[0]
    
    # Normaliser la profondeur
    depth_min = depth_map.min()
    depth_max = depth_map.max()
    depth_map = (depth_map - depth_min) / (depth_max - depth_min)
    
    # Créer le maillage 3D
    rows, cols = depth_map.shape
    vertices = []
    colors = []
    
    # Image originale pour les couleurs
    img_colors = np.array(img.resize((cols, rows)))
    
    for r in range(rows):
        for c in range(cols):
            z = depth_map[r, c] * 0.4  # Ajustement du relief
            vertices.append([c / cols, (rows - r) / rows, z])
            colors.append(img_colors[r, c])
            
    vertices = np.array(vertices)
    colors = np.array(colors) / 255.0
    
    # Création des faces
    faces = []
    for r in range(rows - 1):
        for c in range(cols - 1):
            i = r * cols + c
            faces.append([i, i + 1, i + cols])
            faces.append([i + 1, i + cols + 1, i + cols])
            
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, vertex_colors=colors)
    
    # Nettoyage et Export
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    mesh.export(output_path)
    return True

if __name__ == "__main__":
    # Test
    test_img = "static/uploads/default/test.jpg"
    if os.path.exists(test_img):
        ai_reconstruct(test_img, "static/models/test_ai_model.glb")
        print("Reconstruction IA terminée.")

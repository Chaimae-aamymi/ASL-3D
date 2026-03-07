from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from werkzeug.utils import secure_filename
import os
import numpy as np
from PIL import Image
import json
from datetime import datetime
from degradation_detector import DegradationDetector
from reconstruction_engine import ReconstructionEngine
import traceback

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'

# Créer les dossiers s'ils n'existent pas
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Initialiser les modules IA
detector = DegradationDetector()
reconstructor = ReconstructionEngine()

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'obj', 'ply', 'gltf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Page d'accueil"""
    return render_template('index.html')

@app.route('/scanner')
def scanner():
    """Page du scanner 3D"""
    return render_template('scanner.html')

@app.route('/reconstruction')
def reconstruction():
    """Page de reconstruction"""
    return render_template('reconstruction.html')

@app.route('/analysis')
def analysis():
    """Page d'analyse des dégradations"""
    return render_template('analysis.html')

@app.route('/restoration-guide')
def restoration_guide():
    """Guide de restauration"""
    return render_template('restoration_guide.html')

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Servir les fichiers uploadés"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/outputs/<path:filename>')
def output_file(filename):
    """Servir les fichiers générés"""
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload et traitement initial du fichier"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Aucun fichier fourni'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Aucun fichier sélectionné'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Type de fichier non supporté'}), 400
        
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_")
        filename = timestamp + filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'message': 'Fichier uploadé avec succès'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/detect-degradation/<filename>', methods=['POST'])
def detect_degradation(filename):
    """Détecter les dégradations dans l'image"""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Fichier non trouvé'}), 404
        
        # Charger l'image
        image = Image.open(filepath)
        image_array = np.array(image)
        
        # Détection des dégradations
        degradations = detector.detect(image_array)
        
        # Créer la visualisation
        visualization = detector.visualize(image_array, degradations)
        
        # Sauvegarder la visualisation
        output_filename = f"degradation_{filename}"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        Image.fromarray(visualization).save(output_path)
        
        return jsonify({
            'success': True,
            'degradations': degradations,
            'visualization': output_filename,
            'severity': detector.calculate_severity(degradations),
            'recommendations': detector.get_recommendations(degradations)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reconstruct-3d/<filename>', methods=['POST'])
def reconstruct_3d(filename):
    """Reconstruire le modèle 3D du bâtiment"""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Fichier non trouvé'}), 404
        
        data = request.get_json()
        reconstruction_params = data.get('params', {})
        
        # Effectuer la reconstruction
        model_data = reconstructor.reconstruct(filepath, reconstruction_params)
        
        # Sauvegarder le modèle
        model_filename = f"model_3d_{filename.rsplit('.', 1)[0]}.obj"
        model_path = os.path.join(app.config['OUTPUT_FOLDER'], model_filename)
        reconstructor.save_model(model_data, model_path)
        
        return jsonify({
            'success': True,
            'model': model_filename,
            'vertices': model_data['vertices'],
            'faces': model_data['faces'],
            'message': 'Reconstruction 3D complétée'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/restoration-plan/<filename>', methods=['POST'])
def get_restoration_plan(filename):
    """Générer un plan de restauration"""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Fichier non trouvé'}), 404
        
        data = request.get_json()
        degradations = data.get('degradations', [])
        
        # Générer le plan de restauration
        plan = reconstructor.generate_restoration_plan(degradations)
        
        # Sauvegarder le rapport
        report_filename = f"restoration_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path = os.path.join(app.config['OUTPUT_FOLDER'], report_filename)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'plan': plan,
            'report': report_filename
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    """Télécharger un fichier de résultat"""
    try:
        filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Fichier non trouvé'}), 404
        
        return send_file(filepath, as_attachment=True)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files', methods=['GET'])
def list_files():
    """Lister les fichiers uploadés ou générés"""
    try:
        folder_type = request.args.get('type', 'uploads')
        folder = app.config['OUTPUT_FOLDER'] if folder_type == 'outputs' else app.config['UPLOAD_FOLDER']
        
        if not os.path.exists(folder):
            return jsonify({'files': []})
            
        files = os.listdir(folder)
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'Fichier trop volumineux'}), 413

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Erreur serveur interne'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)

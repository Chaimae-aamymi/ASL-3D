import numpy as np
from PIL import Image
import json
from datetime import datetime

class ReconstructionEngine:
    """Moteur de reconstruction 3D des bâtiments"""
    
    def __init__(self):
        self.restoration_techniques = {
            'fissures': {
                'steps': [
                    'Nettoyage des fissures avec air comprimé',
                    'Application de primer/scellant',
                    'Remplissage avec mortier spécialisé',
                    'Lissage et finition',
                    'Application de vernis protecteur'
                ],
                'duration': '3-5 jours',
                'cost_factor': 2.0
            },
            'humidite': {
                'steps': [
                    'Évaluation de la source d\'humidité',
                    'Installation de système de drainage',
                    'Application de membrane imperméabilisante',
                    'Installation de ventilation',
                    'Traitement des zones affectées'
                ],
                'duration': '1-2 semaines',
                'cost_factor': 3.5
            },
            'erosion': {
                'steps': [
                    'Évaluation de la profondeur d\'érosion',
                    'Nettoyage de la surface',
                    'Application de consolidant',
                    'Retraitement de surface',
                    'Application de revêtement protecteur'
                ],
                'duration': '4-7 jours',
                'cost_factor': 2.5
            },
            'champignons': {
                'steps': [
                    'Isolement de la zone infectée',
                    'Nettoyage biocide professionnel',
                    'Traitement anti-fongique',
                    'Amélioration de la ventilation',
                    'Suivi et prévention'
                ],
                'duration': '2-3 semaines',
                'cost_factor': 3.0
            },
            'decoloration': {
                'steps': [
                    'Nettoyage doux avec eau et savon',
                    'Gommage léger si nécessaire',
                    'Rinçage à l\'eau déminéralisée',
                    'Séchage complet',
                    'Application de vernis protecteur'
                ],
                'duration': '1-2 jours',
                'cost_factor': 1.0
            },
            'effritement': {
                'steps': [
                    'Retrait des matériaux instables',
                    'Nettoyage de la surface',
                    'Application de consolidant',
                    'Remplissage des zones creuses',
                    'Finition et protection'
                ],
                'duration': '3-5 jours',
                'cost_factor': 2.5
            }
        }
    
    def reconstruct(self, image_path, params=None):
        """Reconstruire le modèle 3D basé sur l'image"""
        if params is None:
            params = {}
        
        # Charger l'image
        image = Image.open(image_path)
        image_array = np.array(image)
        
        # Convertir en niveaux de gris pour l'analyse de profondeur
        if len(image_array.shape) == 3:
            gray = np.dot(image_array[..., :3], [0.299, 0.587, 0.114])
        else:
            gray = image_array
        
        # Normaliser
        gray = (gray - gray.min()) / (gray.max() - gray.min()) * 255
        
        # Générer une carte de profondeur
        depth_map = self._generate_depth_map(gray, params)
        
        # Créer un maillage 3D
        vertices, faces = self._create_mesh(gray, depth_map, params)
        
        return {
            'vertices': vertices,
            'faces': faces,
            'depth_map': depth_map,
            'image_shape': image_array.shape
        }
    
    def _generate_depth_map(self, gray_image, params):
        """Générer une carte de profondeur à partir de l'image"""
        height, width = gray_image.shape
        
        # Créer une carte de profondeur basique
        depth_map = np.zeros((height, width))
        
        # Utiliser la luminosité comme indicateur de profondeur
        depth_map = (gray_image / 255.0) * 100
        
        # Appliquer un lissage gaussien
        from scipy.ndimage import gaussian_filter
        depth_map = gaussian_filter(depth_map, sigma=params.get('smoothness', 2))
        
        return depth_map
    
    def _create_mesh(self, gray_image, depth_map, params):
        """Créer un maillage 3D à partir de la carte de profondeur"""
        height, width = gray_image.shape
        scale = params.get('scale', 1.0)
        
        # Créer les vertices
        vertices = []
        for y in range(height):
            for x in range(width):
                vertices.append([
                    x * scale,
                    y * scale,
                    depth_map[y, x] * scale
                ])
        
        # Créer les faces (triangles)
        faces = []
        for y in range(height - 1):
            for x in range(width - 1):
                # Index des 4 coins du quad
                tl = y * width + x
                tr = y * width + (x + 1)
                bl = (y + 1) * width + x
                br = (y + 1) * width + (x + 1)
                
                # Créer deux triangles
                faces.append([tl, tr, bl])
                faces.append([tr, br, bl])
        
        return np.array(vertices), np.array(faces)
    
    def save_model(self, model_data, output_path):
        """Sauvegarder le modèle 3D en format OBJ"""
        vertices = model_data['vertices']
        faces = model_data['faces']
        
        with open(output_path, 'w') as f:
            f.write("# 3D Model - Building Reconstruction\n")
            f.write(f"# Generated on {datetime.now().isoformat()}\n\n")
            
            # Écrire les vertices
            for vertex in vertices:
                f.write(f"v {vertex[0]:.6f} {vertex[1]:.6f} {vertex[2]:.6f}\n")
            
            f.write("\n")
            
            # Écrire les faces
            for face in faces:
                f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")
    
    def generate_restoration_plan(self, degradations):
        """Générer un plan détaillé de restauration"""
        plan = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_issues': len(degradations),
                'degradation_types': list(set([d['type'] for d in degradations])),
                'estimated_duration': self._estimate_duration(degradations),
                'estimated_cost_factor': self._estimate_cost(degradations)
            },
            'phases': [],
            'recommendations': [],
            'timeline': [],
            'safety_measures': self._get_safety_measures(),
            'monitoring_plan': self._get_monitoring_plan()
        }
        
        # Grouper par type de dégradation
        degradation_groups = {}
        for d in degradations:
            deg_type = d['type']
            if deg_type not in degradation_groups:
                degradation_groups[deg_type] = []
            degradation_groups[deg_type].append(d)
        
        # Créer les phases
        priority_order = ['champignons', 'humidite', 'fissures', 'erosion', 'effritement', 'decoloration']
        
        phase_num = 1
        for deg_type in priority_order:
            if deg_type in degradation_groups:
                issues = degradation_groups[deg_type]
                technique = self.restoration_techniques.get(deg_type, {})
                
                plan['phases'].append({
                    'phase': phase_num,
                    'type': deg_type,
                    'affected_areas': len(issues),
                    'steps': technique.get('steps', []),
                    'duration': technique.get('duration', 'À évaluer'),
                    'cost_multiplier': technique.get('cost_factor', 1.0),
                    'precautions': self._get_precautions(deg_type),
                    'expected_outcome': self._get_expected_outcome(deg_type)
                })
                
                phase_num += 1
        
        # Ajouter les recommandations
        for deg_type in degradation_groups:
            plan['recommendations'].append({
                'type': deg_type,
                'count': len(degradation_groups[deg_type]),
                'action': self._get_recommendation(deg_type)
            })
        
        # Créer un timeline
        plan['timeline'] = self._create_timeline(plan['phases'])
        
        return plan
    
    def _estimate_duration(self, degradations):
        """Estimer la durée totale de restauration"""
        durations = {
            'champignons': 14,
            'humidite': 10,
            'fissures': 4,
            'erosion': 5,
            'effritement': 4,
            'decoloration': 1
        }
        
        total_days = 0
        for d in degradations:
            deg_type = d['type']
            if deg_type in durations:
                total_days = max(total_days, durations[deg_type])
        
        return f"{total_days}-{total_days+5} jours"
    
    def _estimate_cost(self, degradations):
        """Estimer le facteur de coût"""
        total_factor = sum([
            self.restoration_techniques.get(d['type'], {}).get('cost_factor', 1.0)
            for d in degradations
        ])
        
        return round(total_factor / len(degradations), 2) if degradations else 1.0
    
    def _get_safety_measures(self):
        """Obtenir les mesures de sécurité"""
        return [
            'Inspection de stabilité structurelle avant travaux',
            'Installation d\'échafaudage sécurisé',
            'Équipement de protection individuelle obligatoire',
            'Ventilation adéquate pendant les traitements chimiques',
            'Évaluation asbestos avant modification',
            'Mise en place de barrières de sécurité'
        ]
    
    def _get_monitoring_plan(self):
        """Obtenir le plan de suivi post-restauration"""
        return {
            'frequency': 'Inspections trimestrielles pendant 2 ans',
            'checklist': [
                'Intégrité des scellants',
                'Absence de nouvelles fissures',
                'Contrôle d\'humidité',
                'État du revêtement protecteur',
                'Efficacité de la ventilation'
            ],
            'maintenance': 'Nettoyage annuel et retraitement tous les 5 ans'
        }
    
    def _get_precautions(self, degradation_type):
        """Obtenir les précautions pour un type de dégradation"""
        precautions = {
            'champignons': ['Masques respiratoires', 'Isolation des zones', 'Ventilation forcée'],
            'humidite': ['Évaluation électrique', 'Gants étanches', 'Dés-humidification'],
            'fissures': ['Évaluation structurelle', 'Étaiement si nécessaire'],
            'erosion': ['Protection anti-poussière', 'Contrôle des débris'],
            'effritement': ['Récupération des débris', 'Protection du sol'],
            'decoloration': ['Nettoyage délicat', 'Ventilation']
        }
        
        return precautions.get(degradation_type, [])
    
    def _get_expected_outcome(self, degradation_type):
        """Obtenir le résultat attendu"""
        outcomes = {
            'champignons': 'Élimination complète, surface saine, prévention de réinfection',
            'humidite': 'Régulation d\'humidité normale, prévention de dégâts futurs',
            'fissures': 'Fissures colmatées, structure stabilisée',
            'erosion': 'Surface restaurée, protection à long terme',
            'effritement': 'Matériau consolidé, structure intacte',
            'decoloration': 'Couleur uniforme restaurée, surface protégée'
        }
        
        return outcomes.get(degradation_type, 'Amélioration significative attendue')
    
    def _get_recommendation(self, degradation_type):
        """Obtenir la recommandation"""
        recommendations = {
            'champignons': 'Traitement prioritaire immédiat pour éviter propagation',
            'humidite': 'Diagnostic complet de source recommandé',
            'fissures': 'Évaluation structurelle avant intervention',
            'erosion': 'Protection supplémentaire recommandée',
            'effritement': 'Intervention rapide pour prévention',
            'decoloration': 'Traitement cosmétique avec protection'
        }
        
        return recommendations.get(degradation_type, 'Intervention recommandée')
    
    def _create_timeline(self, phases):
        """Créer un timeline des travaux"""
        timeline = []
        cumulative_days = 0
        
        for i, phase in enumerate(phases, 1):
            # Extraire le nombre de jours de la durée
            duration_str = phase['duration']
            try:
                days = int(duration_str.split('-')[0])
            except:
                days = 5
            
            timeline.append({
                'week': (cumulative_days // 7) + 1,
                'phase': i,
                'type': phase['type'],
                'start_day': cumulative_days + 1,
                'end_day': cumulative_days + days,
                'duration_days': days
            })
            
            cumulative_days += days
        
        return timeline

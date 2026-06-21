import math
from datetime import datetime

class ReconstructionEngine:
    """Minimal replacement for the original ReconstructionEngine.
    Provides only the small set of methods used elsewhere in the app:
    - generate_restoration_plan
    - analyze_project_impact
    - calculate_vibration_impact
    """

    def generate_restoration_plan(self, degradations):
        degradations = degradations or []
        total = len(degradations)
        types = list({d.get('type') for d in degradations if d.get('type')})
        
        # 1. Scaler logarithmique basé sur la quantité de dégradations
        # Évite l'explosion linéaire (ex: 1500 dégradations = 3000 jours)
        scale_factor = 1.0 + min(1.5, math.log1p(total) * 0.15)
        
        # 2. Définition des phases de base (durée en jours)
        phases_definitions = []
        
        # Phase 1: Diagnostic et Préparation (Toujours présente)
        phases_definitions.append({
            'type': 'Diagnostic & Préparation de Surface',
            'base_min': 2,
            'base_max': 3,
            'affected_areas': 'Ensemble des façades et zones diagnostiquées',
            'steps': [
                'Inspection visuelle détaillée de toutes les zones signalées par l\'IA.',
                'Nettoyage doux à basse pression pour éliminer les poussières et résidus de surface.',
                'Pose de témoins physiques (fissurimètres) sur les désordres structurels majeurs.'
            ],
            'precautions': [
                'Proscrire les jets haute pression (> 50 bars) sur les pierres historiques fragilisées.',
                'Port d\'Équipements de Protection Individuelle (EPI) complets.'
            ],
            'expected_outcome': 'Surfaces saines, propres et prêtes pour les interventions spécialisées.'
        })
        
        # Phase 2: Traitement Biocide & Nettoyage (Si champignons ou decoloration)
        if 'champignons' in types or 'decoloration' in types:
            phases_definitions.append({
                'type': 'Traitement Biocide & Nettoyage Chimique',
                'base_min': 3,
                'base_max': 5,
                'affected_areas': 'Zones contaminées par les micro-organismes',
                'steps': [
                    'Application d\'un produit biocide biodégradable et fongicide adapté.',
                    'Brossage manuel délicat (brosses nylon/soie, interdiction de brosses métalliques).',
                    'Rinçage à l\'eau claire avec contrôle strict du pH résiduel.'
                ],
                'precautions': [
                    'Protéger les menuiseries et éléments décoratifs adjacents.',
                    'Confinement des eaux de lavage pour éviter la pollution du sol.'
                ],
                'expected_outcome': 'Éradication des lichens/mousses et arrêt des dégradations d\'origine biologique.'
            })
            
        # Phase 3: Traitement de l\'Humidité & Assainissement (Si humidite)
        if 'humidite' in types or 'humidite' in [t.lower() for t in types]:
            phases_definitions.append({
                'type': 'Assainissement & Traitement de l\'Humidité',
                'base_min': 5,
                'base_max': 8,
                'affected_areas': 'Zones à forte humidité ou sujettes aux remontées capillaires',
                'steps': [
                    'Création d\'une barrière étanche par injection de résine hydrophobe en bas de mur.',
                    'Piquage des enduits dégradés saturés en sels minéraux.',
                    'Application d\'un enduit d\'assainissement hautement perméable à la vapeur.'
                ],
                'precautions': [
                    'Laisser sécher naturellement les maçonneries après injection.',
                    'Ne pas utiliser de revêtements étanches qui bloqueraient l\'humidité à l\'intérieur.'
                ],
                'expected_outcome': 'Arrêt définitif des remontées capillaires et assainissement durable des murs.'
            })

        # Phase 4: Consolidation & Rejointoiement (Si erosion ou effritement)
        if 'erosion' in types or 'effritement' in types:
            phases_definitions.append({
                'type': 'Consolidation & Rejointoiement des Maçonneries',
                'base_min': 6,
                'base_max': 10,
                'affected_areas': 'Zones érodées et joints pulvérulents',
                'steps': [
                    'Dégarnissage manuel des joints dégradés sur une profondeur de 2 cm.',
                    'Application d\'un consolidant de pierre à base de silicate d\'éthyle.',
                    'Rejointoiement au mortier de chaux naturelle (NHL 2 ou NHL 3.5) teinté à l\'identique.'
                ],
                'precautions': [
                    'Interdiction d\'utiliser du ciment Portland (incompatible avec le bâti ancien).',
                    'Maintenir le mortier de chaux humide pendant sa prise.'
                ],
                'expected_outcome': 'Cohésion de la pierre restaurée et imperméabilité à l\'eau des joints rétablie.'
            })

        # Phase 5: Injection & Traitement des Fissures (Si fissures)
        if 'fissures' in types:
            phases_definitions.append({
                'type': 'Traitement & Injection des Fissures',
                'base_min': 5,
                'base_max': 7,
                'affected_areas': 'Fissures et microfissures structurelles',
                'steps': [
                    'Purge des lèvres de la fissure et pose d\'injecteurs tous les 15-20 cm.',
                    'Injection sous basse pression de coulis de chaux fine ou résine fluide.',
                    'Rebouchage de surface avec un mortier de restauration minéral adapté.'
                ],
                'precautions': [
                    'Surveiller la pression d\'injection pour éviter l\'éclatement des parements.',
                    'S\'assurer de la stabilisation préalable du monument.'
                ],
                'expected_outcome': 'Rétablissement du monolithisme de la structure et scellement étanche.'
            })

        # Phase Finale: Finitions & Protection (Toujours présente)
        phases_definitions.append({
            'type': 'Finitions & Protection Hydrofuge',
            'base_min': 2,
            'base_max': 3,
            'affected_areas': 'Ensemble des surfaces restaurées',
            'steps': [
                'Harmonisation esthétique locale (patine réversible ou badigeon de chaux très fluide).',
                'Application d\'un traitement hydrofuge de surface minéral incolore et respirant.',
                'Repli de chantier, dépose des échafaudages et nettoyage final des abords.'
            ],
            'precautions': [
                'Vérifier que le produit hydrofuge est perméable à la vapeur d\'eau (non filmogène).',
                'Faire des essais de teinte préalables sur des parties discrètes.'
            ],
            'expected_outcome': 'Rendu esthétique harmonieux préservant l\'aspect historique et protection durable.'
        })

        # 3. Calcul des durées mises à l'échelle et constitution des phases
        phases = []
        duration_min = 0
        duration_max = 0
        
        for idx, defn in enumerate(phases_definitions):
            scaled_min = int(defn['base_min'] * scale_factor)
            scaled_max = int(defn['base_max'] * scale_factor)
            duration_min += scaled_min
            duration_max += scaled_max
            
            phases.append({
                'phase': str(idx + 1),
                'type': defn['type'],
                'duration': f"{scaled_min}-{scaled_max} jours",
                'affected_areas': defn['affected_areas'],
                'steps': defn['steps'],
                'precautions': defn['precautions'],
                'expected_outcome': defn['expected_outcome']
            })

        # 4. Mesures de sécurité génériques
        safety_measures = [
            'Installation d\'un échafaudage de service conforme, ancré sans altérer les pierres d\'époque.',
            'Port obligatoire des EPI (casque, lunettes, masque anti-poussière, harnais si travail en hauteur).',
            'Balise de sécurité et signalétique pour le public aux abords immédiats du chantier.',
            'Stockage sécurisé et ventilé des produits chimiques et solvants de traitement.'
        ]

        # 5. Plan de surveillance post-restauration
        monitoring_plan = {
            'frequency': 'Visite de contrôle trimestrielle la première année, puis annuelle.',
            'maintenance': 'Nettoyage annuel des systèmes d\'évacuation des eaux pluviales et retraits de végétation.',
            'checklist': [
                'Lecture des jauges sur les fissures-témoins pour s\'assurer de l\'absence de mouvement.',
                'Mesure d\'humidité résiduelle par humidimètre de contact.',
                'Contrôle visuel de la tenue des nouveaux joints et de l\'état de surface de la pierre.',
                'Vérification de l\'absence de nouvelles efflorescences ou de proliférations biologiques.'
            ]
        }

        plan = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_issues': total,
                'degradation_types': types,
                'estimated_duration': f"{duration_min}-{duration_max} jours",
                'estimated_cost_factor': round(1.0 + min(2.5, math.log1p(total) * 0.20), 2)
            },
            'phases': phases,
            'safety_measures': safety_measures,
            'monitoring_plan': monitoring_plan
        }
        return plan


    def analyze_project_impact(self, degradations, project_name, project_desc):
        """Returns a basic impact dict when no infrastructure project is specified."""
        if not project_name:
            return None  # No impact data to show in PDF if no project given
        return {
            'project':            project_name or 'N/A',
            'description':        project_desc or '',
            'risk_level':         'MODÉRÉ',
            'risk_color':         (217, 119, 6),   # orange — moderate
            'main_concerns':      [
                'Vibrations potentielles liées aux travaux à proximité.',
                'Surveiller l\'intégrité des maçonneries pendant la phase de travaux.'
            ],
            'engineering_advice': [
                'Réaliser une campagne de mesure vibratoire (capteurs accéléromètre) avant le démarrage.',
                'Installer un suivi fissurimétrique mensuel sur les zones fragiles identifiées.'
            ]
        }

    def calculate_vibration_impact(self, distance_m, project_type, intensity='medium', degradations=None):
        k_values = {'tramway': 0.03, 'route': 0.02, 'tunnel': 0.05, 'chantier': 0.025}
        v_source_map = {'low': 5.0, 'medium': 15.0, 'high': 30.0}
        k = k_values.get(project_type, 0.025)
        v_source = v_source_map.get(intensity, 15.0)
        distance_m = max(float(distance_m), 1.0)
        
        # Check for severe structural degradations
        has_severe_cracks = False
        if degradations:
            has_severe_cracks = any(
                d.get('type') == 'fissures' and d.get('severity') in ('haute', 'critique')
                for d in degradations
            )
            
        # Boost risk label if distance is short and monument is fragile
        v_impact = v_source * math.exp(-k * distance_m)
        severity_boost = False
        if has_severe_cracks and distance_m < 50.0:
            severity_boost = True
            risk_label = 'CRITIQUE'
        else:
            if v_impact >= 10.0:
                risk_label = 'CRITIQUE'
            elif v_impact >= 3.0:
                risk_label = 'ELEVE'
            elif v_impact >= 0.5:
                risk_label = 'MODERE'
            else:
                risk_label = 'FAIBLE'

        # Mitigated Impact Calculation (Engineering Solutions)
        v_mitigated = v_impact * 0.40
        if v_mitigated >= 10.0:
            mitigated_label = 'CRITIQUE'
        elif v_mitigated >= 3.0:
            mitigated_label = 'ELEVE'
        elif v_mitigated >= 0.5:
            mitigated_label = 'MODERE'
        else:
            mitigated_label = 'FAIBLE'
            
        solutions = [
            {
                'name': 'Écrans anti-vibratoires (Tranchées actives)',
                'desc': 'Creusement d\'une tranchée étroite remplie de bentonite ou de matériau amortisseur le long du tracé pour diffracter et absorber les ondes.',
                'reduction': 0.60
            },
            {
                'name': 'Dalles flottantes amortissantes',
                'desc': 'Pose de la voie ferrée ou de la chaussée sur une dalle en béton isolée du sol par des plots en élastomère de haute résilience.',
                'reduction': 0.75
            }
        ]
        
        recs = [
            f"Vibrations de la source estimées à {v_source} mm/s.",
            f"Coefficient d'amortissement géologique (k) : {k}.",
            f"Risque structurel global : {risk_label}."
        ]
        
        return {
            'v_source': v_source,
            'k': k,
            'distance_m': distance_m,
            'v_impact': round(v_impact, 4),
            'risk_label': risk_label,
            'risk_color': (220,38,38) if risk_label=='CRITIQUE' else (217,119,6),
            'severity_boost': severity_boost,
            'recommendations': recs,
            'v_mitigated': round(v_mitigated, 4),
            'mitigated_label': mitigated_label,
            'solutions': solutions
        }

    def calculate_smart_deviation(self, distance_m, project_type, intensity='medium', degradations=None):
        base_impact = self.calculate_vibration_impact(distance_m, project_type, intensity, degradations)
        has_severe_cracks = False
        if degradations:
            has_severe_cracks = any(
                d.get('type') == 'fissures' and d.get('severity') in ('haute', 'critique')
                for d in degradations
            )
            
        safety_buffer = 50.0 if has_severe_cracks else 30.0
        needs_deviation = distance_m < safety_buffer
        
        if needs_deviation:
            corrected_distance = safety_buffer + 15.0
            mitigated_data = self.calculate_vibration_impact(corrected_distance, project_type, intensity, degradations)
            
            # detour geometry calculation
            arc_length = math.pi * safety_buffer / 2.0
            straight_line = safety_buffer * math.sqrt(2)
            detour_overhead_m = round(arc_length - straight_line + 15.0, 2)
            cost_increase_pct = round((detour_overhead_m / distance_m) * 15.0, 1)
            
            recs = [
                f"Déviation automatique IA appliquée : Tracé déplacé de {distance_m:.1f}m à {corrected_distance:.1f}m pour contourner la zone de risque.",
                f"Réduction majeure de l'impact vibratoire de {base_impact['v_impact']:.2f} mm/s à {mitigated_data['v_impact']:.2f} mm/s.",
                f"Évitement réussi des vibrations de haute intensité sur les structures fragilisées."
            ]
        else:
            corrected_distance = distance_m
            mitigated_data = base_impact
            detour_overhead_m = 0.0
            cost_increase_pct = 0.0
            recs = ["Aucune déviation requise. Le tracé respecte le périmètre de sécurité réglementaire."]
            
        return {
            'needs_deviation': needs_deviation,
            'original_distance': distance_m,
            'corrected_distance': corrected_distance,
            'original_v_impact': base_impact['v_impact'],
            'corrected_v_impact': mitigated_data['v_impact'],
            'original_risk': base_impact['risk_label'],
            'corrected_risk': mitigated_data['risk_label'],
            'detour_overhead_m': detour_overhead_m,
            'cost_increase_pct': cost_increase_pct,
            'recommendations': recs,
            'safety_buffer': safety_buffer
        }


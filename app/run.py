#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de démarrage pour ASL-3D
Utilisation: python run.py
"""

import os
import sys
from app import app, db
from models import TaskStatus

# Supprimer les messages de TensorFlow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

if __name__ == '__main__':
    # Créer les dossiers nécessaires
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('outputs', exist_ok=True)

    # Nettoyage automatique : marquer les tâches "running" comme échouées
    # (elles sont orphelines si le serveur a été redémarré)
    with app.app_context():
        stale = TaskStatus.query.filter_by(status='running').all()
        for t in stale:
            t.status = 'failed'
            t.message = 'Tâche interrompue (redémarrage du serveur). Veuillez relancer.'
        if stale:
            db.session.commit()
            print(f"    [!] {len(stale)} tâche(s) orpheline(s) nettoyée(s).")
    
    print("""
    =============================================================
    |                                                           |
    |               ASL-3D - Demarrage...                       |
    |                                                           |
    |     Restauration Numerique Intelligente de Batiments      |
    |                Historiques avec l'IA                      |
    |                                                           |
    |              Creee avec passion par AAMYMI Chaimae        |
    |                                                           |
    =============================================================
    
    [+] Ouvrez votre navigateur et allez a:
    
       http://127.0.0.1:5000
    
    [*] Fonctionnalites:
       - Scanner 3D Intelligent
       - Detection IA des Degradations
       - Reconstruction 3D
       - Plan de Restauration
    
    Appuyez sur Ctrl+C pour arreter le serveur.
    """)
    
    # Lancer l'application
    # IMPORTANT: use_reloader=False pour ne pas tuer les threads d'analyse IA
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_RUN_PORT', '5000'))
    app.run(debug=True, host=host, port=port, use_reloader=False)

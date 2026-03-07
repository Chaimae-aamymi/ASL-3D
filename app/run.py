#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de démarrage pour ASL-3D
Utilisation: python run.py
"""

import os
import sys
from app import app

# Supprimer les messages de TensorFlow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

if __name__ == '__main__':
    # Créer les dossiers nécessaires
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('outputs', exist_ok=True)
    
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║          🏛️  ASL-3D - Démarrage...                 ║
    ║                                                           ║
    ║     Restauration Numérique Intelligente de Bâtiments      ║
    ║                Historiques avec l'IA                      ║
    ║                                                           ║
    ║              Créée avec ❤️ par AAMYMI Chaimae           ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    
    📱 Ouvrez votre navigateur et allez à:
    
       http://127.0.0.1:5000
    
    ✨ Fonctionnalités:
       • Scanner 3D Intelligent
       • Détection IA des Dégradations
       • Reconstruction 3D
       • Plan de Restauration
    
    Appuyez sur Ctrl+C pour arrêter le serveur.
    """)
    
    # Lancer l'application
    app.run(debug=True, host='127.0.0.1', port=5000)

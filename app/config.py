#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Configuration Application ASL-3D
"""

import os

class Config:
    """Configuration de base"""
    # Flask
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'heritage-3d-secret-key-2026')
    
    # Upload
    UPLOAD_FOLDER = 'uploads'
    OUTPUT_FOLDER = 'outputs'
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    
    # Fichiers autorisés
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'obj', 'ply', 'gltf'}
    
    # Détection
    MIN_DEGRADATION_AREA = 50  # Pixels carrés
    CONFIDENCE_THRESHOLD = 0.6
    
    # Reconstruction
    DEFAULT_SCALE = 1.0
    DEFAULT_SMOOTHNESS = 2.0
    DEFAULT_QUALITY = 'medium'

class DevelopmentConfig(Config):
    """Configuration Développement"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Configuration Production"""
    DEBUG = False
    TESTING = False

class TestingConfig(Config):
    """Configuration Tests"""
    DEBUG = True
    TESTING = True
    UPLOAD_FOLDER = 'test_uploads'
    OUTPUT_FOLDER = 'test_outputs'

# Configuration active
config = DevelopmentConfig()

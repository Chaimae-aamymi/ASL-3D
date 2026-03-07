# ============================================================================
# ASL-3D v2.0 - Script de démarrage PowerShell
# ============================================================================

Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║           🏛️  ASL-3D v2.0 - DÉMARRAGE                        ║" -ForegroundColor Cyan
Write-Host "║        'AI-Powered Heritage Building Restoration'              ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Activer l'environnement virtuel
Write-Host "📦 Activation de l'environnement virtuel..." -ForegroundColor Yellow
& .\venv_asl3d\Scripts\Activate.ps1

Write-Host ""
Write-Host "✓ Environnement activé!" -ForegroundColor Green
Write-Host ""

# Vérifier les installations
Write-Host "🔍 Vérification des dépendances..." -ForegroundColor Yellow
python -c "
import sys
import flask
import numpy
import keras
import tensorflow
import cv2
import scipy
import PIL

print('✓ Flask:', flask.__version__)
print('✓ NumPy:', numpy.__version__)
print('✓ Keras:', keras.__version__)
print('✓ TensorFlow:', tensorflow.__version__)
print('✓ OpenCV-contrib:', cv2.__version__)
print('✓ SciPy:', scipy.__version__)
print('✓ Pillow:', PIL.__version__)
"

Write-Host ""
Write-Host "🚀 Démarrage ASL-3D..." -ForegroundColor Cyan
Write-Host "📍 Accédez à: http://127.0.0.1:5000" -ForegroundColor Green
Write-Host ""

# Démarrer l'application
python run.py

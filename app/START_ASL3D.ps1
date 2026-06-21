# ============================================================================
# ASL-3D v2.0 - Script de demarrage PowerShell
# ============================================================================

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "            ASL-3D v2.0 - DEMARRAGE" -ForegroundColor Cyan
Write-Host "        'AI-Powered Heritage Building Restoration'" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# Activer l'environnement virtuel
Write-Host "Activation de l'environnement virtuel..." -ForegroundColor Yellow
& .\venv_asl3d\Scripts\Activate.ps1

Write-Host ""
Write-Host "Environnement active!" -ForegroundColor Green
Write-Host ""

# Verifier les installations
Write-Host "Verification des dependances..." -ForegroundColor Yellow
python -c "
def check_lib(name):
    try:
        mod = __import__(name)
        if name == 'cv2':
            print('+ cv2:', mod.__version__)
        elif name == 'PIL':
            from PIL import Image
            print('+ Pillow:', Image.__version__)
        else:
            ver = getattr(mod, '__version__', 'Installed')
            print('+', name + ':', ver)
    except ImportError:
        print('-', name + ':', 'Not Installed')

libs = ['flask', 'numpy', 'keras', 'tensorflow', 'cv2', 'scipy', 'PIL']
for lib in libs:
    check_lib(lib)
"

Write-Host ""
Write-Host "Demarrage ASL-3D..." -ForegroundColor Cyan
Write-Host "Accedez a: http://127.0.0.1:5000" -ForegroundColor Green
Write-Host ""

# Demarrer l'application
python run.py

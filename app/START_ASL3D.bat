@echo off
REM Démarrage ASL-3D avec l'environnement virtuel

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║           🏛️  ASL-3D v2.0 - DÉMARRAGE                        ║
echo ║        "AI-Powered Heritage Building Restoration"              ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

REM Activer l'environnement virtuel
call venv_asl3d\Scripts\activate.bat

REM Vérifier Python
echo ✓ Python activé:
python --version
echo.

REM Démarrer l'application
echo 🚀 Démarrage ASL-3D...
echo.
python run.py

pause

import os
import sys
from sqlalchemy import text

sys.path.append(r'c:\Users\HP\pfe\app')

from app import app
from models import db

with app.app_context():
    try:
        db.session.execute(text('ALTER TABLE task_status ADD COLUMN progress INTEGER DEFAULT 0;'))
        db.session.commit()
        print("Colonne progress ajoutee avec succes!")
    except Exception as e:
        print(f"Erreur ou colonne deja existante: {e}")

import os
import sys
from sqlalchemy import text

# Append current dir to sys.path
sys.path.append(r'c:\Users\HP\pfe\app')

from app import app
from models import db

with app.app_context():
    try:
        db.session.execute(text('ALTER TABLE projects ADD COLUMN latitude DOUBLE PRECISION;'))
        db.session.execute(text('ALTER TABLE projects ADD COLUMN longitude DOUBLE PRECISION;'))
        db.session.commit()
        print("Colonnes latitude et longitude ajoutees avec succes!")
    except Exception as e:
        print(f"Erreur ou colonnes deja existantes: {e}")

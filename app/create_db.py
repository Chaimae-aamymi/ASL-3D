"""
create_db.py — Cree la base de donnees asl3d_db et ses tables pour PostgreSQL
Utilisation : python create_db.py
"""
import os
import sys

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("[-] psycopg2 non installe. Executez : pip install psycopg2-binary")
    sys.exit(1)

# Import app to use SQLAlchemy for table creation
sys.path.insert(0, os.path.dirname(__file__))
from app import app
from models import db

HOST     = 'localhost'
USER     = 'postgres'
PASSWORD = 'admin'
DB_NAME  = 'asl3d_db'

print(f"[+] Connexion a PostgreSQL ({HOST}) en tant que {USER}...")

try:
    # Connect to the default 'postgres' database to create the new one
    conn = psycopg2.connect(host=HOST, user=USER, password=PASSWORD, dbname='postgres')
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
except Exception as e:
    print(f"[-] Impossible de se connecter a PostgreSQL : {e}")
    print("   -> Assurez-vous que PostgreSQL est en cours d'execution.")
    sys.exit(1)

print(f"[+] Connecte. Verification de la base '{DB_NAME}'...")

try:
    cursor.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{DB_NAME}'")
    exists = cursor.fetchone()
    if not exists:
        cursor.execute(f"CREATE DATABASE {DB_NAME}")
        print(f"[+] Base '{DB_NAME}' creee.")
    else:
        print(f"[+] Base '{DB_NAME}' existe deja.")
except Exception as e:
    print(f"[-] Erreur lors de la creation de la base : {e}")
    sys.exit(1)
finally:
    cursor.close()
    conn.close()

# Creation des tables via SQLAlchemy
print(f"[*] Creation des tables via SQLAlchemy...")
try:
    with app.app_context():
        db.create_all()
        # Create test admin user if not exists
        from models import User
        if not User.query.filter_by(email='admin@asl3d.com').first():
            from werkzeug.security import generate_password_hash
            admin = User(
                name='Admin ASL3D',
                email='admin@asl3d.com',
                password_hash=generate_password_hash('admin123'),
                role='admin',
                oauth_provider='local'
            )
            db.session.add(admin)
            db.session.commit()
            print("[+] Utilisateur admin cree (admin@asl3d.com / admin123)")
    print("[+] Schema cree avec succes !")
except Exception as e:
    print(f"[-] Erreur lors de la creation des tables : {e}")
    sys.exit(1)

print("""
=================================================
  [+] Base de donnees PostgreSQL ASL-3D prete !  
                                                
  Maintenant :                                  
  1. Demarrez le serveur Flask                  
     -> python run.py                           
  2. Allez sur http://127.0.0.1:5000/login      
     -> Connectez-vous avec admin@asl3d.com     
=================================================
""")

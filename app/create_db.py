"""
create_db.py — Crée la base de données asl3d_db et exécute le schéma SQL
Utilisation : python create_db.py
"""
import os
import sys

try:
    import pymysql
except ImportError:
    print("❌ PyMySQL non installé. Exécutez : pip install pymysql")
    sys.exit(1)

HOST     = 'localhost'
USER     = 'root'
PASSWORD = 'Chaimae@2005'
DB_NAME  = 'asl3d_db'
SQL_FILE = os.path.join(os.path.dirname(__file__), 'db_setup.sql')

print(f"🔌 Connexion à MySQL ({HOST}) en tant que {USER}...")

try:
    conn = pymysql.connect(host=HOST, user=USER, password=PASSWORD, charset='utf8mb4')
    cursor = conn.cursor()
except Exception as e:
    print(f"❌ Impossible de se connecter à MySQL : {e}")
    print("   → Assurez-vous que XAMPP MySQL est démarré.")
    sys.exit(1)

print(f"✅ Connecté. Création de la base '{DB_NAME}'...")

try:
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    cursor.execute(f"USE `{DB_NAME}`;")
    conn.commit()
    print(f"✅ Base '{DB_NAME}' créée (ou déjà existante).")
except Exception as e:
    print(f"❌ Erreur lors de la création de la base : {e}")
    sys.exit(1)

# Exécuter db_setup.sql
print(f"📄 Exécution de {SQL_FILE}...")
try:
    with open(SQL_FILE, 'r', encoding='utf-8') as f:
        sql = f.read()

    # Split on semicolons (skip empty statements)
    statements = [s.strip() for s in sql.split(';') if s.strip()]
    for stmt in statements:
        try:
            cursor.execute(stmt)
        except pymysql.err.OperationalError as e:
            # Ignore "table already exists" errors
            if e.args[0] in (1050, 1060, 1061):
                continue
            print(f"  ⚠️  {e}")

    conn.commit()
    print("✅ Schéma créé avec succès !")
except FileNotFoundError:
    print(f"❌ Fichier {SQL_FILE} introuvable.")
    sys.exit(1)
except Exception as e:
    print(f"❌ Erreur SQL : {e}")
    sys.exit(1)
finally:
    cursor.close()
    conn.close()

print("""
╔═══════════════════════════════════════════════╗
║  ✅ Base de données ASL-3D prête !             ║
║                                               ║
║  Maintenant :                                 ║
║  1. Redémarrez le serveur Flask               ║
║     → Ctrl+C puis : python run.py             ║
║  2. Allez sur http://127.0.0.1:5000/register  ║
║     → Créez votre compte                      ║
╚═══════════════════════════════════════════════╝
""")

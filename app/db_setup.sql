-- ===========================================================
-- ASL-3D Database Setup — MySQL (XAMPP)
-- Fichier  : db_setup.sql
-- Exécuter : source db_setup.sql   (depuis phpMyAdmin ou CLI)
-- ===========================================================

-- 1. Créer et sélectionner la base de données
CREATE DATABASE IF NOT EXISTS asl3d_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE asl3d_db;

-- ===========================================================
-- 2. TABLE users  — Comptes ingénieurs / gestionnaires
-- ===========================================================
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(120)  NOT NULL,
    email         VARCHAR(180)  NOT NULL UNIQUE,
    password_hash VARCHAR(255),               -- NULL si connexion OAuth2
    oauth_provider ENUM('local','google','github') DEFAULT 'local',
    oauth_id      VARCHAR(120)  DEFAULT NULL, -- ID fourni par Google/GitHub
    role          ENUM('admin','ingenieur','lecteur') DEFAULT 'ingenieur',
    avatar_url    VARCHAR(255)  DEFAULT NULL,
    created_at    DATETIME      DEFAULT CURRENT_TIMESTAMP,
    last_login    DATETIME      DEFAULT NULL
) ENGINE=InnoDB;

-- ===========================================================
-- 3. TABLE projects  — Monuments / chantiers de restauration
-- ===========================================================
CREATE TABLE IF NOT EXISTS projects (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT           NOT NULL,
    name          VARCHAR(200)  NOT NULL,                  -- Nom du projet
    monument      VARCHAR(200)  NOT NULL,                  -- Nom du monument
    description   TEXT          DEFAULT NULL,
    location      VARCHAR(255)  DEFAULT NULL,
    upload_folder VARCHAR(255)  NOT NULL,                  -- Chemin relatif dossier photos
    status        ENUM('nouveau','en_cours','termine','danger','archive')
                                DEFAULT 'nouveau',
    created_at    DATETIME      DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Index pour accélérer les requêtes par utilisateur
CREATE INDEX idx_projects_user ON projects(user_id);

-- ===========================================================
-- 4. TABLE analyses  — Rapports d'analyse IA
-- ===========================================================
CREATE TABLE IF NOT EXISTS analyses (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    project_id      INT           NOT NULL,
    source_image    VARCHAR(255)  NOT NULL,   -- Nom du fichier analysé
    annotated_image VARCHAR(255)  DEFAULT NULL, -- Image avec annotations OpenCV
    risk_score      DECIMAL(5,2)  DEFAULT 0.00, -- Score 0–100
    severity        ENUM('faible','moyenne','haute','critique') DEFAULT 'faible',
    degradations    JSON          DEFAULT NULL, -- Données brutes JSON des détections
    recommendations TEXT          DEFAULT NULL,
    status_update   ENUM('Sain','Attention','Danger') DEFAULT 'Sain',
    model_used      VARCHAR(100)  DEFAULT 'YOLOv8',
    created_at      DATETIME      DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_analyses_project ON analyses(project_id);

-- ===========================================================
-- 5. TABLE reconstructions  — Modèles 3D générés
-- ===========================================================
CREATE TABLE IF NOT EXISTS reconstructions (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    project_id    INT           NOT NULL,
    model_file    VARCHAR(255)  NOT NULL,   -- Chemin vers le .glb / .obj
    vertices      INT           DEFAULT 0,
    faces         INT           DEFAULT 0,
    quality       ENUM('low','medium','high','ultra') DEFAULT 'high',
    created_at    DATETIME      DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ===========================================================
-- 6. TABLE reports  — Rapports PDF générés
-- ===========================================================
CREATE TABLE IF NOT EXISTS reports (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    analysis_id   INT           NOT NULL,
    project_id    INT           NOT NULL,
    engineer_name VARCHAR(150)  NOT NULL,
    pdf_path      VARCHAR(255)  NOT NULL,   -- Chemin relatif vers le PDF
    created_at    DATETIME      DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id)  REFERENCES projects(id)  ON DELETE CASCADE
) ENGINE=InnoDB;

-- ===========================================================
-- 7. Données de test (optionnel — supprimer en production)
-- ===========================================================
-- Mot de passe = 'admin123' (hashed avec bcrypt — à remplacer par l'app)
INSERT IGNORE INTO users (name, email, password_hash, role, oauth_provider) VALUES
('Admin ASL3D', 'admin@asl3d.com', '$2b$12$placeholder_replace_by_app', 'admin', 'local');

-- ===========================================================
-- 8. Vue de synthèse pour le tableau de bord
-- ===========================================================
CREATE OR REPLACE VIEW v_dashboard AS
SELECT
    p.id              AS project_id,
    p.name            AS project_name,
    p.monument,
    p.status,
    p.created_at,
    u.name            AS engineer,
    COUNT(a.id)       AS analysis_count,
    MAX(a.risk_score) AS max_risk_score,
    MAX(a.status_update) AS alert_level
FROM projects p
LEFT JOIN users u ON p.user_id = u.id
LEFT JOIN analyses a ON a.project_id = p.id
GROUP BY p.id, p.name, p.monument, p.status, p.created_at, u.name;

-- ===========================================================
-- Fin du script
-- Connexion depuis Python : PyMySQL + SQLAlchemy
-- URI : mysql+pymysql://root:@localhost/asl3d_db
-- ===========================================================

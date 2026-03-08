"""
models.py — SQLAlchemy models for ASL-3D (MySQL via XAMPP)
Connection URI: mysql+pymysql://root:@localhost/asl3d_db
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(120), nullable=False)
    email          = db.Column(db.String(180), unique=True, nullable=False)
    password_hash  = db.Column(db.String(255), nullable=True)
    oauth_provider = db.Column(db.Enum('local', 'google', 'github'), default='local')
    oauth_id       = db.Column(db.String(120), nullable=True)
    role           = db.Column(db.Enum('admin', 'ingenieur', 'lecteur'), default='ingenieur')
    avatar_url     = db.Column(db.String(255), nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    last_login     = db.Column(db.DateTime, nullable=True)

    projects = db.relationship('Project', backref='owner', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'


class Project(db.Model):
    __tablename__ = 'projects'

    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name          = db.Column(db.String(200), nullable=False)
    monument      = db.Column(db.String(200), nullable=False)
    description   = db.Column(db.Text, nullable=True)
    location      = db.Column(db.String(255), nullable=True)
    upload_folder = db.Column(db.String(255), nullable=False)
    status        = db.Column(
        db.Enum('nouveau', 'en_cours', 'termine', 'danger', 'archive'),
        default='nouveau'
    )
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    analyses        = db.relationship('Analysis',       backref='project', lazy=True, cascade='all, delete-orphan')
    reconstructions = db.relationship('Reconstruction', backref='project', lazy=True, cascade='all, delete-orphan')
    reports         = db.relationship('Report',         backref='project', lazy=True, cascade='all, delete-orphan')

    @property
    def latest_analysis(self):
        return Analysis.query.filter_by(project_id=self.id).order_by(Analysis.created_at.desc()).first()

    def __repr__(self):
        return f'<Project {self.name}>'


class Analysis(db.Model):
    __tablename__ = 'analyses'

    id               = db.Column(db.Integer, primary_key=True)
    project_id       = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    source_image     = db.Column(db.String(255), nullable=False)
    annotated_image  = db.Column(db.String(255), nullable=True)
    risk_score       = db.Column(db.Numeric(5, 2), default=0.00)
    severity         = db.Column(db.Enum('faible', 'moyenne', 'haute', 'critique'), default='faible')
    degradations     = db.Column(db.JSON, nullable=True)
    recommendations  = db.Column(db.Text, nullable=True)
    status_update    = db.Column(db.Enum('Sain', 'Attention', 'Danger'), default='Sain')
    model_used       = db.Column(db.String(100), default='YOLOv8')
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    reports = db.relationship('Report', backref='analysis', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Analysis project={self.project_id} score={self.risk_score}>'


class Reconstruction(db.Model):
    __tablename__ = 'reconstructions'

    id         = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    model_file = db.Column(db.String(255), nullable=False)
    vertices   = db.Column(db.Integer, default=0)
    faces      = db.Column(db.Integer, default=0)
    quality    = db.Column(db.Enum('low', 'medium', 'high', 'ultra'), default='high')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Reconstruction project={self.project_id} file={self.model_file}>'


class Report(db.Model):
    __tablename__ = 'reports'

    id            = db.Column(db.Integer, primary_key=True)
    analysis_id   = db.Column(db.Integer, db.ForeignKey('analyses.id'), nullable=False)
    project_id    = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    engineer_name = db.Column(db.String(150), nullable=False)
    pdf_path      = db.Column(db.String(255), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Report project={self.project_id} pdf={self.pdf_path}>'

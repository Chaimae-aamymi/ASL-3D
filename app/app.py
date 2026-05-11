import os
import io
import json
import base64
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, send_file, send_from_directory, current_app
)
import threading
from werkzeug.utils import secure_filename
import numpy as np
from PIL import Image

from models import db, User, Project, Analysis, Reconstruction, Report, TaskStatus, UrbanProject

#  Optional deps (fail gracefully if not installed yet) 
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    MATPLOTLIB = True
except ImportError:
    MATPLOTLIB = False

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

from ai_reconstruction_engine import ai_reconstruct

#  App Factory 
app = Flask(__name__, template_folder='templates', static_folder='static')

#  Configuration 
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'asl3d-2026-secret'),
    SQLALCHEMY_DATABASE_URI=os.environ.get('DB_URI', 'postgresql://postgres:admin@localhost/asl3d_db'),


    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=1000 * 1024 * 1024,  # 1000 MB
    UPLOAD_BASE=os.path.join('static', 'uploads'),
    OUTPUT_FOLDER='outputs',
    YOLO_FOLDER=os.path.join('static', 'analyses', 'results'),
    AVATAR_FOLDER=os.path.join('static', 'avatars'),
)

os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
os.makedirs(app.config['UPLOAD_BASE'], exist_ok=True)
os.makedirs(app.config['YOLO_FOLDER'], exist_ok=True)
os.makedirs(app.config['AVATAR_FOLDER'], exist_ok=True)

db.init_app(app)

ALLOWED_IMG = {'jpg', 'jpeg', 'png', 'bmp', 'webp', 'jpge', 'tiff', 'tif', 'heic', 'heif', 'gif', 'ico'}

def allowed_image(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMG

# ── Auth helpers ───────────────────────────────────────────────────────
def login_required(f):
    """Decorator: redirect to /login if no active session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Connectez-vous pour accéder à cette page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def current_user():
    uid = session.get('user_id')
    return User.query.get(uid) if uid else None

# ── Matplotlib helpers ─────────────────────────────────────────────────
def pie_chart_b64(sain: int, danger: int) -> str:
    """Generate a Sain/Dégradé pie chart as base64 PNG."""
    if not MATPLOTLIB:
        return ''
    fig, ax = plt.subplots(figsize=(3.5, 3.5))
    fig.patch.set_facecolor('#151b28')
    sizes  = [max(sain, 0), max(danger, 0)]
    if sum(sizes) == 0:
        sizes = [1, 0] # Avoid NaN if there are 0 projects
    labels = ['Sain', 'Dégradé']
    colors = ['#06d6a0', '#ff6b6b']
    wedge_props = {'linewidth': 2, 'edgecolor': '#151b28'}
    ax.pie(sizes, labels=labels, colors=colors, autopct='%1.0f%%',
           wedgeprops=wedge_props, textprops={'color': '#e8ecf4', 'fontsize': 10})
    ax.set_facecolor('#151b28')
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=90, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return 'data:image/png;base64,' + base64.b64encode(buf.read()).decode()

def risk_gauge_b64(score: float) -> str:
    """Generate a risk gauge as base64 PNG."""
    if not MATPLOTLIB:
        return ''
    score = float(score)
    value = score / 100.0
    if score >= 70:
        color, label = '#ff6b6b', 'DANGER'
    elif score >= 40:
        color, label = '#ffd166', 'ATTENTION'
    else:
        color, label = '#06d6a0', 'SAIN'

    fig, ax = plt.subplots(figsize=(4, 2.2), subplot_kw={'aspect': 'equal'})
    fig.patch.set_facecolor('#151b28')
    ax.set_facecolor('#151b28')
    theta = np.linspace(np.pi, 0, 200)
    ax.plot(np.cos(theta), np.sin(theta), color='#2a3347', linewidth=18,
            solid_capstyle='round')
    theta_fill = np.linspace(np.pi, np.pi - value * np.pi, 200)
    ax.plot(np.cos(theta_fill), np.sin(theta_fill), color=color,
            linewidth=18, solid_capstyle='round')
    ax.text(0, 0.05, label, ha='center', va='center', fontsize=11,
            fontweight='bold', color=color, fontfamily='monospace')
    ax.text(0, -0.28, f'{int(score)}/100', ha='center', va='center',
            fontsize=9, color='#d0d6e8', fontfamily='monospace')
    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-0.5, 1.2)
    ax.axis('off')
    plt.tight_layout(pad=0.1)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=90, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return 'data:image/png;base64,' + base64.b64encode(buf.read()).decode()


# ═══════════════════════════════════════════════════════════════════════
# ROUTE 1 — Authentication
# ═══════════════════════════════════════════════════════════════════════
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email, oauth_provider='local').first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            user.last_login = datetime.utcnow()
            db.session.commit()
            flash(f'Bienvenue, {user.name} !', 'success')
            return redirect(url_for('dashboard'))
        flash('Email ou mot de passe incorrect.', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        if not name or not email or not password:
            flash('Tous les champs sont obligatoires.', 'error')
        elif password != confirm:
            flash('Les mots de passe ne correspondent pas.', 'error')
        elif len(password) < 6:
            flash('Le mot de passe doit contenir au moins 6 caractères.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('Cet email est déjà utilisé.', 'error')
        else:
            user = User(name=name, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Compte créé avec succès ! Connectez-vous.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('Vous avez été déconnecté.', 'success')
    return redirect(url_for('login'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = current_user()
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_info':
            name = request.form.get('name')
            email = request.form.get('email')
            avatar_file = request.files.get('avatar')
            
            # Avatar Upload
            if avatar_file and avatar_file.filename != '':
                if allowed_image(avatar_file.filename):
                    ext = avatar_file.filename.rsplit('.', 1)[1].lower()
                    filename = f"user_{user.id}_{int(datetime.utcnow().timestamp())}.{ext}"
                    filepath = os.path.join(app.config['AVATAR_FOLDER'], filename)
                    avatar_file.save(filepath)
                    user.avatar_url = f"/static/avatars/{filename}"
                else:
                    flash('Format d\'image non supporté.', 'error')

            # Simple validation: email must look valid-ish
            if not name or not email or '@' not in email:
                flash('Nom ou email invalide.', 'error')
            else:
                user.name = name
                user.email = email
                db.session.commit()
                flash('Profil mis à jour !', 'success')
                
        elif action == 'change_password':
            old_p = request.form.get('old_password')
            new_p = request.form.get('new_password')
            conf_p = request.form.get('confirm_password')
            
            if not user.check_password(old_p):
                flash('Ancien mot de passe incorrect.', 'error')
            elif new_p != conf_p:
                flash('Les nouveaux mots de passe ne correspondent pas.', 'error')
            elif len(new_p) < 6:
                flash('Le mot de passe doit faire au moins 6 caractères.', 'error')
            else:
                user.set_password(new_p)
                db.session.commit()
                flash('Mot de passe mis à jour !', 'success')
                
        return redirect(url_for('profile'))

    return render_template('profile.html', user=user)


# ═══════════════════════════════════════════════════════════════════════
# OAUTH2 — Google & GitHub Social Login  (using Authlib)
# ═══════════════════════════════════════════════════════════════════════
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
except ImportError:
    pass

try:
    from authlib.integrations.flask_client import OAuth as AuthlibOAuth
    _oauth = AuthlibOAuth(app)

    # ── Google ────────────────────────────────────────────────────────
    _google_id     = os.environ.get('GOOGLE_CLIENT_ID', '')
    _google_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '')
    if _google_id and _google_id != 'VOTRE_CLIENT_ID_GOOGLE':
        _oauth.register(
            name='google',
            client_id=_google_id,
            client_secret=_google_secret,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'},
        )
        GOOGLE_OAUTH = True
    else:
        GOOGLE_OAUTH = False

    # ── GitHub ────────────────────────────────────────────────────────
    _github_id     = os.environ.get('GITHUB_CLIENT_ID', '')
    _github_secret = os.environ.get('GITHUB_CLIENT_SECRET', '')
    if _github_id and _github_id != 'VOTRE_CLIENT_ID_GITHUB':
        _oauth.register(
            name='github',
            client_id=_github_id,
            client_secret=_github_secret,
            access_token_url='https://github.com/login/oauth/access_token',
            authorize_url='https://github.com/login/oauth/authorize',
            api_base_url='https://api.github.com/',
            client_kwargs={'scope': 'read:user user:email'},
        )
        GITHUB_OAUTH = True
    else:
        GITHUB_OAUTH = False

    AUTHLIB_AVAILABLE = True
except Exception as _e:
    AUTHLIB_AVAILABLE = False
    GOOGLE_OAUTH      = False
    GITHUB_OAUTH      = False
    print(f'[OAuth] Authlib not available: {_e}')


def _oauth_login_user(email: str, name: str, provider: str, oauth_id: str):
    """Find or create a user from OAuth data, then start session."""
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            name=name,
            email=email,
            oauth_provider=provider,
            oauth_id=str(oauth_id),
            role='ingenieur',
        )
        db.session.add(user)
        db.session.commit()
    session['user_id'] = user.id
    flash(f'Bienvenue, {user.name} ! (connexion via {provider.capitalize()})', 'success')


# ── Google Routes ─────────────────────────────────────────────────────
@app.route('/auth/google')
def auth_google():
    if not GOOGLE_OAUTH:
        flash('Connexion Google non configurée. Ajoutez vos clés dans le fichier .env', 'error')
        return redirect(url_for('login'))
    redirect_uri = url_for('auth_google_callback', _external=True)
    return _oauth.google.authorize_redirect(redirect_uri)


@app.route('/auth/google/callback')
def auth_google_callback():
    if not GOOGLE_OAUTH:
        return redirect(url_for('login'))
    try:
        token    = _oauth.google.authorize_access_token()
        userinfo = token.get('userinfo') or _oauth.google.userinfo()
        _oauth_login_user(
            email    = userinfo.get('email', ''),
            name     = userinfo.get('name', userinfo.get('email', 'Utilisateur')),
            provider = 'google',
            oauth_id = userinfo.get('sub', ''),
        )
        return redirect(url_for('dashboard'))
    except Exception as e:
        flash(f'Erreur Google OAuth : {e}', 'error')
        return redirect(url_for('login'))


# ── GitHub Routes ─────────────────────────────────────────────────────
@app.route('/auth/github')
def auth_github():
    if not GITHUB_OAUTH:
        flash('Connexion GitHub non configurée. Ajoutez vos clés dans le fichier .env', 'error')
        return redirect(url_for('login'))
    redirect_uri = url_for('auth_github_callback', _external=True)
    return _oauth.github.authorize_redirect(redirect_uri)


@app.route('/auth/github/callback')
def auth_github_callback():
    if not GITHUB_OAUTH:
        return redirect(url_for('login'))
    try:
        _oauth.github.authorize_access_token()
        resp  = _oauth.github.get('user')
        info  = resp.json()
        # GitHub may not expose public email — fetch primary email separately
        email = info.get('email')
        if not email:
            er = _oauth.github.get('user/emails')
            for e in er.json():
                if e.get('primary') and e.get('verified'):
                    email = e['email']
                    break
        email = email or f"github_{info['id']}@users.noreply.github.com"
        _oauth_login_user(
            email    = email,
            name     = info.get('name') or info.get('login', 'Utilisateur GitHub'),
            provider = 'github',
            oauth_id = info.get('id', ''),
        )
        return redirect(url_for('dashboard'))
    except Exception as e:
        flash(f'Erreur GitHub OAuth : {e}', 'error')
        return redirect(url_for('login'))


# ═══════════════════════════════════════════════════════════════════════
# ROUTE 2 — Dashboard (Tableau de bord)
# ═══════════════════════════════════════════════════════════════════════

@app.route('/')
@login_required
def dashboard():
    user = current_user()
    projects = Project.query.filter_by(user_id=user.id).order_by(
        Project.updated_at.desc()).all()

    total_projects = len(projects)
    danger_count   = sum(1 for p in projects if p.status == 'danger')
    recent_analyses = Analysis.query.join(Project).filter(
        Project.user_id == user.id
    ).order_by(Analysis.created_at.desc()).limit(5).all()

    # Matplotlib pie chart
    sain_count    = sum(1 for p in projects if p.status not in ('danger',))
    pie_chart     = pie_chart_b64(sain_count, danger_count)

    return render_template('index.html',
                           user=user,
                           projects=projects,
                           total_projects=total_projects,
                           danger_count=danger_count,
                           recent_analyses=recent_analyses,
                           pie_chart=pie_chart)


# ═══════════════════════════════════════════════════════════════════════
# ROUTE 3 — Scanner (Importation des données)
# ═══════════════════════════════════════════════════════════════════════
@app.route('/scanner', methods=['GET', 'POST'])
@login_required
def scanner():
    user = current_user()
    projects = Project.query.filter_by(user_id=user.id).order_by(
        Project.created_at.desc()).all()
    new_project = None

    if request.method == 'POST':
        monument    = request.form.get('monument', '').strip()
        proj_name   = request.form.get('project_name', '').strip()
        description = request.form.get('description', '').strip()
        location    = request.form.get('location', '').strip()
        latitude    = request.form.get('latitude')
        longitude   = request.form.get('longitude')
        files       = request.files.getlist('files')

        if not monument or not proj_name:
            flash('Le nom du monument et du projet sont obligatoires.', 'error')
            return redirect(url_for('scanner'))

        if not files or all(f.filename == '' for f in files):
            flash('Veuillez sélectionner au moins une image.', 'error')
            return redirect(url_for('scanner'))

        # Create upload sub-folder
        safe_monument = secure_filename(monument.replace(' ', '_'))
        folder_name   = f"{safe_monument}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        upload_path   = os.path.join(app.config['UPLOAD_BASE'], folder_name)
        os.makedirs(upload_path, exist_ok=True)

        saved_files = []
        for f in files:
            if f and f.filename and allowed_image(f.filename):
                fname = secure_filename(f.filename)
                f.save(os.path.join(upload_path, fname))
                saved_files.append(fname)
            else:
                flash(f'Fichier ignoré (format invalide) : {f.filename}', 'error')

        if not saved_files:
            flash('Aucun fichier valide uploadé.', 'error')
            return redirect(url_for('scanner'))

        # Save project to DB
        lat_val = float(latitude) if latitude else None
        lng_val = float(longitude) if longitude else None

        project = Project(
            user_id=user.id,
            name=proj_name,
            monument=monument,
            description=description,
            location=location,
            latitude=lat_val,
            longitude=lng_val,
            upload_folder=folder_name,
            status='nouveau'
        )
        db.session.add(project)
        db.session.commit()
        new_project = project

        flash(f'{len(saved_files)} image(s) importée(s) pour « {monument} ».', 'success')
        projects = Project.query.filter_by(user_id=user.id).order_by(
            Project.created_at.desc()).all()

    return render_template('scanner.html', user=user, projects=projects,
                           new_project=new_project)


# ═══════════════════════════════════════════════════════════════════════
# ROUTE 3a — Gestion des Projets
# ═══════════════════════════════════════════════════════════════════════
@app.route('/projects')
@login_required
def projects_management():
    user = current_user()
    projects = Project.query.filter_by(user_id=user.id).order_by(
        Project.updated_at.desc()).all()
    
    # Statistiques pour la gestion
    total_projects = len(projects)
    danger_count   = sum(1 for p in projects if p.status == 'danger')
    inprogress_count = sum(1 for p in projects if p.status == 'en_cours')
    completed_count = sum(1 for p in projects if p.status == 'termine')

    return render_template('projects.html',
                           user=user,
                           projects=projects,
                           total_projects=total_projects,
                           danger_count=danger_count,
                           inprogress_count=inprogress_count,
                           completed_count=completed_count)


# ═══════════════════════════════════════════════════════════════════════
# ROUTE API — Photos du projet
# ═══════════════════════════════════════════════════════════════════════
@app.route('/api/project/<int:project_id>/photos')
@login_required
def get_project_photos(project_id):
    user = current_user()
    project = Project.query.filter_by(id=project_id, user_id=user.id).first()
    if not project:
        return {"photos": []}, 404
        
    upload_path = os.path.join(app.config['UPLOAD_BASE'], project.upload_folder)
    if not os.path.exists(upload_path):
        return {"photos": []}
        
    photos = []
    for f in os.listdir(upload_path):
        if allowed_image(f):
            photos.append(url_for('static', filename=f'uploads/{project.upload_folder}/{f}'))
            
    return {"photos": photos}


# ═══════════════════════════════════════════════════════════════════════
# ROUTE 3b — Nettoyage complet d'un projet
# ═══════════════════════════════════════════════════════════════════════
@app.route('/delete_project', methods=['POST'])
@login_required
def delete_project():
    user = current_user()
    project_id = request.form.get('project_id', type=int)

    if not project_id:
        flash('ID projet invalide.', 'error')
        return redirect(url_for('index'))

    project = Project.query.filter_by(id=project_id, user_id=user.id).first()
    if not project:
        flash('Projet introuvable ou accès refusé.', 'error')
        return redirect(url_for('index'))

    import shutil
    try:
        # 1. Supprimer le dossier d'upload physique
        upload_path = os.path.join(app.config['UPLOAD_BASE'], project.upload_folder)
        if os.path.exists(upload_path):
            shutil.rmtree(upload_path, ignore_errors=True)

        # 2. Supprimer les fichiers de reconstruction (.glb)
        for recon in project.reconstructions:
            if recon.model_file:
                m_path = os.path.join(app.config['OUTPUT_FOLDER'], recon.model_file)
                if os.path.exists(m_path):
                    os.remove(m_path)

        # 3. Supprimer les images d'analyse annotées YOLOv8
        for ana in project.analyses:
            if ana.annotated_image:
                i_path = os.path.join(app.config['YOLO_FOLDER'], ana.annotated_image)
                if os.path.exists(i_path):
                    os.remove(i_path)

        # 4. Supprimer les rapports PDF générés
        for report in project.reports:
            if report.pdf_path and os.path.exists(report.pdf_path):
                os.remove(report.pdf_path)

        # 5. Supprimer de la base de données (SQLAlchemy cascade)
        db.session.delete(project)
        db.session.commit()
        flash(f"Le projet '{project.name}' et ses fichiers associés ont été complètement effacés.", "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la suppression : {e}", "error")

    return redirect(url_for('index'))


# ═══════════════════════════════════════════════════════════════════════
# ROUTE 3c — Ajouter des images à un projet existant
# ═══════════════════════════════════════════════════════════════════════
@app.route('/add_images', methods=['POST'])
@login_required
def add_images():
    user = current_user()
    project_id = request.form.get('project_id', type=int)
    files = request.files.getlist('files')

    if not project_id:
        flash('ID projet manquant.', 'error')
        return redirect(request.referrer or url_for('projects_management'))

    project = Project.query.filter_by(id=project_id, user_id=user.id).first()
    if not project:
        flash('Projet introuvable.', 'error')
        return redirect(request.referrer or url_for('projects_management'))

    if not files or all(f.filename == '' for f in files):
        flash('Veuillez sélectionner au moins une image.', 'error')
        return redirect(request.referrer or url_for('projects_management'))

    upload_path = os.path.join(app.config['UPLOAD_BASE'], project.upload_folder)
    os.makedirs(upload_path, exist_ok=True)

    count = 0
    for f in files:
        if f and f.filename and allowed_image(f.filename):
            fname = secure_filename(f.filename)
            # Ensure no duplicates: append timestamp if exists
            final_path = os.path.join(upload_path, fname)
            if os.path.exists(final_path):
                base, ext = os.path.splitext(fname)
                fname = f"{base}_{int(datetime.now().timestamp())}{ext}"
            
            f.save(os.path.join(upload_path, fname))
            count += 1

    if count > 0:
        db.session.commit() # Trigger onupdate for updated_at
        flash(f"{count} nouvelle(s) image(s) ajoutée(s) au projet '{project.name}'.", "success")
    else:
        flash("Aucune image valide n'a été ajoutée.", "error")

    return redirect(request.referrer or url_for('projects_management'))


def bg_cloud_reconstruct(app_main, project_id, image_files, task_id):
    """Worker dédié à la reconstruction via le Cloud (SaaS)."""
    with app_main.app_context():
        try:
            from cloud_service import cloud_service
            print(f"[BG-CLOUD] Début de la tâche Cloud pour le projet {project_id}")
            
            # 1. Lancer la reconstruction Cloud
            result = cloud_service.run_reconstruction(image_files, project_id)
            
            if result['status'] == 'success':
                # Dans le cas de la démo, on utilise un fichier placeholder
                model_filename = result.get('model_file', 'cloud_model_demo.glb')
                
                # Enregistrer en BDD
                recon = Reconstruction(
                    project_id=project_id,
                    model_file=model_filename,
                    vertices=50000, # Valeur estimée pour le Cloud
                    faces=100000,
                    quality='ultra' # Le Cloud est toujours ultra
                )
                
                task = TaskStatus.query.get(task_id)
                if task:
                    task.status = 'completed'
                    task.message = "Modèle généré via Cloud AI"
                
                db.session.add(recon)
                db.session.commit()
                print(f"[BG-CLOUD] Succès pour le projet {project_id}")
            else:
                raise Exception(result.get('message', 'Erreur Cloud inconnue'))

        except Exception as e:
            db.session.rollback()
            task = TaskStatus.query.get(task_id)
            if task:
                task.status = 'failed'
                task.message = f"Erreur Cloud: {str(e)}"
                db.session.commit()
            print(f"[BG-CLOUD] ÉCHEC : {e}")

# ═══════════════════════════════════════════════════════════════════════
# ROUTE 4 — Exploration Géospatiale 3D (Jumeau Numérique Mondial)
# ═══════════════════════════════════════════════════════════════════════
@app.route('/geospatial-3d')
@login_required
def geospatial_3d():
    user = current_user()
    selected_project_id = request.args.get('project_id', type=int)
    projects = Project.query.filter_by(user_id=user.id).all()
    
    selected_project = None
    if selected_project_id:
        selected_project = Project.query.filter_by(id=selected_project_id, user_id=user.id).first()
        
    return render_template('geospatial_3d.html', 
                           user=user, 
                           projects=projects,
                           selected_project=selected_project,
                           google_maps_api_key=os.getenv('GOOGLE_MAPS_API_KEY'))



def bg_analysis(app_main, project_id, folder, task_id, infra_name=None, infra_desc=None):
    with app_main.app_context():
        try:
            from degradation_detector import DegradationDetector
            detector     = DegradationDetector()
            
            all_degradations = []
            crack_count = 0
            
            images = [f for f in os.listdir(folder) if allowed_image(f)]
            if not images:
                raise ValueError("Aucune image à analyser.")
            
            first_annotated_name = None
            first_image_name = None
            
            task = TaskStatus.query.get(task_id)
            total_images = len(images)
            
            for i, image_name in enumerate(images):
                image_path = os.path.join(folder, image_name)
                image_arr    = np.array(Image.open(image_path).convert('RGB'))
                degradations = detector.detect(image_arr)
                
                if not first_image_name:
                    first_image_name = image_name
                
                # count fissures based on detector output
                crack_count += sum(1 for d in degradations if d.get('type') == 'fissures')
                all_degradations.extend(degradations)
                
                # Annotated visualization in static/analyses/results/
                viz_arr = detector.visualize(image_arr, degradations)
                annotated_name = f'yolo_result_{project_id}_{image_name}_{datetime.now().strftime("%H%M%S")}.png'
                annotated_path = os.path.join(app_main.config['YOLO_FOLDER'], annotated_name)
                Image.fromarray(viz_arr).save(annotated_path)
                
                if not first_annotated_name:
                    first_annotated_name = annotated_name
                    
                # Update progress — use direct SQL to avoid stale ORM object
                if task_id:
                    progress_pct = int(((i + 1) / total_images) * 100)
                    db.session.execute(
                        db.text("UPDATE task_status SET progress = :p WHERE id = :id"),
                        {"p": progress_pct, "id": task_id}
                    )
                    db.session.commit()

            # Threshold logic based on average cracks across ALL images
            avg_crack = crack_count / len(images) if images else 0
            
            if avg_crack < 3:
                severity, status_update = 'faible', 'Sain'
                rec_text = "Entretien normal. Pas de fissures majeures détectées sur l'ensemble."
            elif avg_crack <= 7:
                severity, status_update = 'moyenne', 'Attention'
                rec_text = "Surveillance accrue recommandée. Fissures détectées réparties sur le bâtiment."
            else:
                severity, status_update = 'critique', 'Danger'
                rec_text = "Intervention d'urgence. De nombreuses fissures majeures sur l'ensemble du projet."

            # Compute fallback legacy score based on rules
            if severity == 'critique':
                score = min(100, 75 + (avg_crack * 2.5))
            elif severity == 'moyenne':
                score = 45 + (avg_crack * 4)
            else:
                score = 15 + (avg_crack * 5)

            ana = Analysis(
                project_id=project_id,
                source_image=first_image_name,
                annotated_image=first_annotated_name,
                risk_score=round(score, 2),
                severity=severity,
                degradations=all_degradations,
                recommendations=rec_text,
                status_update=status_update,
                infra_project_name=infra_name,
                infra_project_desc=infra_desc
            )
            
            project = Project.query.get(project_id)
            if status_update == 'Danger':
                project.status = 'danger'
            elif status_update == 'Attention' and project.status == 'nouveau':
                project.status = 'en_cours'
                
            task = TaskStatus.query.get(task_id)
            if task:
                task.status = 'completed'
                task.progress = 100

            db.session.add(ana)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            task = TaskStatus.query.get(task_id)
            if task:
                task.status = 'failed'
                task.message = str(e)
            db.session.commit()

def bg_reconstruction(app_main, project_id, folder, task_id):
    with app_main.app_context():
        try:
            # Pick the best image (first one for now)
            images = [f for f in os.listdir(folder) if allowed_image(f)]
            if not images:
                raise ValueError("Aucune image pour la reconstruction.")
            
            image_path = os.path.join(folder, images[0])
            output_model = os.path.join('static', 'models', f'model_{project_id}.glb')
            
            # Run AI reconstruction
            ai_reconstruct(image_path, output_model)
            
            # Update task
            from sqlalchemy import text
            db.session.execute(text("UPDATE task_status SET status = 'completed', progress = 100, message = 'Modèle 3D généré avec succès' WHERE id = :tid"), {'tid': task_id})
            db.session.commit()
            
        except Exception as e:
            print(f"Erreur Reconstruction IA: {e}")
            from sqlalchemy import text
            db.session.execute(text("UPDATE task_status SET status = 'failed', message = :msg WHERE id = :tid"), 
                              {'msg': str(e), 'tid': task_id})
            db.session.commit()

@app.route('/reconstruct/<int:project_id>', methods=['POST'])
@login_required
def run_reconstruct(project_id):
    user = current_user()
    project = Project.query.filter_by(id=project_id, user_id=user.id).first_or_404()
    
    # Check if a reconstruction is already running
    active_task = TaskStatus.query.filter_by(project_id=project_id, task_type='reconstruction', status='running').first()
    if active_task:
        flash("Une reconstruction est déjà en cours.", "warning")
        return redirect(url_for('project_detail', project_id=project_id))
    
    # Create new task
    new_task = TaskStatus(
        project_id=project_id,
        task_type='reconstruction',
        status='running',
        progress=0,
        message="Démarrage de la reconstruction IA..."
    )
    db.session.add(new_task)
    db.session.commit()
    
    folder = os.path.join(current_app.config['UPLOAD_BASE'], project.upload_folder)
    
    # Start thread
    thread = threading.Thread(target=bg_reconstruction, args=(current_app._get_current_object(), project_id, folder, new_task.id))
    thread.start()
    
    flash("La reconstruction 3D intelligente a été lancée.", "success")
    return redirect(url_for('project_detail', project_id=project_id))


# ═══════════════════════════════════════════════════════════════════════
# ROUTE API — Statut de tâche (pour la barre de progression)
# ═══════════════════════════════════════════════════════════════════════
@app.route('/api/task_status/<int:task_id>')
@login_required
def api_task_status(task_id):
    task = TaskStatus.query.filter_by(id=task_id).first()
    if not task:
        return {"status": "unknown", "progress": 0}
    return {
        "status": task.status,
        "progress": task.progress or 0,
        "message": task.message
    }

# ═══════════════════════════════════════════════════════════════════════
# ROUTE 5 — Analyse IA (YOLOv8 + Risk Score)
# ═══════════════════════════════════════════════════════════════════════
@app.route('/analysis', methods=['GET', 'POST'])
@login_required
def analysis():
    user = current_user()
    projects = Project.query.filter_by(user_id=user.id).order_by(
        Project.created_at.desc()).all()
    result   = None
    gauge    = None
    selected_project_id = request.args.get('project_id', type=int)
    active_task = None

    if request.method == 'POST':
        project_id = request.form.get('project_id', type=int)
        image_name = request.form.get('image_name', '')
        infra_name = request.form.get('infra_project_name', '').strip()
        infra_desc = request.form.get('infra_project_desc', '').strip()

        project = Project.query.filter_by(id=project_id, user_id=user.id).first()
        if not project:
            flash('Projet introuvable.', 'error')
            return redirect(url_for('analysis'))
            
        folder = os.path.join(app.config['UPLOAD_BASE'], project.upload_folder)
        if not os.path.exists(folder):
            flash("Le dossier d'images de ce projet est introuvable sur le disque.", 'error')
            return redirect(url_for('analysis'))

        # Check if already running
        existing_task = TaskStatus.query.filter_by(project_id=project_id, task_type='yolo', status='running').first()
        if existing_task:
            flash('Une analyse globale est déjà en cours pour ce projet.', 'info')
            return redirect(url_for('analysis', project_id=project_id))

        # Create Task
        task = TaskStatus(project_id=project_id, task_type='yolo', status='running')
        db.session.add(task)
        db.session.commit()
        
        # Start Thread
        t = threading.Thread(target=bg_analysis, args=(current_app._get_current_object(), project_id, folder, task.id, infra_name, infra_desc))
        t.daemon = True
        t.start()
        
        flash('Analyse IA démarrée avec succès en arrière-plan !', 'success')
        return redirect(url_for('analysis', project_id=project_id))

    # Load data for selected project
    project_images = []
    if selected_project_id:
        proj = Project.query.filter_by(id=selected_project_id, user_id=user.id).first()
        if proj:
            folder = os.path.join(app.config['UPLOAD_BASE'], proj.upload_folder)
            if os.path.exists(folder):
                project_images = [
                    f for f in os.listdir(folder) if allowed_image(f)
                ]

        # Existing analysis for this project
        active_task = TaskStatus.query.filter_by(project_id=selected_project_id, task_type='yolo').order_by(TaskStatus.started_at.desc()).first()
        existing_ana = Analysis.query.filter_by(project_id=selected_project_id).order_by(Analysis.created_at.desc()).first()
        if existing_ana:
            result = existing_ana
            gauge  = risk_gauge_b64(existing_ana.risk_score)

    return render_template('analysis.html',
                           user=user,
                           projects=projects,
                           project_images=project_images,
                           result=result,
                           gauge=gauge,
                           selected_project_id=selected_project_id,
                           active_task=active_task)


def _compute_risk_score(degradations: list) -> float:
    """Map degradation confidence + severity to a 0-100 risk score."""
    if not degradations:
        return 0.0
    severity_w = {'haute': 1.0, 'critique': 1.0, 'moyenne': 0.6, 'basse': 0.3}
    total = sum(
        d.get('confidence', 0) * severity_w.get(d.get('severity', 'basse'), 0.3)
        for d in degradations
    )
    return min(total * 40, 100.0)  # scale to 0–100


def _build_recommendations(degradations: list) -> str:
    recs = {
        'fissures':    'Remplissage mortier spécialisé, évaluation structurelle urgente.',
        'humidite':    'Traitement imperméabilisant + drainage + ventilation forcée.',
        'erosion':     'Retraitement de surface + revêtement protecteur haute performance.',
        'champignons': 'Nettoyage biocide professionnel + traitement anti-fongique.',
        'decoloration':'Nettoyage doux contrôlé + vernis protecteur UV.',
        'effritement': 'Consolidation avancée + rejointoiement spécialisé.',
    }
    types_seen = {d.get('type') for d in degradations}
    lines = [f"• {t.upper()} : {recs[t]}" for t in types_seen if t in recs]
    return '\n'.join(lines) if lines else 'Aucune recommandation spécifique.'


# ═══════════════════════════════════════════════════════════════════════
# ROUTE 6 — Guide de Restauration + Rapport PDF
# ═══════════════════════════════════════════════════════════════════════
@app.route('/restoration-guide', methods=['GET', 'POST'])
@login_required
def restoration_guide():
    user     = current_user()
    projects = Project.query.filter_by(user_id=user.id).order_by(
        Project.updated_at.desc()).all()
    plan        = None
    selected_analysis = None
    selected_project_id = request.args.get('project_id', type=int)

    if request.method == 'POST':
        analysis_id = request.form.get('analysis_id', type=int)
        ana = Analysis.query.join(Project).filter(
            Analysis.id == analysis_id,
            Project.user_id == user.id
        ).first()
        if not ana:
            flash('Analyse introuvable.', 'error')
            return redirect(url_for('restoration_guide'))

        from reconstruction_engine import ReconstructionEngine
        engine = ReconstructionEngine()
        plan   = engine.generate_restoration_plan(
            ana.degradations or []
        )
        selected_analysis   = ana
        selected_project_id = ana.project_id

    # All analyses for projects belonging to user
    all_analyses = Analysis.query.join(Project).filter(
        Project.user_id == user.id
    ).order_by(Analysis.created_at.desc()).all()

    return render_template('restoration_guide.html',
                           user=user,
                           projects=projects,
                           all_analyses=all_analyses,
                           plan=plan,
                           selected_analysis=selected_analysis,
                           selected_project_id=selected_project_id)


@app.route('/generate-pdf/<int:analysis_id>')
@login_required
def generate_pdf(analysis_id):
    user = current_user()
    ana  = Analysis.query.join(Project).filter(
        Analysis.id == analysis_id,
        Project.user_id == user.id
    ).first()
    if not ana:
        flash('Analyse introuvable.', 'error')
        return redirect(url_for('restoration_guide'))

    if not FPDF_AVAILABLE:
        flash('La bibliothèque fpdf2 n\'est pas installée.', 'error')
        return redirect(url_for('restoration_guide'))

    try:
        from report_generator import generate_report
        from reconstruction_engine import ReconstructionEngine
        
        project  = ana.project
        engine   = ReconstructionEngine()
        plan     = engine.generate_restoration_plan(ana.degradations or [])
        
        # New Impact Analysis
        impact = engine.analyze_project_impact(
            ana.degradations or [],
            ana.infra_project_name,
            ana.infra_project_desc
        )
        
        pdf_name = f'rapport_{project.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        pdf_path = os.path.join(app.config['OUTPUT_FOLDER'], pdf_name)

        generate_report(
            output_path=pdf_path,
            engineer_name=user.name,
            project=project,
            analysis=ana,
            plan=plan,
            impact=impact
        )

        # Save in DB
        report = Report(
            analysis_id=analysis_id,
            project_id=project.id,
            engineer_name=user.name,
            pdf_path=pdf_name
        )
        db.session.add(report)
        db.session.commit()

        return send_file(pdf_path, as_attachment=True, download_name=pdf_name)

    except Exception as e:
        flash(f'Erreur lors de la génération du PDF : {e}', 'error')
        return redirect(url_for('restoration_guide'))


# ── File serving ───────────────────────────────────────────────────────
@app.route('/outputs/<path:filename>')
@login_required
def output_file(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)


@app.route('/api/download/<path:filename>')
@login_required
def api_download(filename):
    """Generic download for any output file (models, PDFs, annotated images)."""
    # Try outputs folder first, then uploads base
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if os.path.exists(output_path):
        return send_file(output_path, as_attachment=True, download_name=filename)
    upload_path = os.path.join(app.config['UPLOAD_BASE'], filename)
    if os.path.exists(upload_path):
        return send_file(upload_path, as_attachment=True, download_name=filename)
    flash(f'Fichier introuvable : {filename}', 'error')
    return redirect(url_for('dashboard'))



@app.route('/static/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_BASE'], filename)


# ── Project helper: list images ────────────────────────────────────────
@app.route('/project/<int:project_id>/images')
@login_required
def project_images(project_id):
    user = current_user()
    project = Project.query.filter_by(id=project_id, user_id=user.id).first_or_404()
    folder  = os.path.join(app.config['UPLOAD_BASE'], project.upload_folder)
    images  = [f for f in os.listdir(folder) if allowed_image(f)] if os.path.exists(folder) else []
    return render_template('project_detail.html', project=project, images=images, user=user)


# ═══════════════════════════════════════════════════════════════════════
# ROUTE 8 — Urban Impact Assessment
# ═══════════════════════════════════════════════════════════════════════
@app.route('/urban-assessment', methods=['GET', 'POST'])
@login_required
def urban_assessment():
    user     = current_user()
    projects = Project.query.filter_by(user_id=user.id).order_by(Project.updated_at.desc()).all()
    result   = None
    selected_project_id = request.args.get('project_id', type=int)

    if request.method == 'POST':
        project_id = request.form.get('project_id', type=int)
        proj_type  = request.form.get('type', 'tramway')
        distance_m = request.form.get('distance_m', 100, type=float)
        intensity  = request.form.get('vibration_intensity', 'medium')

        project = Project.query.filter_by(id=project_id, user_id=user.id).first()
        if not project:
            flash('Projet introuvable.', 'error')
            return redirect(url_for('urban_assessment'))

        from reconstruction_engine import ReconstructionEngine
        engine    = ReconstructionEngine()
        latest    = project.latest_analysis
        degs      = latest.degradations if latest else []
        vib_data  = engine.calculate_vibration_impact(distance_m, proj_type, intensity, degs)

        up = UrbanProject(
            project_id=project_id, type=proj_type,
            distance_m=distance_m, vibration_intensity=intensity,
            v_impact=vib_data['v_impact'], risk_label=vib_data['risk_label'],
            recommendations='\n'.join(vib_data['recommendations'])
        )
        db.session.add(up)
        db.session.commit()

        flash(f'Analyse enregistree. V_impact = {vib_data["v_impact"]} mm/s — {vib_data["risk_label"]}', 'success')
        selected_project_id = project_id
        result = dict(vib_data)
        result['project_name'] = project.monument
        result['type_label']   = proj_type.capitalize()

    assessments = []
    if selected_project_id:
        assessments = UrbanProject.query.filter_by(project_id=selected_project_id).order_by(UrbanProject.created_at.desc()).all()

    return render_template('urban_assessment.html',
                           user=user, projects=projects, result=result,
                           assessments=assessments, selected_project_id=selected_project_id)


@app.route('/urban-assessment/pdf/<int:urban_id>')
@login_required
def urban_pdf(urban_id):
    user = current_user()
    up   = UrbanProject.query.join(Project).filter(
        UrbanProject.id == urban_id, Project.user_id == user.id
    ).first()
    if not up:
        flash('Evaluation introuvable.', 'error')
        return redirect(url_for('urban_assessment'))

    from report_generator import generate_report
    from reconstruction_engine import ReconstructionEngine
    engine  = ReconstructionEngine()
    project = up.project
    latest  = project.latest_analysis
    plan    = engine.generate_restoration_plan(latest.degradations or []) if latest else None
    k_map   = {'tramway': 0.03, 'route': 0.02, 'tunnel': 0.05, 'chantier': 0.025}
    vs_map  = {'low': 5.0, 'medium': 15.0, 'high': 30.0}

    vib_data = {
        'v_impact':        up.v_impact,
        'risk_label':      up.risk_label,
        'risk_color':      (220, 38, 38) if up.risk_label == 'CRITIQUE' else (217, 119, 6),
        'distance_m':      up.distance_m,
        'v_source':        vs_map.get(up.vibration_intensity, 15.0),
        'k':               k_map.get(up.type, 0.025),
        'recommendations': (up.recommendations or '').split('\n'),
        'severity_boost':  up.risk_label == 'CRITIQUE',
        'type_label':      up.type.capitalize(),
    }
    pdf_name = f'urban_{project.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    pdf_path = os.path.join(app.config['OUTPUT_FOLDER'], pdf_name)
    generate_report(output_path=pdf_path, engineer_name=user.name,
                    project=project, analysis=latest, plan=plan, urban_impact=vib_data)
    return send_file(pdf_path, as_attachment=True, download_name=pdf_name)


# ── Error handlers ─────────────────────────────────────────────────────
@app.errorhandler(413)
def too_large(e):
    flash('Fichier trop volumineux (max 1000 MB / 1 GB).', 'error')
    return redirect(url_for('scanner'))

@app.errorhandler(404)
def not_found(e):
    return render_template('index.html'), 404

@app.errorhandler(500)
def server_error(e):
    flash('Erreur interne du serveur.', 'error')
    return redirect(url_for('dashboard'))


# ── Init DB + run ──────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Creates tables if not already created by db_setup.sql
    app.run(debug=True, host='127.0.0.1', port=5000)

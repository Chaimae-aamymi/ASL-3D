import os
import sys
import subprocess
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
try:
    from dotenv import load_dotenv
    load_dotenv()  # Charge le fichier .env automatiquement
except ImportError:
    load_dotenv = None
import io
import json
import base64
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, send_file, send_from_directory, current_app
)
import threading
from werkzeug.utils import secure_filename
import numpy as np
from PIL import Image

# Prometheus monitoring
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from models import db, User, Project, Analysis, Reconstruction, Report, TaskStatus, UrbanProject
from sqlalchemy import text

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

from sfm_engine import run_advanced_reconstruction

#  App Factory 
app = Flask(__name__, template_folder='templates', static_folder='static')

# Configure Logging to file for Promtail/Loki when running on host
import logging
from logging.handlers import RotatingFileHandler

os.makedirs('logs', exist_ok=True)
log_file = os.path.join('logs', 'app.log')
file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
))
file_handler.setLevel(logging.INFO)

# Apply to root logger and app loggers
logging.getLogger().addHandler(file_handler)
logging.getLogger().setLevel(logging.INFO)
app.logger.addHandler(file_handler)
logging.getLogger('werkzeug').addHandler(file_handler)

# Prometheus metrics
if PROMETHEUS_AVAILABLE:
    request_count = Counter('asl3d_requests_total', 'Total requests', ['method', 'endpoint'])
    request_duration = Histogram('asl3d_request_duration_seconds', 'Request duration', ['endpoint'])
    active_tasks = Gauge('asl3d_active_tasks', 'Active tasks count', ['task_type'])
    project_count = Gauge('asl3d_projects_total', 'Total projects')
else:
    request_count = None
    request_duration = None
    active_tasks = None
    project_count = None

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
os.makedirs(os.path.join(app.static_folder, 'models'), exist_ok=True)

db.init_app(app)

ALLOWED_IMG = {'jpg', 'jpeg', 'jfif', 'png', 'bmp', 'webp', 'jpge', 'tiff', 'tif', 'heic', 'heif', 'gif', 'ico'}

def allowed_image(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMG

# ── Auth helpers ───────────────────────────────────────────────────────
def login_required(f):
    """Decorator: redirect to /login if no active session or email not verified."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Connectez-vous pour accéder à cette page.', 'error')
            return redirect(url_for('login'))
        user = current_user()
        if not user:
            session.pop('user_id', None)
            flash('Connectez-vous pour accéder à cette page.', 'error')
            return redirect(url_for('login'))
        if not user.is_verified:
            session.pop('user_id', None)
            flash('Veuillez vérifier votre adresse email pour activer votre compte.', 'warning')
            return redirect(url_for('verify_email_page', email=user.email))
        return f(*args, **kwargs)
    return decorated

def current_user():
    uid = session.get('user_id')
    return User.query.get(uid) if uid else None


def role_required(*roles):
    """Decorator: restrict route access to specific roles."""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            user = current_user()
            if not user or user.role not in roles:
                flash("Vous n'avez pas l'autorisation d'accéder à cette page.", 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator


def check_project_access(project_id, user):
    """Returns Project if user has access (owner or admin), else None."""
    if not project_id or not user:
        return None
    if user.role == 'admin':
        return Project.query.get(project_id)
    return Project.query.filter_by(id=project_id, user_id=user.id).first()


@app.context_processor
def inject_template_user():
    """Évite UndefinedError: 'user' sur les pages d'erreur et layouts partiels."""
    u = current_user() if 'user_id' in session else None
    return {'user': u}


def reconcile_stale_sfm_task(task_or_id, timeout_minutes=None):
    """Marque une tâche SfM bloquée (thread tué, reload Flask, etc.)."""
    if timeout_minutes is None:
        timeout_minutes = int(os.getenv('SFM_STALL_MINUTES', '120'))
    task = task_or_id
    if isinstance(task_or_id, int):
        task = TaskStatus.query.get(task_or_id)
    if not task or task.task_type != 'sfm' or task.status != 'running':
        return task
    now = datetime.utcnow()
    started = task.started_at or now
    updated = task.updated_at or started
    progress = task.progress or 0
    stale = False
    if progress <= 10 and (now - started) > timedelta(minutes=timeout_minutes):
        stale = True
    elif progress < 95 and (now - updated) > timedelta(minutes=timeout_minutes):
        stale = True
    if stale:
        task.status = 'failed'
        task.message = (
            'Reconstruction interrompue (serveur redémarré ou processus arrêté). '
            'Relancez la reconstruction. Conseil : FLASK_USE_RELOADER=0 dans .env.'
        )
        db.session.commit()
    return task


def reconcile_stale_yolo_task(task_or_id, timeout_minutes=None):
    """Marque une tâche d'analyse IA bloquée (thread tué, reload Flask, etc.)."""
    if timeout_minutes is None:
        timeout_minutes = int(os.getenv('YOLO_STALL_MINUTES', '60'))
    task = task_or_id
    if isinstance(task_or_id, int):
        task = TaskStatus.query.get(task_or_id)
    if not task or task.task_type != 'yolo' or task.status != 'running':
        return task
    now = datetime.utcnow()
    started = task.started_at or now
    updated = task.updated_at or started
    progress = task.progress or 0
    stale = False
    if progress <= 5 and (now - started) > timedelta(minutes=timeout_minutes):
        stale = True
    elif progress < 95 and (now - updated) > timedelta(minutes=timeout_minutes):
        stale = True
    if stale:
        task.status = 'failed'
        task.message = (
            "L'analyse IA a été interrompue (serveur redémarré ou processus arrêté). "
            "Veuillez relancer l'analyse."
        )
        db.session.commit()
    return task


def _reconstruction_page_context(user, selected_project_id=None):
    """Variables attendues par reconstruction.html."""
    running_task = None
    last_task = None
    result = None
    model_glb_url = None

    if selected_project_id:
        running_task = TaskStatus.query.filter_by(
            project_id=selected_project_id, task_type='sfm', status='running',
        ).order_by(TaskStatus.started_at.desc()).first()
        if running_task:
            reconcile_stale_sfm_task(running_task)
            if running_task.status != 'running':
                running_task = None

        last_task = TaskStatus.query.filter_by(
            project_id=selected_project_id, task_type='sfm',
        ).order_by(TaskStatus.started_at.desc()).first()

        result = Reconstruction.query.filter_by(
            project_id=selected_project_id,
        ).order_by(Reconstruction.created_at.desc()).first()

        model_fname = f'model_{selected_project_id}.glb'
        model_path = os.path.join(app.root_path, 'static', 'models', model_fname)
        if os.path.isfile(model_path) and os.path.getsize(model_path) > 500:
            model_glb_url = url_for('static', filename=f'models/{model_fname}')
        elif result and result.model_file:
            alt = os.path.join(app.static_folder, 'models', result.model_file)
            if os.path.isfile(alt) and os.path.getsize(alt) > 500:
                model_glb_url = url_for('static', filename=f'models/{result.model_file}')

    return {
        'running_task': running_task,
        'last_task': last_task,
        'result': result,
        'model_glb_url': model_glb_url,
        'selected_project_id': selected_project_id,
    }


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
        try:
            email    = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            
            if not email or not password:
                flash('Email et mot de passe requis.', 'error')
                return render_template('login.html')
            
            user = User.query.filter_by(email=email, oauth_provider='local').first()
            if user and user.check_password(password):
                if not user.is_verified:
                    flash('Veuillez vérifier votre adresse email pour activer votre compte.', 'warning')
                    return redirect(url_for('verify_email_page', email=email))
                session['user_id'] = user.id
                user.last_login = datetime.utcnow()
                db.session.commit()
                flash(f'Bienvenue, {user.name} !', 'success')
                return redirect(url_for('dashboard'))
            flash('Email ou mot de passe incorrect.', 'error')
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Login failed: {str(e)}", file=sys.stderr)
            flash(f'Erreur serveur : {str(e)}. Contactez un administrateur.', 'error')

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
            token = secrets.token_urlsafe(32)
            user = User(name=name, email=email, is_verified=False, verification_token=token)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            # Envoyer l'email de vérification
            success, verify_url = _send_verification_email(email, name, token)
            if not success:
                flash(f"⚠️ Impossible d'envoyer l'email. Pour le test local, activez votre compte via ce lien direct : {verify_url}", "error")
            return redirect(url_for('verify_email_page', email=email))

    return render_template('register.html')


def _send_verification_email(email, name, token):
    """Envoie un email de vérification via SMTP Gmail."""
    try:
        verify_url = url_for('verify_email_confirm', token=token, _external=True)
        mail_user   = os.getenv('MAIL_USERNAME', '')
        mail_pass   = os.getenv('MAIL_PASSWORD', '')
        mail_sender = os.getenv('MAIL_DEFAULT_SENDER', mail_user)
        mail_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
        mail_port   = int(os.getenv('MAIL_PORT', 587))

        msg = MIMEMultipart('alternative')
        msg['Subject'] = '✅ Activez votre compte ASL-3D'
        msg['From']    = mail_sender
        msg['To']      = email

        html_body = f"""
        <div style="font-family:'Outfit',Arial,sans-serif;background:#0F172A;padding:40px;border-radius:16px;max-width:520px;margin:auto;">
          <div style="text-align:center;margin-bottom:24px;">
            <h1 style="color:#818CF8;font-size:2rem;margin:0;">ASL-3D</h1>
            <p style="color:rgba(255,255,255,0.5);margin:4px 0 0;">Restauration Numérique Intelligente</p>
          </div>
          <div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:14px;padding:32px;">
            <h2 style="color:white;margin-top:0;">Bonjour {name} 👋</h2>
            <p style="color:rgba(255,255,255,0.6);line-height:1.6;">Merci de vous être inscrit sur <strong style="color:white;">ASL-3D</strong>. Cliquez sur le bouton ci-dessous pour activer votre compte :</p>
            <div style="text-align:center;margin:28px 0;">
              <a href="{verify_url}" style="background:linear-gradient(135deg,#4F46E5,#9333EA);color:white;padding:14px 32px;border-radius:12px;text-decoration:none;font-weight:700;font-size:1rem;display:inline-block;">
                ✅ Vérifier mon email
              </a>
            </div>
            <p style="color:rgba(255,255,255,0.4);font-size:0.82rem;">Ce lien expire dans 24h. Si vous n'avez pas créé de compte, ignorez cet email.</p>
          </div>
        </div>
        """
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(mail_server, mail_port) as server:
            server.ehlo()
            server.starttls()
            server.login(mail_user, mail_pass)
            server.sendmail(mail_user, email, msg.as_string())
        app.logger.info(f"[EMAIL] Vérification envoyée à {email}")
        return True, verify_url
    except Exception as e:
        app.logger.error(f"[EMAIL ERROR] Impossible d'envoyer à {email} : {e}", exc_info=True)
        return False, verify_url


@app.route('/verify-email')
def verify_email_page():
    """Page d'attente après inscription."""
    email = request.args.get('email', '')
    return render_template('verify_email.html', email=email)


@app.route('/verify-email/<token>')
def verify_email_confirm(token):
    """Lien cliqué dans l'email — active le compte."""
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        flash('Lien de vérification invalide ou expiré.', 'error')
        return redirect(url_for('login'))
    user.is_verified = True
    user.verification_token = None
    db.session.commit()
    flash('✅ Votre compte est activé ! Connectez-vous.', 'success')
    return redirect(url_for('login'))


@app.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Renvoie l'email de vérification."""
    email = request.form.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if user and not user.is_verified:
        token = secrets.token_urlsafe(32)
        user.verification_token = token
        db.session.commit()
        success, verify_url = _send_verification_email(email, user.name, token)
        if success:
            flash('Email de vérification renvoyé !', 'success')
        else:
            flash(f"⚠️ Impossible d'envoyer l'email. Pour le test local, activez votre compte via ce lien direct : {verify_url}", "error")
    else:
        flash('Email introuvable ou déjà vérifié.', 'error')
    return redirect(url_for('verify_email_page', email=email))


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
            is_verified=True,
        )
        db.session.add(user)
        db.session.commit()
    else:
        if not user.is_verified:
            user.is_verified = True
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
# MONITORING — Prometheus Metrics
# ═══════════════════════════════════════════════════════════════════════
_METRICS_SKIP_ENDPOINTS = frozenset({'metrics', 'health', 'static'})


def _track_prometheus_request():
    return (
        PROMETHEUS_AVAILABLE
        and request.endpoint
        and request.endpoint not in _METRICS_SKIP_ENDPOINTS
    )


@app.before_request
def track_request_start():
    if _track_prometheus_request():
        request.start_time = datetime.utcnow()


@app.after_request
def track_request_end(response):
    if _track_prometheus_request() and hasattr(request, 'start_time'):
        duration = (datetime.utcnow() - request.start_time).total_seconds()
        ep = request.endpoint or 'unknown'
        request_count.labels(method=request.method, endpoint=ep).inc()
        request_duration.labels(endpoint=ep).observe(duration)
    return response


@app.route('/metrics')
def metrics():
    if not PROMETHEUS_AVAILABLE:
        return "Prometheus client not available", 503

    with app.app_context():
        if active_tasks:
            try:
                sfm_tasks = TaskStatus.query.filter_by(
                    task_type='sfm', status='running',
                ).count()
                yolo_tasks = TaskStatus.query.filter_by(
                    task_type='yolo', status='running',
                ).count()
                active_tasks.labels(task_type='sfm').set(sfm_tasks)
                active_tasks.labels(task_type='yolo').set(yolo_tasks)
            except Exception as e:
                print(f"[METRICS] active_tasks: {e}")

        if project_count:
            try:
                project_count.set(Project.query.count())
            except Exception as e:
                print(f"[METRICS] project_count: {e}")

    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.route('/health')
def health():
    try:
        db.session.execute(text('SELECT 1'))
        return {'status': 'healthy', 'database': 'ok'}, 200
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}, 503


# ═══════════════════════════════════════════════════════════════════════
# ROUTE 2 — Dashboard (Tableau de bord)
# ═══════════════════════════════════════════════════════════════════════

@app.route('/')
@login_required
def dashboard():
    user = current_user()
    if user.role == 'admin':
        projects = Project.query.order_by(Project.updated_at.desc()).all()
        recent_analyses = Analysis.query.order_by(Analysis.created_at.desc()).limit(5).all()
    else:
        projects = Project.query.filter_by(user_id=user.id).order_by(
            Project.updated_at.desc()).all()
        recent_analyses = Analysis.query.join(Project).filter(
            Project.user_id == user.id
        ).order_by(Analysis.created_at.desc()).limit(5).all()

    total_projects = len(projects)
    danger_count   = sum(1 for p in projects if p.status == 'danger')

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
@role_required('ingenieur')
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

        # Create Project first to obtain a stable project id and predictable folder name
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
            upload_folder='',  # will be set after files are saved
            status='nouveau'
        )
        db.session.add(project)
        db.session.commit()

        # build a standard folder name using the project id and sanitized monument
        safe_monument = secure_filename((monument or f"p{project.id}").replace(' ', '_')) or f"p{project.id}"
        folder_name = f"project_{project.id}_{safe_monument}"
        upload_path = os.path.join(app.config['UPLOAD_BASE'], folder_name)
        os.makedirs(upload_path, exist_ok=True)

        saved_files = []
        for f in files:
            if f and f.filename and allowed_image(f.filename):
                filename = secure_filename(f.filename)
                dst = os.path.join(upload_path, filename)
                f.save(dst)
                saved_files.append(filename)
            else:
                flash(f'Fichier ignoré (format invalide) : {getattr(f, "filename", "")}', 'error')

        if not saved_files:
            # cleanup project row if nothing saved
            db.session.delete(project)
            db.session.commit()
            flash('Aucune image valide importée.', 'error')
            projects = Project.query.filter_by(user_id=user.id).order_by(Project.created_at.desc()).all()
            return render_template('scanner.html', user=user, projects=projects, new_project=None)

        # update project with the folder name and commit
        project.upload_folder = folder_name
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
    if user.role == 'admin':
        projects = Project.query.order_by(Project.updated_at.desc()).all()
    else:
        projects = Project.query.filter_by(user_id=user.id).order_by(
            Project.updated_at.desc()).all()
    
    # Statistiques pour la gestion
    total_projects   = len(projects)
    nouveau_count    = sum(1 for p in projects if p.status == 'nouveau')
    danger_count     = sum(1 for p in projects if p.status == 'danger')
    inprogress_count = sum(1 for p in projects if p.status == 'en_cours')
    completed_count  = sum(1 for p in projects if p.status == 'termine')

    return render_template('projects.html',
                           user=user,
                           projects=projects,
                           total_projects=total_projects,
                           nouveau_count=nouveau_count,
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
    project = check_project_access(project_id, user)
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
@role_required('ingenieur')
def delete_project():
    user = current_user()
    project_id = request.form.get('project_id', type=int)

    if not project_id:
        flash('ID projet invalide.', 'error')
        return redirect(url_for('dashboard'))

    project = Project.query.filter_by(id=project_id, user_id=user.id).first()
    if not project:
        flash('Projet introuvable ou accès refusé.', 'error')
        return redirect(url_for('dashboard'))
    import shutil
    try:
        # 1. Supprimer le dossier d'upload physique
        upload_path = os.path.join(app.config['UPLOAD_BASE'], project.upload_folder)
        if os.path.exists(upload_path):
            shutil.rmtree(upload_path, ignore_errors=True)

        # 2. Supprimer les fichiers de reconstruction (.glb)
        for recon in project.reconstructions:
            if recon.model_file:
                for base in (os.path.join(app.static_folder, 'models'), app.config['OUTPUT_FOLDER']):
                    m_path = os.path.join(base, recon.model_file)
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

    return redirect(url_for('dashboard'))


# ═══════════════════════════════════════════════════════════════════════
# ROUTE 3c — Ajouter des images à un projet existant
# ═══════════════════════════════════════════════════════════════════════
@app.route('/add_images', methods=['POST'])
@role_required('ingenieur')
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


# Removed cloud reconstruction worker — only COLMAP+Blender pipeline is supported now.





def bg_analysis(app_main, project_id, folder, task_id, infra_name=None, infra_desc=None):
    with app_main.app_context():
        try:
            # ── Helper: write progress + message + updated_at to DB ──────
            def _set_progress(pct, msg=""):
                db.session.execute(
                    db.text(
                        "UPDATE task_status SET progress = :p, message = :m, "
                        "updated_at = NOW() WHERE id = :id"
                    ),
                    {"p": pct, "m": msg, "id": task_id},
                )
                db.session.commit()

            images = [f for f in os.listdir(folder) if allowed_image(f)]
            if not images:
                raise ValueError("Aucune image à analyser.")

            remote_url = os.environ.get('REMOTE_GPU_API_URL', '').rstrip('/')
            use_remote = bool(remote_url)
            api_failed = False
            remote_results = None

            from degradation_detector import DegradationDetector
            detector = DegradationDetector()

            if use_remote:
                _set_progress(2, "Préparation des images pour l'API GPU distante...")
                try:
                    import zipfile
                    import io
                    import requests
                    
                    # Création du ZIP en mémoire des images
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for image_name in images:
                            image_path = os.path.join(folder, image_name)
                            zip_file.write(image_path, arcname=image_name)
                    zip_buffer.seek(0)
                    
                    _set_progress(5, "Envoi des images au GPU distant (Colab T4)...")
                    files = {'file': ('project_images.zip', zip_buffer, 'application/zip')}
                    
                    yolo_api_url = f"{remote_url}/api/process_yolo"
                    print(f"[BG-ANALYSIS-REMOTE] Envoi de {len(images)} images a {yolo_api_url}")
                    response = requests.post(yolo_api_url, files=files, timeout=240)
                    
                    if response.status_code == 200:
                        remote_results = response.json()
                        _set_progress(75, "Inference YOLO distante reussie. Generation locale des annotations...")
                    else:
                        raise RuntimeError(f"L'API distante a renvoye le statut {response.status_code}")
                except Exception as remote_err:
                    print(f"[BG-ANALYSIS-REMOTE] Echec de la connexion distante : {remote_err}")
                    api_failed = True
                    _set_progress(10, "Echec de l'API distante. Bascule sur le CPU local (Fallback ONNX)...")

            all_degradations = []
            first_annotated_name = None
            first_image_name = None

            if use_remote and not api_failed and remote_results:
                # ── CHEMIN REMOTE (GPU) ──
                all_degradations = remote_results.get('degradations', [])
                score_final = remote_results.get('risk_score', 0)
                severity = remote_results.get('severity', 'faible')
                status_update = remote_results.get('status_update', 'Sain')
                rec_text = remote_results.get('recommendations', '')

                # Grouper les dégradations par image pour la visualisation locale
                from collections import defaultdict
                degs_by_image = defaultdict(list)
                for d in all_degradations:
                    img_name = d.get('source_image')
                    if img_name:
                        degs_by_image[img_name].append(d)

                total_images = len(images)
                for i, image_name in enumerate(images):
                    image_path = os.path.join(folder, image_name)
                    image_arr = np.array(Image.open(image_path).convert('RGB'))

                    pct = 75 + int(((i + 1) / total_images) * 20)
                    _set_progress(pct, f"Generation du rendu visuel {i + 1}/{total_images} : {image_name}")

                    if not first_image_name:
                        first_image_name = image_name

                    image_degradations = degs_by_image[image_name]
                    viz_arr = detector.visualize(image_arr, image_degradations)
                    annotated_name = f'yolo_result_{project_id}_{image_name}_{datetime.now().strftime("%H%M%S")}.png'
                    annotated_path = os.path.join(app_main.config['YOLO_FOLDER'], annotated_name)
                    Image.fromarray(viz_arr).save(annotated_path)

                    if not first_annotated_name:
                        first_annotated_name = annotated_name
            else:
                # ── CHEMIN LOCAL (CPU Fallback avec ONNX) ──
                _set_progress(12, "Chargement des modeles IA locaux...")
                detector.build_models()
                
                counts = {
                    'fissures': 0,
                    'humidite': 0,
                    'effritement': 0
                }

                total_images = len(images)
                for i, image_name in enumerate(images):
                    image_path = os.path.join(folder, image_name)
                    image_arr = np.array(Image.open(image_path).convert('RGB'))

                    pct = 15 + int(((i) / total_images) * 80)
                    msg = f"Analyse locale {i + 1}/{total_images} : {image_name}"
                    if len(msg) > 250:
                        msg = msg[:247] + "..."
                    _set_progress(pct, msg)

                    degradations = detector.detect(image_arr)

                    if not first_image_name:
                        first_image_name = image_name

                    for d in degradations:
                        pathologie = d.get('type')
                        if pathologie in counts:
                            counts[pathologie] += 1
                        d['source_image'] = image_name

                    all_degradations.extend(degradations)

                    viz_arr = detector.visualize(image_arr, degradations)
                    annotated_name = f'yolo_result_{project_id}_{image_name}_{datetime.now().strftime("%H%M%S")}.png'
                    annotated_path = os.path.join(app_main.config['YOLO_FOLDER'], annotated_name)
                    Image.fromarray(viz_arr).save(annotated_path)

                    if not first_annotated_name:
                        first_annotated_name = annotated_name

                _set_progress(96, "Calcul local du score de risque...")
                total_defauts = sum(counts.values())
                score_structurel = (counts['fissures'] * 15) + (counts['effritement'] * 12)
                score_chimique = (counts['humidite'] * 8)
                score_brut = (score_structurel + score_chimique) / len(images) if images else 0
                score_final = min(100, round(score_brut, 2))

                recommandations_list = []
                if counts['fissures'] > 0 or counts['effritement'] > 0:
                    recommandations_list.append("Risque structurel detecte : Planifier une inspection des maconneries.")
                if counts['humidite'] > 0:
                    recommandations_list.append("Probleme d'etancheite : Traiter les infiltrations.")

                if score_final < 35:
                    severity, status_update = 'faible', 'Sain'
                    rec_text = "Entretien normal. " + " ".join(recommandations_list) if recommandations_list else "Aucune anomalie majeure."
                elif score_final <= 65:
                    severity, status_update = 'moyenne', 'Attention'
                    rec_text = "Surveillance recommandee. " + " ".join(recommandations_list)
                else:
                    severity, status_update = 'critique', 'Danger'
                    rec_text = "Alerte : Intervention urgente requise ! " + " ".join(recommandations_list)

            # Enregistrement du diagnostic complet en Base de Donnees
            ana = Analysis(
                project_id=project_id,
                source_image=first_image_name,
                annotated_image=first_annotated_name,
                risk_score=score_final,
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
            elif status_update == 'Attention':
                if project.status not in ('danger',):
                    project.status = 'en_cours'
            else:
                if project.status not in ('danger', 'en_cours'):
                    project.status = 'termine'
                
            task = TaskStatus.query.get(task_id)
            if task:
                task.status = 'completed'
                task.progress = 100

            db.session.add(ana)
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            print(f"[BG-ANALYSIS-ERROR] {e}")
            task = TaskStatus.query.get(task_id)
            if task:
                task.status = 'failed'
                task.message = str(e)[:250]
            db.session.commit()

# ═══════════════════════════════════════════════════════════════════════
# ROUTE 4 — Lancement de l'Analyse d'Images (YOLOv8 Background)
# ═══════════════════════════════════════════════════════════════════════
@app.route('/analyze_project', methods=['POST'])
@role_required('ingenieur')
def analyze_project():
    user = current_user()
    project_id = request.form.get('project_id', type=int)
    
    if not project_id:
        flash("Identifiant de projet manquant.", "error")
        return redirect(url_for('dashboard'))
        
    project = Project.query.filter_by(id=project_id, user_id=user.id).first()
    if not project:
        flash("Projet introuvable.", "error")
        return redirect(url_for('dashboard'))

    upload_path = os.path.join(app.config['UPLOAD_BASE'], project.upload_folder)
    if not os.path.exists(upload_path) or not any(allowed_image(f) for f in os.listdir(upload_path)):
        flash("Le dossier d'images est vide. Importez des photos avant l'analyse.", "error")
        return redirect(url_for('projects_management'))

    existing = TaskStatus.query.filter_by(
        project_id=project_id, task_type='yolo', status='running',
    ).first()
    if existing:
        reconcile_stale_yolo_task(existing)
        if existing.status == 'running':
            flash("Une analyse est déjà en cours pour ce projet.", "warning")
            return redirect(url_for('projects_management'))

    # Création du ticket de suivi de tâche en BD
    task = TaskStatus(
        project_id=project_id,
        task_type='yolo',
        status='running',
        progress=0
    )
    db.session.add(task)
    db.session.commit()

    # Lancement de l'analyse IA dans un thread séparé (Non-bloquant pour Flask)
    thr = threading.Thread(
        target=bg_analysis,
        args=(app, project_id, upload_path, task.id)
    )
    thr.start()

    flash("Analyse par IA des pathologies lancée en arrière-plan !", "success")
    return redirect(url_for('projects_management'))


# ═══════════════════════════════════════════════════════════════════════
# ROUTE 5 — Reconstruction 3D (COLMAP + Open3D)
# ═══════════════════════════════════════════════════════════════════════
def bg_reconstruction(app_main, project_id, input_dir, output_filename, task_id, max_px):
    """Worker COLMAP + export GLB (fichier canonique model_{project_id}.glb)."""
    with app_main.app_context():
        import shutil
        task = TaskStatus.query.get(task_id)
        try:
            def progress_updater(message, percent=None):
                print(f"[RECONSTRUCTION {task_id}] {percent}% : {message}")
                if percent is not None:
                    db.session.execute(
                        text("UPDATE task_status SET progress = :p, message = :m WHERE id = :id"),
                        {"p": percent, "m": message, "id": task_id},
                    )
                else:
                    db.session.execute(
                        text("UPDATE task_status SET message = :m WHERE id = :id"),
                        {"m": message, "id": task_id},
                    )
                db.session.commit()

            canonical_name = f'model_{project_id}.glb'
            static_dest = os.path.join(app_main.static_folder, 'models', canonical_name)
            os.makedirs(os.path.dirname(static_dest), exist_ok=True)
            output_path = os.path.join(app_main.config['OUTPUT_FOLDER'], output_filename)

            remote_url = os.environ.get('REMOTE_GPU_API_URL', '').rstrip('/')
            use_remote = bool(remote_url)
            api_failed = False
            reconstructed_remotely = False

            if use_remote:
                progress_updater("Envoi du projet au serveur GPU distant (COLMAP)...", 10)
                try:
                    import zipfile
                    import io
                    import requests
                    
                    # Zippage en mémoire des images du projet
                    zip_buffer = io.BytesIO()
                    images = [f for f in os.listdir(input_dir) if allowed_image(f)]
                    if len(images) < 3:
                        raise ValueError("Au moins 3 images nécessaires.")
                        
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for image_name in images:
                            image_path = os.path.join(input_dir, image_name)
                            zip_file.write(image_path, arcname=image_name)
                    zip_buffer.seek(0)
                    
                    files = {'file': ('colmap_project.zip', zip_buffer, 'application/zip')}
                    colmap_api_url = f"{remote_url}/api/process_colmap"
                    print(f"[BG-RECONSTRUCT-REMOTE] Envoi de {len(images)} images a {colmap_api_url}")
                    
                    # Utiliser un timeout très long pour COLMAP (30 minutes)
                    response = requests.post(colmap_api_url, files=files, timeout=1800)
                    
                    if response.status_code == 200:
                        progress_updater("Modele 3D genere sur le serveur distant. Telechargement...", 85)
                        with open(static_dest, 'wb') as f_out:
                            f_out.write(response.content)
                        shutil.copy2(static_dest, output_path)
                        reconstructed_remotely = True
                        progress_updater("Modele 3D telecharge avec succes !", 95)
                    else:
                        raise RuntimeError(f"Le serveur distant a renvoye le code statut {response.status_code}")
                except Exception as remote_err:
                    print(f"[BG-RECONSTRUCT-REMOTE] Echec reconstruction distante : {remote_err}")
                    api_failed = True
                    progress_updater("Echec de la reconstruction distante. Bascule sur le CPU local (Fallback)...", 12)

            if not reconstructed_remotely:
                # ── FALLBACK LOCAL CPU ──
                # Forcer 600px max pour éviter d'exploser la RAM du CPU local
                forced_max_px = 600
                progress_updater(f"Lancement du pipeline COLMAP local (CPU Fallback, resolution max forcee a {forced_max_px}px)...", 15)
                
                success = run_advanced_reconstruction(
                    input_dir=input_dir,
                    output_dir=static_dest,
                    progress_callback=progress_updater,
                    downscale_max_px=forced_max_px,
                )

                if not success or not os.path.isfile(static_dest) or os.path.getsize(static_dest) < 500:
                    raise RuntimeError("Pipeline SfM local echoue ou fichier GLB invalide.")

                shutil.copy2(static_dest, output_path)

            textured = reconstructed_remotely or os.path.isdir(os.path.join(input_dir, 'textured'))
            recon = Reconstruction(
                project_id=project_id,
                model_file=canonical_name,
                quality='ultra' if textured else 'high',
            )
            db.session.add(recon)

            project = Project.query.get(project_id)
            if project and project.status in ('nouveau', 'en_cours'):
                project.status = 'termine'

            if task:
                task.status = 'completed'
                task.progress = 100
                task.message = (
                    'Modele 3D texture genere a distance (GPU T4)'
                    if reconstructed_remotely
                    else 'Modele 3D genere en local (CPU Fallback a 600px)'
                )
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            print(f"[BG-RECONSTRUCT-ERROR] {e}")
            task = TaskStatus.query.get(task_id)
            if task:
                task.status = 'failed'
                task.message = str(e)[:250]
                db.session.commit()


@app.route('/reconstruct_project', methods=['POST'])
@role_required('ingenieur')
def reconstruct_project():
    user = current_user()
    project_id = request.form.get('project_id', type=int)
    max_px = request.form.get('downscale_max_px', default=1920, type=int)

    if not project_id:
        flash("ID du projet introuvable.", "error")
        return redirect(url_for('dashboard'))

    project = Project.query.filter_by(id=project_id, user_id=user.id).first()
    if not project:
        flash("Accès refusé ou projet introuvable.", "error")
        return redirect(url_for('dashboard'))

    upload_path = os.path.join(app.config['UPLOAD_BASE'], project.upload_folder)
    
    # Création du ticket de suivi SfM
    task = TaskStatus(
        project_id=project_id,
        task_type='sfm',
        status='running',
        progress=0,
        message="Initialisation du pipeline COLMAP..."
    )
    db.session.add(task)
    db.session.commit()

    output_filename = f"model_project_{project_id}_{int(datetime.utcnow().timestamp())}.glb"

    # Lancement du calcul lourd dans un thread distinct
    thr = threading.Thread(
        target=bg_reconstruction,
        args=(app, project_id, upload_path, output_filename, task.id, max_px)
    )
    thr.start()

    flash("Génération du jumeau numérique 3D lancée ! Suivez la progression sur l'interface.", "success")
    return redirect(url_for('projects_management'))


# ═══════════════════════════════════════════════════════════════════════
# ROUTE 6 — API Status (Pooling pour mettre à jour l'interface en AJAX)
# ═══════════════════════════════════════════════════════════════════════
@app.route('/api/project/<int:project_id>/tasks')
@login_required
def project_tasks_status(project_id):
    user = current_user()
    project = check_project_access(project_id, user)
    if not project:
        return {"tasks": []}, 404

    # Optionnel : réconcilier les tâches figées à chaque appel de statut
    running_tasks = TaskStatus.query.filter_by(project_id=project_id, status='running').all()
    for t in running_tasks:
        if t.task_type == 'sfm':
            reconcile_stale_sfm_task(t)

    tasks = TaskStatus.query.filter_by(project_id=project_id).order_by(TaskStatus.updated_at.desc()).all()
    
    return {
        "tasks": [{
            "id": t.id,
            "type": t.task_type,
            "status": t.status,
            "progress": t.progress,
            "message": t.message,
            "updated_at": t.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        } for t in tasks]
    }


# ═══════════════════════════════════════════════════════════════════════
# ROUTE 7 — Page Reconstruction 3D (GET) + Lancement Reconstruction (POST)
# ═══════════════════════════════════════════════════════════════════════
@app.route('/reconstruction', methods=['GET', 'POST'])
@login_required
def reconstruction():
    user = current_user()
    if user.role == 'admin':
        projects = Project.query.all()
    else:
        projects = Project.query.filter_by(user_id=user.id).all()
        
    selected_project_id = request.args.get('project_id', type=int)
    if selected_project_id:
        proj = check_project_access(selected_project_id, user)
        if not proj:
            flash("Projet introuvable ou accès refusé.", "error")
            return redirect(url_for('reconstruction'))

    if request.method == 'POST':
        if user.role == 'admin':
            flash("Actions non autorisées pour le rôle Admin.", "error")
            return redirect(url_for('reconstruction'))
            
        project_id = request.form.get('project_id', type=int)
        quality = request.form.get('quality', 'high')
        downscale_map = {'low': 1200, 'medium': 1600, 'high': 1920, 'ultra': 0}
        max_px = downscale_map.get(quality, 1600)

        if not project_id:
            flash("Sélectionnez un projet.", "error")
            return redirect(url_for('reconstruction'))

        project = Project.query.filter_by(id=project_id, user_id=user.id).first()
        if not project:
            flash("Projet introuvable.", "error")
            return redirect(url_for('reconstruction'))

        existing = TaskStatus.query.filter_by(
            project_id=project_id, task_type='sfm', status='running',
        ).first()
        if existing:
            reconcile_stale_sfm_task(existing)
        if existing and existing.status == 'running':
            flash("Une reconstruction est déjà en cours pour ce projet.", "warning")
            return redirect(url_for('reconstruction', project_id=project_id))

        upload_path = os.path.join(app.config['UPLOAD_BASE'], project.upload_folder)
        task = TaskStatus(
            project_id=project_id,
            task_type='sfm',
            status='running',
            progress=0,
            message=f"Démarrage reconstruction {quality.upper()}...",
        )
        db.session.add(task)
        db.session.commit()

        output_filename = f"model_project_{project_id}_{int(datetime.utcnow().timestamp())}.glb"
        thr = threading.Thread(
            target=bg_reconstruction,
            args=(app, project_id, upload_path, output_filename, task.id, max_px),
            daemon=True,
        )
        thr.start()

        flash("Reconstruction 3D lancée.", "success")
        return redirect(url_for('reconstruction', project_id=project_id))

    ctx = _reconstruction_page_context(user, selected_project_id)
    return render_template(
        'reconstruction.html',
        user=user,
        projects=projects,
        **ctx,
    )


# ═══════════════════════════════════════════════════════════════════════
# ROUTE 8 — Page Analyse IA (GET) + Lancement Analyse (POST)
# ═══════════════════════════════════════════════════════════════════════
@app.route('/analysis', methods=['GET', 'POST'])
@login_required
def analysis():
    user = current_user()
    if user.role == 'admin':
        projects = Project.query.all()
    else:
        projects = Project.query.filter_by(user_id=user.id).all()
        
    selected_project_id = request.args.get('project_id', type=int)
    if selected_project_id:
        proj = check_project_access(selected_project_id, user)
        if not proj:
            flash("Projet introuvable ou accès refusé.", "error")
            return redirect(url_for('analysis'))
            
    active_task = None
    result = None
    gauge = None

    if request.method == 'POST':
        if user.role == 'admin':
            flash("Actions non autorisées pour le rôle Admin.", "error")
            return redirect(url_for('analysis'))
            
        project_id = request.form.get('project_id', type=int)
        infra_name = request.form.get('infra_project_name') or None
        infra_desc = request.form.get('infra_project_desc') or None
        if not project_id:
            flash("Identifiant de projet manquant.", "error")
            return redirect(url_for('analysis'))

        project = Project.query.filter_by(id=project_id, user_id=user.id).first()
        if not project:
            flash("Projet introuvable.", "error")
            return redirect(url_for('analysis'))

        upload_path = os.path.join(app.config['UPLOAD_BASE'], project.upload_folder)
        if not os.path.exists(upload_path) or not any(allowed_image(f) for f in os.listdir(upload_path)):
            flash("Le dossier d'images est vide.", "error")
            return redirect(url_for('analysis'))

        existing = TaskStatus.query.filter_by(
            project_id=project_id, task_type='yolo', status='running',
        ).first()
        if existing:
            reconcile_stale_yolo_task(existing)
            if existing.status == 'running':
                flash("Une analyse est déjà en cours.", "warning")
                return redirect(url_for('analysis', project_id=project_id))

        task = TaskStatus(
            project_id=project_id,
            task_type='yolo',
            status='running',
            progress=0,
            message="Analyse YOLOv8 en cours...",
        )
        db.session.add(task)
        db.session.commit()

        thr = threading.Thread(
            target=bg_analysis,
            args=(app, project_id, upload_path, task.id, infra_name, infra_desc),
            daemon=True,
        )
        thr.start()

        flash("Analyse IA lancée.", "success")
        return redirect(url_for('analysis', project_id=project_id))

    if selected_project_id:
        active_task = TaskStatus.query.filter_by(
            project_id=selected_project_id, task_type='yolo',
        ).order_by(TaskStatus.started_at.desc()).first()
        if active_task:
            reconcile_stale_yolo_task(active_task)
        result = Analysis.query.filter_by(
            project_id=selected_project_id,
        ).order_by(Analysis.created_at.desc()).first()
        if result and MATPLOTLIB:
            try:
                gauge = risk_gauge_b64(float(result.risk_score))
            except Exception:
                gauge = None

    return render_template(
        'analysis.html',
        projects=projects,
        user=user,
        selected_project_id=selected_project_id,
        active_task=active_task,
        result=result,
        gauge=gauge,
    )


# ═══════════════════════════════════════════════════════════════════════
# ROUTE 9 — Page Guide Restauration
# ═══════════════════════════════════════════════════════════════════════
@app.route('/restoration-guide', methods=['GET', 'POST'])
@login_required
def restoration_guide():
    user = current_user()
    plan = None
    selected_analysis = None
    if user.role == 'admin':
        all_analyses = (
            Analysis.query.order_by(Analysis.created_at.desc()).all()
        )
    else:
        all_analyses = (
            Analysis.query.join(Project)
            .filter(Project.user_id == user.id)
            .order_by(Analysis.created_at.desc())
            .all()
        )

    if request.method == 'POST':
        analysis_id = request.form.get('analysis_id', type=int)
        if user.role == 'admin':
            ana = Analysis.query.get(analysis_id)
        else:
            ana = (
                Analysis.query.join(Project)
                .filter(Analysis.id == analysis_id, Project.user_id == user.id)
                .first()
            )
        if not ana:
            flash("Analyse introuvable.", "error")
        else:
            from reconstruction_engine import ReconstructionEngine
            plan = ReconstructionEngine().generate_restoration_plan(ana.degradations or [])
            selected_analysis = ana

    aid = request.args.get('analysis_id', type=int)
    if aid and not selected_analysis:
        if user.role == 'admin':
            selected_analysis = Analysis.query.get(aid)
        else:
            selected_analysis = (
                Analysis.query.join(Project)
                .filter(Analysis.id == aid, Project.user_id == user.id)
                .first()
            )

    return render_template(
        'restoration_guide.html',
        user=user,
        all_analyses=all_analyses,
        plan=plan,
        selected_analysis=selected_analysis,
    )


@app.route('/generate-pdf/<int:analysis_id>')
@login_required
def generate_pdf(analysis_id):
    user = current_user()
    ana = (
        Analysis.query.join(Project)
        .filter(Analysis.id == analysis_id, Project.user_id == user.id)
        .first_or_404()
    )
    from reconstruction_engine import ReconstructionEngine
    from report_generator import generate_report

    plan = ReconstructionEngine().generate_restoration_plan(ana.degradations or [])
    pdf_name = f"rapport_{ana.project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf_path = os.path.join(app.config['OUTPUT_FOLDER'], pdf_name)
    generate_report(pdf_path, user.name, ana.project, ana, plan=plan)
    return send_file(pdf_path, as_attachment=True, download_name=pdf_name)


# ═══════════════════════════════════════════════════════════════════════
# ROUTE 10 — Page Impact Urbain
# ═══════════════════════════════════════════════════════════════════════
@app.route('/urban-assessment', methods=['GET', 'POST'])
@login_required
def urban_assessment():
    user = current_user()
    projects = Project.query.filter_by(user_id=user.id).all()
    selected_project_id = request.args.get('project_id', type=int)
    result = None
    assessments = []

    if request.method == 'POST':
        project_id = request.form.get('project_id', type=int)
        proj_type = request.form.get('type', 'route')
        distance_m = request.form.get('distance_m', 100, type=float)
        intensity = request.form.get('vibration_intensity', 'medium')
        project = Project.query.filter_by(id=project_id, user_id=user.id).first()
        if not project:
            flash("Projet introuvable.", "error")
        else:
            from reconstruction_engine import ReconstructionEngine
            engine = ReconstructionEngine()
            degs = project.latest_analysis.degradations if project.latest_analysis else None
            result = engine.calculate_vibration_impact(distance_m, proj_type, intensity, degs)
            result['type_label'] = proj_type.capitalize()
            result['project_name'] = project.monument
            up = UrbanProject(
                project_id=project.id,
                type=proj_type,
                distance_m=distance_m,
                vibration_intensity=intensity,
                v_impact=result.get('v_impact'),
                risk_label=result.get('risk_label'),
                recommendations='\n'.join(result.get('recommendations', [])),
            )
            db.session.add(up)
            db.session.commit()
            selected_project_id = project_id

    if selected_project_id:
        assessments = (
            UrbanProject.query.filter_by(project_id=selected_project_id)
            .order_by(UrbanProject.created_at.desc())
            .all()
        )

    return render_template(
        'urban_assessment.html',
        projects=projects,
        user=user,
        selected_project_id=selected_project_id,
        result=result,
        assessments=assessments,
    )


@app.route('/api/task_status/<int:task_id>')
@login_required
def api_task_status(task_id):
    # Expire session cache so we always read fresh values from DB
    # (background thread writes via raw SQL, SQLAlchemy won't auto-refresh)
    db.session.expire_all()
    task = TaskStatus.query.get(task_id)
    if not task:
        return {"status": "unknown", "progress": 0, "message": ""}
    if task.task_type == 'sfm':
        reconcile_stale_sfm_task(task)
    elif task.task_type == 'yolo':
        reconcile_stale_yolo_task(task)
    return {
        "status": task.status,
        "progress": task.progress or 0,
        "message": task.message or "",
    }



@app.route('/api/task_status/<int:task_id>/cancel', methods=['POST'])
@role_required('ingenieur')
def api_cancel_task(task_id):
    task = TaskStatus.query.get(task_id)
    if not task:
        return {"status": "unknown"}, 404
    if task.status == 'running':
        task.status = 'failed'
        task.message = "Reconstruction annulée par l'utilisateur."
        db.session.commit()
    return {"status": task.status, "message": task.message}


@app.route('/project/<int:project_id>')
@app.route('/project/<int:project_id>/images')
@login_required
def project_images(project_id):
    user = current_user()
    project = Project.query.filter_by(id=project_id, user_id=user.id).first_or_404()
    upload_path = os.path.join(app.config['UPLOAD_BASE'], project.upload_folder)
    photos = []
    if os.path.isdir(upload_path):
        photos = sorted(
            f for f in os.listdir(upload_path) if allowed_image(f)
        )
    active_rec = TaskStatus.query.filter_by(
        project_id=project.id, task_type='sfm', status='running',
    ).first()
    if active_rec:
        reconcile_stale_sfm_task(active_rec)
    return render_template(
        'project_detail.html',
        user=user,
        project=project,
        photos=photos,
        active_rec=active_rec if active_rec and active_rec.status == 'running' else None,
    )


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/favicon.png')
def favicon_png():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.png', mimetype='image/png')


@app.errorhandler(404)
def not_found(e):
    if 'user_id' in session:
        flash("Page introuvable.", "error")
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    if 'user_id' in session:
        flash("Erreur interne du serveur. Veuillez réessayer.", "error")
        return redirect(url_for('dashboard'))
    flash("Erreur interne du serveur.", "error")
    return redirect(url_for('login'))


# ═══════════════════════════════════════════════════════════════════════
# ROUTE 11 — Alias routes pour compatibilité
# ═══════════════════════════════════════════════════════════════════════
@app.route('/scanner-construction-3d')
@login_required
def scanner_construction():
    return redirect(url_for('scanner'))

@app.route('/analyse-ia')
@login_required
def analyse_ia_alias():
    return redirect(url_for('analysis'))

@app.route('/guide-restauration')
@login_required
def guide_restauration_alias():
    return redirect(url_for('restoration_guide'))

@app.route('/impact-urbain')
@login_required
def impact_urbain_alias():
    return redirect(url_for('urban_assessment'))


# ═══════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE DE L'APPLICATION
# ═══════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    with app.app_context():
        # Création des tables de la base de données si elles n'existent pas
        db.create_all()
        
        # Seed test users
        try:
            admin_user = User.query.filter_by(email='admin@asl3d.com').first()
            if not admin_user:
                admin_user = User(name='Administrateur Test', email='admin@asl3d.com', role='admin')
                admin_user.set_password('admin123')
                db.session.add(admin_user)
                print("[SEED] Utilisateur Admin créé.")
            else:
                # S'assurer que le rôle est bien admin
                admin_user.role = 'admin'
            
            engineer_user = User.query.filter_by(email='engineer@asl3d.com').first()
            if not engineer_user:
                engineer_user = User(name='Ingénieur Test', email='engineer@asl3d.com', role='ingenieur')
                engineer_user.set_password('engineer123')
                db.session.add(engineer_user)
                print("[SEED] Utilisateur Ingénieur créé.")
            else:
                # S'assurer que le rôle est bien ingénieur
                engineer_user.role = 'ingenieur'
                
            db.session.commit()
            print("[SEED] Seeding des utilisateurs complété avec succès.")
        except Exception as e:
            db.session.rollback()
            print(f"[SEED] Échec du seeding : {e}")

        # Copie automatique du logo temple s'il existe
        try:
            import shutil
            src_logo = r'C:\Users\HP\.gemini\antigravity\brain\ffe089df-38c7-413c-a883-6074cdd1bfef\temple_logo_1781271886938.png'
            if os.path.exists(src_logo):
                shutil.copy2(src_logo, os.path.join(app.static_folder, 'favicon.png'))
                shutil.copy2(src_logo, os.path.join(app.static_folder, 'favicon.ico'))
                print("[FAVICON] Nouveau logo temple copie avec succes.")
        except Exception as e:
            print(f"[FAVICON] Echec de la copie : {e}")
    
    # Lancement de l'application Flask
    use_reloader = os.getenv('FLASK_USE_RELOADER', '0') == '1'
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=use_reloader)
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from models import db, Pouzivatel, Skupina
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

import os

bp = Blueprint('main', __name__)

import re

@bp.app_template_filter('youtube_id')
def youtube_id_filter(url):
    """Získa ID z YouTube URL"""
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else ""


pyALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ✅ HLAVNÁ STRÁNKA
@bp.route('/')
def index():
    print(">>> routes.py - index <<<")
    return render_template('index.html', skupina=None)


# ✅ PRIHLÁSENIE
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        heslo = request.form['heslo']

        pouzivatel = Pouzivatel.query.filter_by(email=email).first()

        if not pouzivatel:
            flash("Účet s týmto e-mailom neexistuje ❌", "danger")
            return redirect(url_for('main.index', zobraz_formular='prihlasenie'))

        if not check_password_hash(pouzivatel.heslo, heslo):
            flash("Nesprávne heslo ❌", "danger")
            return redirect(url_for('main.index', zobraz_formular='prihlasenie'))

        login_user(pouzivatel)
        session['user_id'] = pouzivatel.id
        session['prezyvka'] = pouzivatel.prezyvka
        flash(f"Vitaj späť, {pouzivatel.prezyvka} 👋", "success")
        return redirect(url_for('uzivatel.profil'))

    return redirect(url_for('main.index', zobraz_formular='prihlasenie'))

# ✅ ODHLÁSENIE
@bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash("Bol si odhlásený", "info")
    return redirect(url_for('main.index'))


# ✅ NAHRÁVANIE PROFILOVEJ FOTKY
@bp.route('/upload_fotka', methods=['POST'])
@login_required
def upload_fotka():
    file = request.files.get('profil_fotka')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        current_user.profil_fotka = filename
        db.session.commit()

        flash("Fotka bola úspešne nahratá", "success")
    else:
        flash("Nepodarilo sa nahrať fotku", "danger")

    return redirect(url_for('uzivatel.profil'))

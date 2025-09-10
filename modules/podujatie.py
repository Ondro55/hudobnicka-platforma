# modules/podujatie.py
import os, time
from uuid import uuid4
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import db, Podujatie

ALLOWED_EXT = {'png','jpg','jpeg','webp','gif'}  # SVG radšej neuploadovať od userov

podujatie_bp = Blueprint('podujatie', __name__, url_prefix='/podujatia')

def can_create_events(user) -> bool:
    # teraz len IČO alebo admin; neskôr pridáme PRO (plan=='pro' alebo is_vip)
    return bool(user.is_authenticated and (user.typ_subjektu == 'ico' or user.is_admin))

def _upload_dir():
    p = os.path.join(current_app.root_path, 'static', 'podujatia')
    os.makedirs(p, exist_ok=True)
    return p

def _save_one_photo(file, prefix='evt'):
    if not file or file.filename == '':
        return None
    name = secure_filename(file.filename)
    ext = name.rsplit('.',1)[-1].lower() if '.' in name else ''
    if ext not in ALLOWED_EXT:
        return None
    fname = f"{prefix}_{int(time.time())}_{uuid4().hex[:6]}.{ext}"
    dest = os.path.join(_upload_dir(), fname)
    file.save(dest)
    return fname

# modules/podujatie.py (dopln importy hore)
from datetime import datetime, timedelta

@podujatie_bp.route('/moje', methods=['GET'])
@login_required
def moje():
    if not can_create_events(current_user):
        flash("Podujatia sú aktuálne dostupné len pre firemné (IČO) účty. Čoskoro aj pre PRO.", "warning")
        return redirect(url_for('uzivatel.profil'))

    threshold = datetime.utcnow() - timedelta(days=1)

    aktivne = (Podujatie.query
               .filter_by(pouzivatel_id=current_user.id)
               .filter(Podujatie.start_dt >= threshold)
               .order_by(Podujatie.start_dt.asc())
               .all())

    archiv = (Podujatie.query
              .filter_by(pouzivatel_id=current_user.id)
              .filter(Podujatie.start_dt < threshold)
              .order_by(Podujatie.start_dt.desc())
              .all())

    return render_template('moje_podujatie.html', aktivne=aktivne, archiv=archiv)

# --- UPRAVIŤ / UPDATE ---
@podujatie_bp.route('/<int:id>/edit', methods=['GET'])
@login_required
def edit(id):
    e = Podujatie.query.get_or_404(id)
    if e.pouzivatel_id != current_user.id and not current_user.is_admin:
        abort(403)
    return render_template('podujatie_edit.html', e=e)

@podujatie_bp.route('/<int:id>/update', methods=['POST'])
@login_required
def update(id):
    e = Podujatie.query.get_or_404(id)
    if e.pouzivatel_id != current_user.id and not current_user.is_admin:
        abort(403)

    nazov = (request.form.get('nazov') or '').strip()
    organizator = (request.form.get('organizator') or '').strip()
    miesto = (request.form.get('miesto') or '').strip()
    d = (request.form.get('datum') or '').strip()
    t = (request.form.get('cas') or '').strip()
    popis = (request.form.get('popis') or '').strip()

    if not nazov or not d or not t:
        flash("Vyplň názov, dátum aj čas.", "warning")
        return redirect(url_for('podujatie.edit', id=e.id))

    try:
        start_dt = datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
    except ValueError:
        flash("Neplatný formát dátumu/času.", "danger")
        return redirect(url_for('podujatie.edit', id=e.id))

    e.nazov = nazov
    e.organizator = organizator
    e.miesto = miesto
    e.start_dt = start_dt
    e.popis = popis

    db.session.commit()
    flash("Podujatie uložené.", "success")
    return redirect(url_for('podujatie.moje'))

@podujatie_bp.route('/vytvor', methods=['POST'])
@login_required
def vytvor():
    if not can_create_events(current_user):
        abort(403)

    nazov = (request.form.get('nazov') or '').strip()
    organizator = (request.form.get('organizator') or '').strip()
    miesto = (request.form.get('miesto') or '').strip()
    d = (request.form.get('datum') or '').strip()      # 'YYYY-MM-DD'
    t = (request.form.get('cas') or '').strip()        # 'HH:MM'
    popis = (request.form.get('popis') or '').strip()

    if not nazov or not d or not t:
        flash("Vyplň názov, dátum aj čas.", "warning")
        return redirect(url_for('podujatie.moje'))

    try:
        start_dt = datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
    except ValueError:
        flash("Neplatný formát dátumu/času.", "danger")
        return redirect(url_for('podujatie.moje'))

    evt = Podujatie(
        pouzivatel_id=current_user.id,
        nazov=nazov,
        organizator=organizator or (current_user.organizacia_nazov if current_user.typ_subjektu=='ico' else None),
        miesto=miesto,
        start_dt=start_dt,
        popis=popis
    )

    # voliteľný upload hneď pri vytvorení (jedna fotka)
    file = request.files.get('foto')
    if file:
        fname = _save_one_photo(file, prefix='evt')
        if not fname:
            flash("Nepovolený formát fotky. Povolené: png, jpg, jpeg, webp, gif.", "warning")
        else:
            evt.foto_nazov = fname

    db.session.add(evt)
    db.session.commit()
    flash("Podujatie vytvorené.", "success")
    return redirect(url_for('podujatie.moje'))

@podujatie_bp.route('/<int:id>/upload_foto', methods=['POST'])
@login_required
def upload_foto(id):
    evt = Podujatie.query.get_or_404(id)
    if evt.pouzivatel_id != current_user.id and not current_user.is_admin:
        abort(403)

    file = request.files.get('foto')
    if not file:
        flash("Nevybral si žiadny súbor.", "warning")
        return redirect(url_for('podujatie.moje'))

    # zmaž starú (ak bola)
    if evt.foto_nazov:
        old = os.path.join(_upload_dir(), evt.foto_nazov)
        if os.path.exists(old):
            try: os.remove(old)
            except Exception: pass

    fname = _save_one_photo(file, prefix=f"evt{evt.id}")
    if not fname:
        flash("Nepovolený formát fotky.", "warning")
    else:
        evt.foto_nazov = fname
        db.session.commit()
        flash("Fotka podujatia aktualizovaná.", "success")

    return redirect(url_for('podujatie.moje'))

@podujatie_bp.route('/<int:id>/zmaz_foto', methods=['POST'])
@login_required
def zmaz_foto(id):
    evt = Podujatie.query.get_or_404(id)
    if evt.pouzivatel_id != current_user.id and not current_user.is_admin:
        abort(403)
    if evt.foto_nazov:
        path = os.path.join(_upload_dir(), evt.foto_nazov)
        if os.path.exists(path):
            try: os.remove(path)
            except Exception: pass
        evt.foto_nazov = None
        db.session.commit()
        flash("Fotka podujatia odstránená.", "info")
    return redirect(url_for('podujatie.moje'))

@podujatie_bp.route('/<int:id>/zmaz', methods=['POST'])
@login_required
def zmaz(id):
    evt = Podujatie.query.get_or_404(id)
    if evt.pouzivatel_id != current_user.id and not current_user.is_admin:
        abort(403)

    # zmaž fotku (ak je)
    if evt.foto_nazov:
        path = os.path.join(_upload_dir(), evt.foto_nazov)
        if os.path.exists(path):
            try: os.remove(path)
            except Exception: pass

    db.session.delete(evt)
    db.session.commit()
    flash("Podujatie zmazané.", "info")
    return redirect(url_for('podujatie.moje'))

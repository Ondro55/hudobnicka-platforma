# modules/reklama.py
import os, time
from uuid import uuid4
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import db, Reklama

reklama_bp = Blueprint('reklama', __name__, url_prefix='/reklamy')

ALLOWED = {'png','jpg','jpeg','webp','gif'}

def can_ads(user):
    return bool(user.is_authenticated and (user.typ_subjektu == 'ico' or user.is_admin))

def _dir():
    p = os.path.join(current_app.root_path, 'static', 'reklamy')
    os.makedirs(p, exist_ok=True); return p

def _save(file, prefix='ad'):
    if not file or file.filename == '': return None
    name = secure_filename(file.filename)
    ext = name.rsplit('.',1)[-1].lower() if '.' in name else ''
    if ext not in ALLOWED: return None
    fname = f"{prefix}_{int(time.time())}_{uuid4().hex[:6]}.{ext}"
    file.save(os.path.join(_dir(), fname))
    return fname

@reklama_bp.route('/moje', methods=['GET'])
@login_required
def moje():
    if not can_ads(current_user):
        flash("Reklamy sú dostupné len pre IČO účty (a admin).", "warning")
        return redirect(url_for('uzivatel.profil'))

    ads = (Reklama.query
           .filter_by(pouzivatel_id=current_user.id)
           .order_by(Reklama.created_at.desc())
           .all())
    return render_template('moje_reklamy.html', reklamy=ads)

@reklama_bp.route('/vytvor', methods=['POST'])
@login_required
def vytvor():
    if not can_ads(current_user): abort(403)

    nazov = (request.form.get('nazov') or '').strip()
    text  = (request.form.get('text') or '').strip()
    url   = (request.form.get('url') or '').strip()
    start = (request.form.get('start') or '').strip()
    end   = (request.form.get('end') or '').strip()
    is_top = bool(request.form.get('is_top'))

    if not nazov:
        flash("Zadaj názov reklamy.", "warning"); return redirect(url_for('reklama.moje'))

    try:
        start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%M") if start else datetime.utcnow()
        end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M") if end else None
    except ValueError:
        flash("Neplatný dátum/čas.", "danger"); return redirect(url_for('reklama.moje'))

    ad = Reklama(
        pouzivatel_id=current_user.id,
        nazov=nazov, text=text, url=url,
        start_dt=start_dt, end_dt=end_dt,
        is_top=is_top
    )

    f = request.files.get('foto')
    if f:
        fname = _save(f, prefix='ad')
        if not fname: flash("Nepovolený formát obrázka.", "warning")
        else: ad.foto_nazov = fname

    db.session.add(ad); db.session.commit()
    flash("Reklama vytvorená.", "success")
    return redirect(url_for('reklama.moje'))

@reklama_bp.route('/<int:id>/edit', methods=['GET','POST'])
@login_required
def edit(id):
    ad = Reklama.query.get_or_404(id)
    if ad.pouzivatel_id != current_user.id and not current_user.is_admin: abort(403)

    if request.method == 'POST':
        nazov = (request.form.get('nazov') or '').strip()
        text  = (request.form.get('text') or '').strip()
        url   = (request.form.get('url') or '').strip()
        start = (request.form.get('start') or '').strip()
        end   = (request.form.get('end') or '').strip()
        is_top = bool(request.form.get('is_top'))

        if not nazov:
            flash("Názov je povinný.", "warning"); return redirect(url_for('reklama.edit', id=ad.id))

        try:
            ad.start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%M") if start else ad.start_dt
            ad.end_dt   = datetime.strptime(end, "%Y-%m-%dT%H:%M") if end else None
        except ValueError:
            flash("Neplatný dátum/čas.", "danger"); return redirect(url_for('reklama.edit', id=ad.id))

        ad.nazov = nazov; ad.text = text; ad.url = url; ad.is_top = is_top
        db.session.commit()
        flash("Uložené.", "success")
        return redirect(url_for('reklama.moje'))

    return render_template('reklama_edit.html', ad=ad)

@reklama_bp.route('/<int:id>/upload_foto', methods=['POST'])
@login_required
def upload_foto(id):
    ad = Reklama.query.get_or_404(id)
    if ad.pouzivatel_id != current_user.id and not current_user.is_admin: abort(403)
    f = request.files.get('foto')
    if not f: flash("Nevybraný súbor.", "warning"); return redirect(url_for('reklama.moje'))

    if ad.foto_nazov:
        old = os.path.join(_dir(), ad.foto_nazov)
        if os.path.exists(old):
            try: os.remove(old)
            except Exception: pass

    fname = _save(f, prefix=f"ad{ad.id}")
    if not fname: flash("Nepovolený formát.", "warning")
    else:
        ad.foto_nazov = fname; db.session.commit(); flash("Obrázok aktualizovaný.", "success")
    return redirect(url_for('reklama.moje'))

@reklama_bp.route('/<int:id>/zmaz_foto', methods=['POST'])
@login_required
def zmaz_foto(id):
    ad = Reklama.query.get_or_404(id)
    if ad.pouzivatel_id != current_user.id and not current_user.is_admin: abort(403)
    if ad.foto_nazov:
        p = os.path.join(_dir(), ad.foto_nazov)
        if os.path.exists(p):
            try: os.remove(p)
            except Exception: pass
        ad.foto_nazov = None; db.session.commit()
        flash("Obrázok odstránený.", "info")
    return redirect(url_for('reklama.moje'))

@reklama_bp.route('/<int:id>/zmaz', methods=['POST'])
@login_required
def zmaz(id):
    ad = Reklama.query.get_or_404(id)
    if ad.pouzivatel_id != current_user.id and not current_user.is_admin: abort(403)
    if ad.foto_nazov:
        p = os.path.join(_dir(), ad.foto_nazov)
        if os.path.exists(p):
            try: os.remove(p)
            except Exception: pass
    db.session.delete(ad); db.session.commit()
    flash("Reklama zmazaná.", "info")
    return redirect(url_for('reklama.moje'))

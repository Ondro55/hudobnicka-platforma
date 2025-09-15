# modules/podujatie.py
import os, time
from uuid import uuid4
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import db, Podujatie

ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'webp', 'gif'}  # SVG radšej nie (bezpečnosť)

podujatie_bp = Blueprint('podujatie', __name__, url_prefix='/podujatia')


# ====== P R Á V A ======
def can_create_events(user) -> bool:
    # teraz len IČO alebo admin; neskôr otvoríme aj pre PRO/VIP
    return bool(user.is_authenticated and (user.typ_subjektu == 'ico' or user.is_admin))


# ====== P O M O C N Í C I ======
def _upload_dir():
    p = os.path.join(current_app.root_path, 'static', 'podujatia')
    os.makedirs(p, exist_ok=True)
    return p

def _save_one_photo(file, prefix='evt'):
    if not file or file.filename == '':
        return None
    name = secure_filename(file.filename)
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    if ext not in ALLOWED_EXT:
        return None
    fname = f"{prefix}_{int(time.time())}_{uuid4().hex[:6]}.{ext}"
    dest = os.path.join(_upload_dir(), fname)
    file.save(dest)
    return fname

def _parse_dt(d_str: str, t_str: str) -> datetime | None:
    """Očakáva d='YYYY-MM-DD', t='HH:MM'. Vráti datetime alebo None."""
    d_str = (d_str or '').strip()
    t_str = (t_str or '').strip()
    if not d_str or not t_str:
        return None
    try:
        return datetime.strptime(f"{d_str} {t_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None


# ====== V Z H Ľ A D  (CREATE + LIST) ======
@podujatie_bp.route('/moje', methods=['GET'])
@login_required
def moje():
    """Stránka s formulárom + živým náhľadom (šablóna podujatie_moje.html) a dátami na zoznam aktívnych/archívnych."""
    if not can_create_events(current_user):
        flash("Podujatia sú aktuálne dostupné len pre firemné (IČO) účty. Čoskoro aj pre PRO.", "warning")
        return redirect(url_for('uzivatel.profil'))

    threshold = datetime.utcnow() - timedelta(days=1)

    aktivne = (
        Podujatie.query
        .filter_by(pouzivatel_id=current_user.id)
        .filter(Podujatie.start_dt >= threshold)
        .order_by(Podujatie.start_dt.asc())
        .all()
    )

    archiv = (
        Podujatie.query
        .filter_by(pouzivatel_id=current_user.id)
        .filter(Podujatie.start_dt < threshold)
        .order_by(Podujatie.start_dt.desc())
        .all()
    )

    # Šablóna očakáva `event` (None pri vytváraní) a `action` pre <form action=...>
    return render_template(
        'moje_podujatie.html',
        event=None,
        action=url_for('podujatie.vytvor'),
        aktivne=aktivne,
        archiv=archiv
    )


# ====== E D I T ======
@podujatie_bp.route('/<int:id>/edit', methods=['GET'])
@login_required
def edit(id):
    e = Podujatie.query.get_or_404(id)
    if e.pouzivatel_id != current_user.id and not current_user.is_admin:
        abort(403)

    threshold = datetime.utcnow() - timedelta(days=1)
    aktivne = (
        Podujatie.query
        .filter_by(pouzivatel_id=current_user.id)
        .filter(Podujatie.start_dt >= threshold)
        .order_by(Podujatie.start_dt.asc())
        .all()
    )
    archiv = (
        Podujatie.query
        .filter_by(pouzivatel_id=current_user.id)
        .filter(Podujatie.start_dt < threshold)
        .order_by(Podujatie.start_dt.desc())
        .all()
    )

    return render_template(
        'moje_podujatie.html',     # rovnaká šablóna, len predvyplnená
        event=e,
        action=url_for('podujatie.update', id=e.id),
        aktivne=aktivne,
        archiv=archiv
    )


# ====== C R E A T E  (publikovať hneď) ======
@podujatie_bp.route('/vytvor', methods=['POST'])
@login_required
def vytvor():
    if not can_create_events(current_user):
        abort(403)

    nazov        = (request.form.get('nazov') or '').strip()
    organizator  = (request.form.get('organizator') or '').strip()
    miesto       = (request.form.get('miesto') or '').strip()
    d            = (request.form.get('datum') or '').strip()        # 'YYYY-MM-DD'
    t            = (request.form.get('cas_od') or request.form.get('cas') or '').strip()  # preferuj cas_od
    popis        = (request.form.get('popis') or '').strip()

    if not nazov or not d or not t:
        flash("Vyplň názov, dátum aj začiatok.", "warning")
        return redirect(url_for('podujatie.moje'))

    start_dt = _parse_dt(d, t)
    if not start_dt:
        flash("Neplatný formát dátumu/času.", "danger")
        return redirect(url_for('podujatie.moje'))

    evt = Podujatie(
        pouzivatel_id=current_user.id,
        nazov=nazov,
        organizator=organizator or (current_user.organizacia_nazov if current_user.typ_subjektu == 'ico' else None),
        miesto=miesto,
        start_dt=start_dt,
        popis=popis
    )

    # Ak má model stĺpec `zverejnit`, hneď publikujeme
    if hasattr(evt, 'zverejnit'):
        setattr(evt, 'zverejnit', True)

    # voliteľná fotka
    file = request.files.get('foto')
    if file:
        fname = _save_one_photo(file, prefix='evt')
        if not fname:
            flash("Nepovolený formát fotky. Povolené: png, jpg, jpeg, webp, gif.", "warning")
        else:
            evt.foto_nazov = fname

    # voliteľné: vstupné (uložíme len ak model má taký stĺpec)
    vst = (request.form.get('vstupne') or '').replace(',', '.').strip()
    if vst:
        try:
            vst_val = float(vst)
            if hasattr(evt, 'vstupne'):
                setattr(evt, 'vstupne', vst_val)
        except ValueError:
            pass

    db.session.add(evt)
    db.session.commit()
    flash("Podujatie vytvorené a zverejnené.", "success")
    return redirect(url_for('podujatie.moje'))


# ====== U P D A T E  (publikované ostáva publikované) ======
@podujatie_bp.route('/<int:id>/update', methods=['POST'])
@login_required
def update(id):
    e = Podujatie.query.get_or_404(id)
    if e.pouzivatel_id != current_user.id and not current_user.is_admin:
        abort(403)

    nazov        = (request.form.get('nazov') or '').strip()
    organizator  = (request.form.get('organizator') or '').strip()
    miesto       = (request.form.get('miesto') or '').strip()
    d            = (request.form.get('datum') or '').strip()
    t            = (request.form.get('cas_od') or request.form.get('cas') or '').strip()
    popis        = (request.form.get('popis') or '').strip()

    if not nazov or not d or not t:
        flash("Vyplň názov, dátum aj začiatok.", "warning")
        return redirect(url_for('podujatie.edit', id=e.id))

    start_dt = _parse_dt(d, t)
    if not start_dt:
        flash("Neplatný formát dátumu/času.", "danger")
        return redirect(url_for('podujatie.edit', id=e.id))

    e.nazov       = nazov
    e.organizator = organizator or e.organizator
    e.miesto      = miesto
    e.start_dt    = start_dt
    e.popis       = popis

    # voliteľné: vstupné (ak existuje stĺpec)
    vst = (request.form.get('vstupne') or '').replace(',', '.').strip()
    if hasattr(e, 'vstupne'):
        if vst:
            try:
                e.vstupne = float(vst)
            except ValueError:
                pass
        else:
            e.vstupne = None

    db.session.commit()
    flash("Podujatie uložené.", "success")
    return redirect(url_for('podujatie.moje'))


# ====== F O T K A ======
@podujatie_bp.route('/<int:id>/upload_foto', methods=['POST'])
@login_required
def upload_foto(id):
    e = Podujatie.query.get_or_404(id)
    if e.pouzivatel_id != current_user.id and not current_user.is_admin:
        abort(403)

    file = request.files.get('foto')
    if not file:
        flash("Nevybral si žiadny súbor.", "warning")
        return redirect(url_for('podujatie.edit', id=e.id))

    # zmaž starú (ak bola)
    if e.foto_nazov:
        old = os.path.join(_upload_dir(), e.foto_nazov)
        if os.path.exists(old):
            try:
                os.remove(old)
            except Exception:
                pass

    fname = _save_one_photo(file, prefix=f"evt{e.id}")
    if not fname:
        flash("Nepovolený formát fotky.", "warning")
    else:
        e.foto_nazov = fname
        db.session.commit()
        flash("Fotka podujatia aktualizovaná.", "success")

    return redirect(url_for('podujatie.edit', id=e.id))


@podujatie_bp.route('/<int:id>/zmaz_foto', methods=['POST'])
@login_required
def zmaz_foto(id):
    e = Podujatie.query.get_or_404(id)
    if e.pouzivatel_id != current_user.id and not current_user.is_admin:
        abort(403)

    if e.foto_nazov:
        path = os.path.join(_upload_dir(), e.foto_nazov)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
        e.foto_nazov = None
        db.session.commit()
        flash("Fotka podujatia odstránená.", "info")

    return redirect(url_for('podujatie.edit', id=e.id))


# ====== Z M A Z A Ť  P O D U J A T I E ======
@podujatie_bp.route('/<int:id>/zmaz', methods=['POST'])
@login_required
def zmaz(id):
    e = Podujatie.query.get_or_404(id)
    if e.pouzivatel_id != current_user.id and not current_user.is_admin:
        abort(403)

    # zmaž fotku (ak existuje)
    if e.foto_nazov:
        path = os.path.join(_upload_dir(), e.foto_nazov)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    db.session.delete(e)
    db.session.commit()
    flash("Podujatie zmazané.", "info")
    return redirect(url_for('podujatie.moje'))

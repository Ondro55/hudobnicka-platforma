# modules/inzerat.py

import os
import uuid
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps

from models import db, Inzerat, FotoInzerat, Mesto, Report
try:
    # ak utils/moderation nemáš, nevadí – len preskočíme
    from utils.moderation import auto_moderate_text
except Exception:
    auto_moderate_text = None

# --- Kategórie pre inzerát (zostávajú tvoje) ---
KATEGORIE = [
    "Klávesy", "Gitary", "Bicie", "Dychové nástroje", "Sláčikové nástroje",
    "Ozvučenie", "Noty a knihy", "Doplnky", "Ostatné"
]

inzerat = Blueprint('inzerat', __name__)

ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.webp'}

def _upload_dir() -> str:
    """Cesta z configu + istota, že priečinok existuje."""
    folder = current_app.config.get('UPLOAD_FOLDER_INZERAT') or os.path.join(current_app.root_path, 'static', 'galeria_inzerat')
    os.makedirs(folder, exist_ok=True)
    return folder

def _save_image(file_storage) -> str | None:
    """Ulož fotku, vráť názov súboru alebo None."""
    if not file_storage or not file_storage.filename:
        return None
    base = secure_filename(file_storage.filename)
    _, ext = os.path.splitext(base)
    ext = ext.lower()
    if ext not in ALLOWED_EXT:
        return None

    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(_upload_dir(), filename)

    try:
        img = Image.open(file_storage)
        # oprav orientáciu, zmenši náhľad (max 800 px dlhšia strana)
        img = ImageOps.exif_transpose(img)
        img.thumbnail((800, 800))
        # webp/jpg/png zachováme podľa prípony
        img.save(path)
        return filename
    except Exception as e:
        current_app.logger.warning(f"Chyba pri ukladaní fotky: {e}")
        return None

def _parse_float(val: str | None) -> float | None:
    if not val:
        return None
    try:
        return float(val.replace(',', '.').strip())
    except Exception:
        return None

# 💾 MÔJ BAZÁR – zobrazenie + pridanie cez POST
@inzerat.route('/moj-bazar', methods=['GET', 'POST'])
@login_required
def moj_bazar():
    if request.method == 'POST':
        # texty
        typ       = (request.form.get('typ') or '').strip() or None
        kategoria = (request.form.get('kategoria') or '').strip() or None
        doprava   = (request.form.get('doprava') or '').strip() or None
        popis     = (request.form.get('popis') or '').strip() or None

        # čísla
        cena     = _parse_float(request.form.get('cena'))
        mesto_id = request.form.get('mesto_id', type=int)

        novy = Inzerat(
            typ=typ,
            kategoria=kategoria,
            doprava=doprava,
            cena=cena,
            popis=popis,
            mesto_id=mesto_id,
            pouzivatel_id=current_user.id,
            datum=datetime.utcnow(),
        )
        db.session.add(novy)
        db.session.commit()

        # 📷 Fotky – max 5
        ulozene = 0
        for fs in request.files.getlist('fotky'):
            if ulozene >= 5:
                break
            filename = _save_image(fs)
            if filename:
                db.session.add(FotoInzerat(nazov_suboru=filename, inzerat_id=novy.id))
                ulozene += 1
        if ulozene:
            db.session.commit()

        # 🔎 Jemná automoderácia – len označí report (ak máš utils.moderation)
        if auto_moderate_text:
            try:
                res = auto_moderate_text(f"{typ or ''} {kategoria or ''}\n{popis or ''}")
                if res.get("flag"):
                    db.session.add(Report(
                        reporter_id=current_user.id,
                        entity_type="inzerat",
                        entity_id=novy.id,
                        reason=res.get("reason", "nevhodny_obsah"),
                        details=res.get("note") or "automatická kontrola",
                        status="open",
                    ))
                    db.session.commit()
                    flash("Inzerát uložený a označený na kontrolu.", "warning")
                else:
                    flash("✅ Inzerát bol úspešne pridaný.", "success")
            except Exception:
                flash("✅ Inzerát bol úspešne pridaný.", "success")
        else:
            flash("✅ Inzerát bol úspešne pridaný.", "success")

        return redirect(url_for('inzerat.moj_bazar'))

    # GET
    moje_inzeraty = (Inzerat.query
                     .filter_by(pouzivatel_id=current_user.id)
                     .order_by(Inzerat.datum.desc(), Inzerat.id.desc())
                     .all())
    mesta = Mesto.query.order_by(Mesto.nazov.asc()).all()
    return render_template('moj_bazar.html', inzeraty=moje_inzeraty, mesta=mesta, kategorie=KATEGORIE)

# 🗑️ ZMAZANIE INZERÁTU – POST (ponechávam aj tvoju pôv. URL kvôli kompatibilite)
@inzerat.route('/zmaz-inzerat/<int:inzerat_id>', methods=['POST'], endpoint='zmaz_inzerat')
@inzerat.route('/inzerat/<int:inzerat_id>/zmazat', methods=['POST'])
@login_required
def zmaz_moj(inzerat_id):
    inz = Inzerat.query.get_or_404(inzerat_id)
    if inz.pouzivatel_id != current_user.id and not (current_user.is_admin or current_user.is_moderator):
        abort(403)

    # zmaž fyzické súbory
    folder = _upload_dir()
    for f in list(inz.fotky):
        path = os.path.join(folder, f.nazov_suboru)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    db.session.delete(inz)  # cascade odstráni FotoInzerat
    db.session.commit()
    flash("Inzerát a jeho fotky boli zmazané.", "success")
    return redirect(url_for('inzerat.moj_bazar'))

# ✏️ UPRAVA INZERÁTU
@inzerat.route('/uprav-inzerat/<int:inzerat_id>', methods=['GET', 'POST'])
@login_required
def uprav_inzerat(inzerat_id):
    inz = Inzerat.query.get_or_404(inzerat_id)
    if inz.pouzivatel_id != current_user.id and not (current_user.is_admin or current_user.is_moderator):
        abort(403)

    if request.method == 'POST':
        inz.typ       = (request.form.get('typ') or '').strip() or None
        inz.kategoria = (request.form.get('kategoria') or '').strip() or None
        inz.doprava   = (request.form.get('doprava') or '').strip() or None
        inz.popis     = (request.form.get('popis') or '').strip() or None
        inz.cena      = _parse_float(request.form.get('cena'))

        mesto_id = request.form.get('mesto_id', type=int)
        inz.mesto_id = mesto_id

        # nové fotky (doplníme do limitu 5)
        ulozene = len(inz.fotky)
        for fs in request.files.getlist('fotky'):
            if ulozene >= 5:
                break
            filename = _save_image(fs)
            if filename:
                db.session.add(FotoInzerat(nazov_suboru=filename, inzerat_id=inz.id))
                ulozene += 1

        db.session.commit()
        flash("✅ Inzerát bol úspešne upravený!", "success")
        return redirect(url_for('inzerat.moj_bazar'))

    mesta = Mesto.query.order_by(Mesto.nazov.asc()).all()
    return render_template('uprav_inzerat.html', inzerat=inz, mesta=mesta, kategorie=KATEGORIE)

# 🖼️ ZMAZANIE JEDNEJ FOTKY – POST
@inzerat.route('/zmaz-fotku/<int:foto_id>', methods=['POST'])
@login_required
def zmaz_fotku(foto_id):
    fotka = FotoInzerat.query.get_or_404(foto_id)
    inz = Inzerat.query.get_or_404(fotka.inzerat_id)

    if inz.pouzivatel_id != current_user.id and not (current_user.is_admin or current_user.is_moderator):
        abort(403)

    path = os.path.join(_upload_dir(), fotka.nazov_suboru)
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass

    db.session.delete(fotka)
    db.session.commit()
    flash("🗑️ Fotka bola odstránená.", "success")
    return redirect(url_for('inzerat.uprav_inzerat', inzerat_id=inz.id))

# 🌍 VEREJNÝ BAZÁR + DETAIL
@inzerat.route('/bazar')
def bazar_verejny():
    page = request.args.get('page', 1, type=int)
    typ = (request.args.get('typ') or '').strip() or None
    kategoria = (request.args.get('kategoria') or '').strip() or None
    mesto_id = request.args.get('mesto', type=int)

    q = Inzerat.query
    if typ:
        q = q.filter(Inzerat.typ == typ)
    if kategoria:
        q = q.filter(Inzerat.kategoria == kategoria)
    if mesto_id:
        q = q.filter(Inzerat.mesto_id == mesto_id)

    q = q.order_by(Inzerat.datum.desc(), Inzerat.id.desc())
    pagination = q.paginate(page=page, per_page=12, error_out=False)
    inzeraty = pagination.items

    typy = [t[0] for t in db.session.query(Inzerat.typ).distinct().all()]
    kategorie = [k[0] for k in db.session.query(Inzerat.kategoria).distinct().all()]
    mesta = Mesto.query.order_by(Mesto.nazov.asc()).all()

    return render_template(
        'bazar.html',
        inzeraty=inzeraty,
        pagination=pagination,
        typy=typy,
        kategorie=kategorie,
        mesta=mesta,
        vybrany_typ=typ,
        vybrana_kategoria=kategoria,
        vybrane_mesto=mesto_id
    )

@inzerat.route('/bazar/<int:inzerat_id>')
def bazar_detail(inzerat_id):
    detail_inz = Inzerat.query.get_or_404(inzerat_id)

    typy = [t[0] for t in db.session.query(Inzerat.typ).distinct().all()]
    kategorie = [k[0] for k in db.session.query(Inzerat.kategoria).distinct().all()]
    mesta = Mesto.query.order_by(Mesto.nazov.asc()).all()

    return render_template(
        'bazar.html',
        inzeraty=[],
        pagination=None,
        typy=typy,
        kategorie=kategorie,
        mesta=mesta,
        vybrany_typ=None,
        vybrana_kategoria=None,
        vybrane_mesto=None,
        detail_inz=detail_inz
    )

# ✉️ Rýchla odpoveď z detailu inzerátu (do interných správ) + jemná kontrola
@inzerat.route('/bazar/<int:inzerat_id>/sprava', methods=['POST'])
@login_required
def poslat_spravu(inzerat_id):
    from models import Sprava  # lazy import aby sa necyklil modul
    inz = Inzerat.query.get_or_404(inzerat_id)

    if inz.pouzivatel_id == current_user.id:
        flash("Na vlastný inzerát nie je potrebné reagovať 😉", "info")
        return redirect(url_for('inzerat.bazar_detail', inzerat_id=inz.id))

    obsah = (request.form.get('obsah') or '').strip()
    if not obsah:
        flash("Správa nemôže byť prázdna.", "warning")
        return redirect(url_for('inzerat.bazar_detail', inzerat_id=inz.id))

    s = Sprava(
        obsah=obsah,
        od_id=current_user.id,
        komu_id=inz.pouzivatel_id,
        inzerat_id=inz.id
    )
    db.session.add(s)
    db.session.commit()

    # jemná auto-kontrola len zaflaguje
    if auto_moderate_text:
        try:
            res = auto_moderate_text(obsah)
            if res.get("flag"):
                db.session.add(Report(
                    reporter_id=current_user.id,
                    entity_type="sprava",
                    entity_id=s.id,
                    reason=res.get("reason", "nevhodny_obsah"),
                    details=res.get("note") or "automatická kontrola",
                    status="open",
                ))
                db.session.commit()
        except Exception:
            pass

    flash("Správa bola odoslaná.", "success")
    return redirect(url_for('inzerat.bazar_detail', inzerat_id=inz.id))

# skupina.py (upravené)

import os, secrets, time
from uuid import uuid4
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from models import db, Skupina, Pouzivatel, GaleriaSkupina, VideoSkupina, SkupinaPozvanka

# Povolené prípony (zjednotené a doplnené o webp)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

skupina_bp = Blueprint('skupina', __name__)

def _is_spravca(skupina: Skupina, user: Pouzivatel) -> bool:
    return bool(skupina and user and skupina.zakladatel_id == user.id)

def _gen_token() -> str:
    # krátky, URL-safe token
    return secrets.token_urlsafe(24)[:48]


# =========================
#   Moja skupina (detail)
# =========================
@skupina_bp.route('/moja-skupina')
@login_required
def skupina():
    moja = (
        Skupina.query
        .options(
            joinedload(Skupina.galeria),
            joinedload(Skupina.videa),
            joinedload(Skupina.clenovia)
        )
        .join(Skupina.clenovia)
        .filter(Pouzivatel.id == current_user.id)
        .first()
    )
    if not moja:
        flash("Zatiaľ nemáš vytvorenú žiadnu skupinu.", "info")
    return render_template('moja_skupina.html', pouzivatel=current_user, skupina=moja)

# =========================
#   Vytvorenie skupiny
# =========================
@skupina_bp.route('/pridaj_skupinu', methods=['POST'])
@login_required
def pridaj_skupinu():
    nazov = request.form.get('nazov')
    zaner = request.form.get('zaner')
    mesto = request.form.get('mesto')
    email = request.form.get('email')
    web   = request.form.get('web')
    popis = request.form.get('popis')

    nova_skupina = Skupina(
        nazov=nazov,
        zaner=zaner,
        mesto=mesto,
        email=email,
        web=web,
        popis=popis,
        zakladatel=current_user
    )
    # zakladateľ je automaticky člen
    nova_skupina.clenovia.append(current_user)

    db.session.add(nova_skupina)
    db.session.commit()

    flash('Skupina bola úspešne vytvorená ✅', 'success')
    return redirect(url_for('skupina.skupina'))


# =========================
#   Úprava skupiny
# =========================
@skupina_bp.route('/upravit', methods=['POST'])
@login_required
def upravit():
    skupina = current_user.skupina_clen[0] if current_user.skupina_clen else None

    if not skupina:
        flash("Nemáš žiadnu skupinu na úpravu.", "danger")
        return redirect(url_for('skupina.skupina'))  # FIX endpoint

    skupina.nazov = request.form.get('nazov')
    skupina.zaner = request.form.get('zaner')
    skupina.mesto = request.form.get('mesto')
    skupina.email = request.form.get('email')
    skupina.web   = request.form.get('web')
    skupina.popis = request.form.get('popis')

    db.session.commit()
    flash("Skupina bola úspešne upravená ✅", "success")
    return redirect(url_for('skupina.skupina'))


# =========================================
#   Upload / výmena profilovej fotky skupiny
# =========================================
@skupina_bp.route('/upload_fotka_skupina', methods=['POST'])
@login_required
def upload_fotka_skupina():
    file = request.files.get('profil_fotka_skupina')

    if not file or file.filename == '':
        flash("Nebol vybraný žiadny súbor.", "danger")
        return redirect(url_for('skupina.skupina'))

    if not allowed_file(file.filename):
        flash("Nepovolený formát súboru.", "danger")
        return redirect(url_for('skupina.skupina'))

    skupina = current_user.skupina_clen[0] if current_user.skupina_clen else None
    if not skupina:
        flash("Používateľ nemá žiadnu skupinu.", "danger")
        return redirect(url_for('skupina.skupina'))

    upload_folder = os.path.join(current_app.root_path, 'static', 'profilovky_skupina')
    os.makedirs(upload_folder, exist_ok=True)

    # unikátne meno súboru
    orig = secure_filename(file.filename)
    ext  = orig.rsplit('.', 1)[1].lower()
    filename = f"{skupina.id}_{int(time.time())}_{uuid4().hex[:6]}.{ext}"
    filepath = os.path.join(upload_folder, filename)

    # zmaž starú, ak bola
    if skupina.profil_fotka_skupina:
        predosla = os.path.join(upload_folder, skupina.profil_fotka_skupina)
        if os.path.exists(predosla):
            try:
                os.remove(predosla)
            except Exception:
                pass

    file.save(filepath)
    skupina.profil_fotka_skupina = filename
    db.session.commit()
    flash("Fotka kapely bola aktualizovaná.", "success")
    return redirect(url_for('skupina.skupina'))


# ===================================
#   Odstránenie profilovej fotky
# ===================================
@skupina_bp.route('/odstranit_fotku_skupina')
@login_required
def odstranit_fotku_skupina():
    skupina = current_user.skupina_clen[0] if current_user.skupina_clen else None

    if skupina and skupina.profil_fotka_skupina:
        upload_folder = os.path.join(current_app.root_path, 'static', 'profilovky_skupina')
        filepath = os.path.join(upload_folder, skupina.profil_fotka_skupina)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass

        skupina.profil_fotka_skupina = None
        db.session.commit()
        flash("Fotka kapely bola odstránená.", "info")

    return redirect(url_for('skupina.skupina'))


# ===================================
#   MULTI-upload galérie (limit 20)
# ===================================
@skupina_bp.route('/skupina/galeria', methods=['POST'])
@login_required
def nahraj_fotku_skupina():
    skupina = current_user.skupina_clen[0] if current_user.skupina_clen else None
    if not skupina:
        flash("Nemáš priradenú žiadnu skupinu.", "danger")
        return redirect(url_for('skupina.skupina'))

    files = request.files.getlist('fotos')  # POZOR: input name="fotos"
    if not files:
        flash("Nevybrali ste žiadne fotky.", "warning")
        return redirect(url_for('skupina.skupina'))

    MAX_FOTO = 20
    aktualny_pocet = len(skupina.galeria or [])
    volne = max(0, MAX_FOTO - aktualny_pocet)
    if volne <= 0:
        flash(f"Dosiahnutý limit {MAX_FOTO} fotiek v galérii skupiny.", "warning")
        return redirect(url_for('skupina.skupina'))

    upload_dir = os.path.join(current_app.root_path, 'static', 'galeria_skupina')
    os.makedirs(upload_dir, exist_ok=True)

    ulozene = 0
    preskocene = 0

    for file in files:
        if ulozene >= volne:
            break
        if not file or file.filename == '':
            preskocene += 1
            continue
        if not allowed_file(file.filename):
            preskocene += 1
            continue

        orig = secure_filename(file.filename)
        ext  = orig.rsplit('.', 1)[1].lower()
        unique = f"{skupina.id}_{int(time.time())}_{uuid4().hex[:8]}.{ext}"
        dest_path = os.path.join(upload_dir, unique)

        try:
            file.save(dest_path)
            db.session.add(GaleriaSkupina(nazov_suboru=unique, skupina_id=skupina.id))
            ulozene += 1
        except Exception:
            preskocene += 1

    if ulozene:
        db.session.commit()

    if ulozene and preskocene == 0:
        flash(f"Nahraných {ulozene} fotiek.", "success")
    elif ulozene and preskocene:
        flash(f"Nahraných {ulozene} fotiek, {preskocene} preskočených (typ/limit/problém).", "warning")
    else:
        flash("Nepodarilo sa nahrať žiadnu fotku. Skúste iné súbory.", "danger")

    return redirect(url_for('skupina.skupina'))


# =========================
#   Videá
# =========================
@skupina_bp.route('/skupina/<int:id>/pridaj_video', methods=['POST'])
@login_required
def pridaj_video_skupina(id):
    skupina = Skupina.query.get_or_404(id)
    if current_user not in skupina.clenovia:
        abort(403)

    url = request.form['youtube_url']
    popis = request.form.get('popis')

    db.session.add(VideoSkupina(youtube_url=url, popis=popis, skupina_id=skupina.id))
    db.session.commit()

    flash("Video bolo pridané do skupiny.", "success")
    return redirect(url_for('skupina.skupina'))


@skupina_bp.route('/skupina/video/zmaz/<int:id>', methods=['POST'])
@login_required
def zmaz_video_skupina(id):
    video = VideoSkupina.query.get_or_404(id)
    skupina = video.skupina
    if current_user not in skupina.clenovia:
        abort(403)

    db.session.delete(video)
    db.session.commit()
    flash("Video bolo zmazané.", "success")
    return redirect(url_for('skupina.skupina'))


# =========================
#   Pozvánky
# =========================
@skupina_bp.route('/skupina/<int:id>/pozvi', methods=['POST'])
@login_required
def pozvi_clena(id):
    skupina = Skupina.query.get_or_404(id)
    if not _is_spravca(skupina, current_user):
        abort(403)

    target = (request.form.get('target') or '').strip()
    if not target:
        flash('Zadaj prezývku, email alebo ID používateľa.', 'warning')
        return redirect(url_for('skupina.skupina'))

    # nájdi používateľa podľa id/prezývky/emailu
    q = Pouzivatel.query
    user = None
    if target.isdigit():
        user = q.filter_by(id=int(target)).first()
    if not user:
        user = q.filter(or_(Pouzivatel.prezyvka == target,
                            Pouzivatel.email == target)).first()

    if not user:
        flash('Používateľ neexistuje.', 'danger')
        return redirect(url_for('skupina.skupina'))

    if user.id == current_user.id:
        flash('Nemôžeš pozvať sám seba.', 'info')
        return redirect(url_for('skupina.skupina'))

    # už člen?
    if user in skupina.clenovia:
        flash('Tento používateľ je už členom skupiny.', 'info')
        return redirect(url_for('skupina.skupina'))

    # existujúca neexpirovaná pozvánka?
    now = datetime.utcnow()
    inv = (SkupinaPozvanka.query
           .filter_by(skupina_id=skupina.id, pozvany_id=user.id, stav='pending')
           .filter(or_(SkupinaPozvanka.expires_at == None, SkupinaPozvanka.expires_at > now))
           .first())

    if not inv:
        inv = SkupinaPozvanka(
            token=_gen_token(),
            stav='pending',
            created_at=now,
            expires_at=now + timedelta(days=7),
            skupina_id=skupina.id,
            pozvany_id=user.id,
            pozval_id=current_user.id
        )
        db.session.add(inv)
        db.session.commit()

    # FIX: flash link na GET view (nie POST accept)
    link = url_for('skupina.prijmi_pozvanku_view', token=inv.token, _external=True)
    flash(f'Pozvánka vytvorená. Pošli tento link pozvanému: {link}', 'success')
    return redirect(url_for('skupina.skupina'))


@skupina_bp.route('/pozvanka/<string:token>/zrus', methods=['POST'])
@login_required
def zrus_pozvanku(token):
    inv = SkupinaPozvanka.query.filter_by(token=token).first_or_404()
    skupina = inv.skupina
    if not (_is_spravca(skupina, current_user) or inv.pozval_id == current_user.id):
        abort(403)
    if inv.stav == 'pending':
        inv.stav = 'revoked'
        db.session.commit()
        flash('Pozvánka bola zrušená.', 'info')
    return redirect(url_for('skupina.skupina'))


@skupina_bp.route('/pozvanka/<string:token>', methods=['GET'])
def prijmi_pozvanku_view(token):
    inv = SkupinaPozvanka.query.filter_by(token=token).first_or_404()

    # expirácia -> označ ako expired
    if inv.stav == 'pending' and inv.expires_at and datetime.utcnow() >= inv.expires_at:
        inv.stav = 'expired'
        db.session.commit()

    # ak nie je prihlásený, pošli ho na login s návratom sem
    if not current_user.is_authenticated:
        return redirect(url_for('uzivatel.login', next=request.url))

    # musí byť prihlásený presne pozvaný používateľ
    if current_user.id != inv.pozvany_id:
        flash('Táto pozvánka patrí inému účtu. Odhlás sa a prihlás sa ako pozvaný.', 'danger')
        return redirect(url_for('uzivatel.profil'))

    return render_template('skupina_pozvanka.html', inv=inv)


@skupina_bp.route('/pozvanka/<string:token>/accept', methods=['POST'])
@login_required
def prijmi_pozvanku(token):
    inv = SkupinaPozvanka.query.filter_by(token=token).first_or_404()

    if current_user.id != inv.pozvany_id:
        abort(403)

    # Nepoliahaj sa na model.is_valid() – skontroluj tu
    if inv.stav != 'pending' or (inv.expires_at and datetime.utcnow() >= inv.expires_at):
        flash('Pozvánka už nie je platná.', 'danger')
        return redirect(url_for('uzivatel.profil'))

    skupina = inv.skupina
    if current_user not in skupina.clenovia:
        skupina.clenovia.append(current_user)

    inv.stav = 'accepted'
    db.session.commit()
    flash(f'Pripojené do skupiny: {skupina.nazov}', 'success')
    return redirect(url_for('skupina.skupina'))

@skupina_bp.route('/skupiny', methods=['GET'])
def prehlad_skupin():
    q = (request.args.get('q') or '').strip()
    mesto = (request.args.get('mesto') or '').strip()

    qry = (Skupina.query
           .options(joinedload(Skupina.zakladatel))
           .order_by(Skupina.nazov.asc()))

    if q:
        like = f"%{q}%"
        qry = qry.filter(or_(Skupina.nazov.ilike(like),
                             Skupina.popis.ilike(like)))
    if mesto:
        qry = qry.filter(Skupina.mesto == mesto)

    skupiny = qry.all()
    return render_template('skupiny.html', skupiny=skupiny, q=q, mesto=mesto)


@skupina_bp.route('/skupiny/<int:id>', methods=['GET'])
def skupina_detail(id):
    s = (Skupina.query
         .options(
             joinedload(Skupina.clenovia),
             joinedload(Skupina.galeria),
             joinedload(Skupina.videa),
             joinedload(Skupina.zakladatel),
         )
         .get_or_404(id))

    is_owner_group = current_user.is_authenticated and s.zakladatel_id == current_user.id
    return render_template('skupina_detail.html', skupina=s, is_owner_group=is_owner_group)


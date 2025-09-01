import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, abort
from models import db, Skupina, Pouzivatel, GaleriaSkupina, VideoSkupina
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

# Povolené prípony pre fotky
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

skupina_bp = Blueprint('skupina', __name__, template_folder='templates')

# Zobrazenie stránky skupiny
@skupina_bp.route('/moja-skupina')
@login_required
def skupina():
    moja = current_user.skupina_clen[0] if current_user.skupina_clen else None
    if not moja:
        flash("Zatiaľ nemáš vytvorenú žiadnu skupinu.", "info")
    return render_template('moja_skupina.html', pouzivatel=current_user, skupina=moja)


# Pridanie novej skupiny
@skupina_bp.route('/pridaj_skupinu', methods=['POST'])
@login_required
def pridaj_skupinu():
    nazov = request.form.get('nazov')
    zaner = request.form.get('zaner')
    mesto = request.form.get('mesto')
    email = request.form.get('email')
    web = request.form.get('web')
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
    nova_skupina.clenovia.append(current_user)

    db.session.add(nova_skupina)
    db.session.commit()

    flash('Skupina bola úspešne vytvorená ✅', 'success')
    return redirect(url_for('skupina.skupina'))

# Úprava existujúcej skupiny
@skupina_bp.route('/upravit', methods=['POST'])
@login_required
def upravit():
    skupina = current_user.skupina_clen[0] if current_user.skupina_clen else None

    if not skupina:
        flash("Nemáš žiadnu skupinu na úpravu.", "danger")
        return redirect(url_for('skupina.moja_skupina'))


    skupina.nazov = request.form.get('nazov')
    skupina.zaner = request.form.get('zaner')
    skupina.mesto = request.form.get('mesto')
    skupina.email = request.form.get('email')
    skupina.web = request.form.get('web')
    skupina.popis = request.form.get('popis')

    db.session.commit()
    flash("Skupina bola úspešne upravená ✅", "success")
    return redirect(url_for('skupina.skupina'))


# Nahratie alebo výmena profilovej fotky kapely
@skupina_bp.route('/upload_fotka_skupina', methods=['POST'])
@login_required
def upload_fotka_skupina():
    file = request.files.get('profil_fotka_skupina')

    if not file or file.filename == '':
        flash("Nebol vybraný žiadny súbor.", "danger")
        return redirect(url_for('skupina.skupina'))


    if allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_folder = os.path.join(current_app.root_path, 'static', 'profilovky_skupina')
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, filename)

        skupina = current_user.skupina_clen[0] if current_user.skupina_clen else None
        if not skupina:
            flash("Používateľ nemá žiadnu skupinu.", "danger")
            return redirect(url_for('skupina.skupina'))


        # Odstráni starú fotku, ak existuje
        if skupina.profil_fotka_skupina:
            predosla = os.path.join(upload_folder, skupina.profil_fotka_skupina)
            if os.path.exists(predosla):
                os.remove(predosla)

        file.save(filepath)
        skupina.profil_fotka_skupina = filename
        db.session.commit()
        flash("Fotka kapely bola aktualizovaná.", "success")
    else:
        flash("Nepovolený formát súboru.", "danger")

    return redirect(url_for('skupina.skupina'))

# Odstránenie profilovej fotky kapely
@skupina_bp.route('/odstranit_fotku_skupina')
@login_required
def odstranit_fotku_skupina():
    skupina = current_user.skupina_clen[0] if current_user.skupina_clen else None

    if skupina and skupina.profil_fotka_skupina:
        filepath = os.path.join(current_app.root_path, 'static', 'profilovky_skupina', skupina.profil_fotka_skupina)
        if os.path.exists(filepath):
            os.remove(filepath)

        skupina.profil_fotka_skupina = None
        db.session.commit()
        flash("Fotka kapely bola odstránená.", "info")

    return redirect(url_for('skupina.skupina'))

# Pridanie fotky do galérie skupiny
@skupina_bp.route('/skupina/galeria', methods=['POST'])
@login_required
def nahraj_fotku_skupina():
    from uuid import uuid4
    import time

    moja = current_user.skupina_clen[0] if current_user.skupina_clen else None
    if not moja:
        flash("Nemáš priradenú žiadnu skupinu.", "danger")
        return redirect(url_for('skupina.skupina'))

    files = request.files.getlist('fotos')  # ← multiple
    if not files:
        flash("Nevybrali ste žiadne fotky.", "warning")
        return redirect(url_for('skupina.skupina'))

    # limit napr. 20 fotiek v galérii skupiny
    max_foto = 20
    aktualny_pocet = len(moja.galeria or [])
    volne = max(0, max_foto - aktualny_pocet)
    if volne <= 0:
        flash("Dosiahnutý limit galérie skupiny.", "warning")
        return redirect(url_for('skupina.skupina'))

    allowed = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
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

        fname = secure_filename(file.filename)
        ext = (fname.rsplit('.', 1)[-1].lower() if '.' in fname else '')
        if ext not in allowed:
            preskocene += 1
            continue

        # unikát: groupID_timestamp_rand8.ext
        unique = f"{moja.id}_{int(time.time())}_{uuid4().hex[:8]}.{ext}"
        dest_path = os.path.join(upload_dir, unique)
        try:
            file.save(dest_path)
            db.session.add(GaleriaSkupina(nazov_suboru=unique, skupina_id=moja.id))
            ulozene += 1
        except Exception:
            preskocene += 1

    if ulozene:
        db.session.commit()

    if ulozene and preskocene == 0:
        flash(f"Nahraných {ulozene} fotiek.", "success")
    elif ulozene and preskocene:
        flash(f"Nahraných {ulozene} fotiek, {preskocene} preskočených.", "warning")
    else:
        flash("Nepodarilo sa nahrať žiadnu fotku.", "danger")

    return redirect(url_for('skupina.skupina'))

# Odstránenie fotky z galérie skupiny
@skupina_bp.route('/skupina/galeria/zmaz/<int:id>', methods=['POST'])
@login_required
def zmaz_fotku_skupina(id):
    fotka = GaleriaSkupina.query.get_or_404(id)
    skupina = current_user.skupina_clen[0] if current_user.skupina_clen else None

    if fotka.skupina_id == skupina.id:
        cesta = os.path.join('static/galeria_skupina', fotka.nazov_suboru)
        if os.path.exists(cesta):
            os.remove(cesta)
        db.session.delete(fotka)
        db.session.commit()

    return redirect(url_for('skupina.skupina'))

# Pridanie videa do skupiny #
@skupina_bp.route('/skupina/<int:id>/pridaj_video', methods=['POST'])
@login_required
def pridaj_video_skupina(id):
    skupina = Skupina.query.get_or_404(id)

    # Ochrana – len členovia môžu pridávať videá
    if current_user not in skupina.clenovia:
        abort(403)

    url = request.form['youtube_url']
    popis = request.form.get('popis')

    nove_video = VideoSkupina(youtube_url=url, popis=popis, skupina_id=skupina.id)
    db.session.add(nove_video)
    db.session.commit()

    flash("Video bolo pridané do skupiny.", "success")
    return redirect(url_for('skupina.skupina'))

# Zmazanie videa zo skupiny #
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


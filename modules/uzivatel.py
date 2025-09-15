import os
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, abort
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from sqlalchemy.orm import joinedload
from jinja2 import TemplateNotFound
from models import Pouzivatel, db, GaleriaPouzivatel, VideoPouzivatel, Skupina, Podujatie, Reklama
from flask import request, redirect, url_for, flash, abort
from datetime import datetime, timedelta
from sqlalchemy import or_

uzivatel = Blueprint('uzivatel', __name__)
profil_blueprint = Blueprint('profil', __name__)

# -- Pomocník: bezpečné renderovanie profilu (fallback na modals/profil.html)
def render_profile_template(**ctx):
    try:
        return render_template('profil.html', **ctx)
    except TemplateNotFound:
        return render_template('modals/profil.html', **ctx)

# 🔹 Test endpoint
@uzivatel.route('/test')
def test():
    return "Blueprint uzivatel funguje!"

# 🔹 Domovská stránka
@uzivatel.route('/')
def index():
    typ = request.args.get('typ', 'vsetko')  # vsetko|podujatia|reklamy
    now = datetime.utcnow()
    threshold = now - timedelta(days=1)

    # Podujatia: ukazujeme od včera (ako máš)
    events_q = (
        Podujatie.query
        .filter(Podujatie.start_dt >= threshold)
        .order_by(Podujatie.start_dt.asc())
    )

    # Reklamy: aktívne teraz (DB filter) + autora pre link
    ads_q = (
        Reklama.query
        .options(joinedload(Reklama.autor))
        .filter(
            Reklama.start_dt <= now,
            or_(Reklama.end_dt == None, Reklama.end_dt >= now)
        )
        .order_by(Reklama.is_top.desc(), Reklama.created_at.desc())
        .limit(100)
    )

    feed = []
    if typ in ('vsetko', 'podujatia'):
        for e in events_q.limit(50).all():
            feed.append(('event', e.start_dt, e))

    if typ in ('vsetko', 'reklamy'):
        for ad in ads_q.all():
            # pre feed použijeme čas vzniku reklamy; ak chceš, môžeš dať ad.start_dt
            feed.append(('ad', ad.created_at, ad))

    # najnovšie hore
    feed.sort(key=lambda r: r[1], reverse=True)

    return render_template('index.html', feed=feed, typ=typ)

# 🔹 Login
@uzivatel.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        heslo = request.form['heslo']
        pouzivatel = Pouzivatel.query.filter_by(email=email).first()

        if pouzivatel and pouzivatel.over_heslo(heslo):
            login_user(pouzivatel)
            flash("Prihlásenie prebehlo úspešne.", "success")

            # podpora ?next=/niekam  (len relatívne URL sú povolené)
            next_url = request.args.get('next') or request.form.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)

            # DEFAULT: DOMOV (homepage stredný feed)
            return redirect(url_for('uzivatel.index'))
        else:
            flash("Nesprávne prihlasovacie údaje.", "warning")
            return redirect(url_for('uzivatel.login'))

    return render_template('login.html')


# 🔹 Registrácia
@uzivatel.route('/registracia', methods=['GET', 'POST'])
def registracia():
    if request.method == 'POST':
        typ = (request.form.get('typ_subjektu') or 'fyzicka').strip()

        email = request.form['email'].strip()
        heslo = generate_password_hash(request.form['heslo'])
        obec  = (request.form.get('obec') or '').strip()

        if typ == 'ico':
            organizacia_nazov = (request.form.get('organizacia_nazov') or '').strip()
            ico = (request.form.get('ico') or '').strip()

            if not organizacia_nazov or not ico:
                flash("Vyplň Názov organizácie aj IČO.", "warning")
                return redirect(url_for('uzivatel.registracia'))

            # Pre konzistenciu používame názov organizácie aj ako prezývku (UI ho často zobrazuje)
            prezyvka = organizacia_nazov
            meno = priezvisko = instrument = doplnkovy_nastroj = None

        else:
            # fyzická osoba
            prezyvka = (request.form.get('prezyvka') or '').strip()
            meno = (request.form.get('meno') or '').strip()
            priezvisko = (request.form.get('priezvisko') or '').strip()
            instrument = (request.form.get('instrument') or '').strip()
            doplnkovy_nastroj = (request.form.get('doplnkovy_nastroj') or '').strip() or None
            organizacia_nazov = None
            ico = None

            if not prezyvka:
                flash("Prezývka je povinná pre fyzickú osobu.", "warning")
                return redirect(url_for('uzivatel.registracia'))

        existujuci = Pouzivatel.query.filter(
            (Pouzivatel.email == email) | (Pouzivatel.prezyvka == prezyvka)
        ).first()
        if existujuci:
            flash("Používateľ s týmto e-mailom alebo prezývkou už existuje.", "warning")
            return redirect(url_for('uzivatel.registracia'))

        novy = Pouzivatel(
            prezyvka=prezyvka,
            meno=meno,
            priezvisko=priezvisko,
            email=email,
            heslo=heslo,
            instrument=instrument,
            doplnkovy_nastroj=doplnkovy_nastroj,
            obec=obec,
            typ_subjektu=typ,
            ico=ico,
            organizacia_nazov=organizacia_nazov
        )

        db.session.add(novy)
        db.session.commit()
        flash('Registrácia prebehla úspešne.', "success")
        return redirect(url_for('uzivatel.login'))

    return render_template('modals/registracia.html')


# 🔹 Logout
@uzivatel.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('uzivatel.index'))

# 🔹 Moje konto (edit vlastného profilu)
#     -> 2 URL: /moje-konto aj /profil (endpoint='profil' = alias pre staré odkazy)
@uzivatel.route('/moje-konto', methods=['GET', 'POST'])
@uzivatel.route('/profil', methods=['GET', 'POST'], endpoint='profil')
@login_required
def moje_konto():
    pouzivatel = current_user

    if request.method == 'POST':
        pouzivatel.prezyvka = request.form.get('prezyvka')
        pouzivatel.meno = request.form.get('meno')
        pouzivatel.priezvisko = request.form.get('priezvisko')
        pouzivatel.email = request.form.get('email')
        pouzivatel.obec = request.form.get('obec')
        pouzivatel.instrument = request.form.get('instrument')
        pouzivatel.doplnkovy_nastroj = request.form.get('doplnkovy_nastroj')
        pouzivatel.bio = request.form.get('bio')

        # 🔹 NOVÉ: typ účtu + IČO polia
        typ = request.form.get('typ_subjektu') or 'fyzicka'
        pouzivatel.typ_subjektu = typ
        if typ == 'ico':
            pouzivatel.ico = (request.form.get('ico') or '').strip() or None
            pouzivatel.organizacia_nazov = (request.form.get('organizacia_nazov') or '').strip() or None
        else:
            pouzivatel.ico = None
            pouzivatel.organizacia_nazov = None

        db.session.commit()
        flash("Profil bol úspešne upravený", "success")
        return redirect(url_for('uzivatel.profil'))

    skupina = pouzivatel.skupina_clen[0] if pouzivatel.skupina_clen else None
    galeria = skupina.galeria if skupina else []
    youtube_videa = pouzivatel.videa

    return render_profile_template(
        pouzivatel=pouzivatel,
        skupina=skupina,
        galeria=galeria,
        youtube_videa=youtube_videa
    )


# 🔹 Upload profilovej fotky
@uzivatel.route('/upload_fotka', methods=['POST'])
@login_required
def upload_fotka():
    if 'profil_fotka' not in request.files:
        flash("Nebol vybraný žiadny súbor.", "danger")
        return redirect(url_for('uzivatel.profil'))

    file = request.files['profil_fotka']
    if file.filename == '':
        flash("Nebol vybraný žiadny súbor.", "danger")
        return redirect(url_for('uzivatel.profil'))

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.root_path, 'static', 'profilovky', filename)
        file.save(filepath)

        pouzivatel = current_user
        pouzivatel.profil_fotka = filename
        db.session.commit()

        flash("Profilová fotka bola úspešne nahraná.", "success")
    return redirect(url_for('uzivatel.profil'))

# 🔹 Odstránenie profilovej fotky
@uzivatel.route('/odstranit_fotku')
@login_required
def odstranit_fotku():
    pouzivatel = current_user

    if pouzivatel.profil_fotka:
        filepath = os.path.join(current_app.root_path, 'static', 'profilovky', pouzivatel.profil_fotka)
        if os.path.exists(filepath):
            os.remove(filepath)
        pouzivatel.profil_fotka = None
        db.session.commit()

    flash("Profilová fotka bola odstránená.", "success")
    return redirect(url_for('uzivatel.profil'))

# 🔹 Upload fotky do galérie používateľa
@profil_blueprint.route('/profil/galeria', methods=['POST'])
@login_required
def nahraj_fotku():
    from uuid import uuid4
    import time

    files = request.files.getlist('fotos')
    if not files:
        flash("Nevybrali ste žiadne fotky.", "warning")
        return redirect(url_for('uzivatel.profil'))

    uz = current_user
    max_foto = 10
    aktualny_pocet = len(uz.galeria)
    volne = max(0, max_foto - aktualny_pocet)
    if volne <= 0:
        flash("Dosiahnutý limit 10 fotiek v galérii.", "warning")
        return redirect(url_for('uzivatel.profil'))

    allowed = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    upload_dir = os.path.join(current_app.root_path, 'static', 'galeria_pouzivatel')
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

        unique = f"{uz.id}_{int(time.time())}_{uuid4().hex[:8]}.{ext}"
        dest_path = os.path.join(upload_dir, unique)
        try:
            file.save(dest_path)
            db.session.add(GaleriaPouzivatel(nazov_suboru=unique, pouzivatel_id=uz.id))
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

    return redirect(url_for('uzivatel.profil'))

# 🔹 Odstránenie fotky z galérie používateľa
@profil_blueprint.route('/profil/galeria/zmaz/<int:id>', methods=['POST'])
@login_required
def zmaz_fotku(id):
    fotka = GaleriaPouzivatel.query.get_or_404(id)
    if fotka.pouzivatel_id == current_user.id:
        cesta = os.path.join(current_app.root_path, 'static', 'galeria_pouzivatel', fotka.nazov_suboru)
        if os.path.exists(cesta):
            os.remove(cesta)
        db.session.delete(fotka)
        db.session.commit()
    return redirect(url_for('uzivatel.profil'))

@profil_blueprint.route('/pridaj_video', methods=['POST'])
@login_required
def pridaj_video():
    url = request.form['youtube_url']
    popis = request.form.get('popis')
    nove_video = VideoPouzivatel(youtube_url=url, popis=popis, pouzivatel_id=current_user.id)
    db.session.add(nove_video)
    db.session.commit()
    flash("Video bolo pridané.", "success")
    return redirect(url_for('uzivatel.profil'))

@profil_blueprint.route('/zmaz_video/<int:id>', methods=['POST'])
@login_required
def zmaz_video(id):
    video = VideoPouzivatel.query.get_or_404(id)
    if video.pouzivatel_id != current_user.id:
        abort(403)
    db.session.delete(video)
    db.session.commit()
    flash("Video bolo zmazané.", "success")
    return redirect(url_for('uzivatel.profil'))

# 🔹 Verejný (read-only) profil konkrétneho používateľa
@uzivatel.route('/u/<int:user_id>', methods=['GET'])
def verejny_profil(user_id):
    user = (
        Pouzivatel.query
        .options(
            joinedload(Pouzivatel.galeria),
            joinedload(Pouzivatel.videa),
            joinedload(Pouzivatel.skupina_clen).joinedload(Skupina.clenovia),
            joinedload(Pouzivatel.skupina_clen).joinedload(Skupina.galeria),
        )
        .get(user_id)
    )
    if not user:
        abort(404)

    skupina = user.skupina_clen[0] if user.skupina_clen else None
    galeria = skupina.galeria if skupina else []

    
    # Verejný profil má vlastnú šablónu
    return render_profile_template(
    pouzivatel=user,
    skupina=skupina,
    galeria=galeria,
    youtube_videa=user.videa,
    public_view=True   # ⟵ dôležité, tým odlíšime verejné zobrazenie
)



@uzivatel.route('/admin/user/<int:user_id>/vip/<string:action>', methods=['POST'])
@login_required
def admin_set_vip(user_id, action):
    # len admin môže prepínať VIP
    if not getattr(current_user, 'is_admin', False):
        abort(403)

    user = Pouzivatel.query.get_or_404(user_id)
    turn_on = (action.lower() == 'on')

    user.is_vip = bool(turn_on)
    user.billing_exempt = bool(turn_on)  # VIP automaticky bez fakturácie
    db.session.commit()

    flash(f"VIP pre používateľa #{user.id} {'zapnuté' if turn_on else 'vypnuté'}.", "success")
    # návrat späť na stránku, odkiaľ si prišiel (alebo na profil)
    next_url = request.form.get('next') or request.referrer or url_for('uzivatel.profil')
    return redirect(next_url)
import os
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, abort, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from sqlalchemy.orm import joinedload
from jinja2 import TemplateNotFound
from models import Pouzivatel, db, GaleriaPouzivatel, VideoPouzivatel, Skupina, Podujatie, Reklama
from flask import request, redirect, url_for, flash, abort
from datetime import datetime, timedelta
from sqlalchemy import or_
import re, smtplib
from email.message import EmailMessage
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

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

def _pwd_ok(pwd: str) -> bool:
    # aspoň 8 znakov, min. 1 písmeno a 1 číslo
    return bool(re.fullmatch(r'(?=.*[A-Za-z])(?=.*\d).{8,}', pwd or ''))

def _make_serializer() -> URLSafeTimedSerializer:
    # salt nech je fixný, ale jedinečný pre túto funkcionalitu
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='regv1')

def _send_verif_email(to_email: str, link: str):
    cfg = current_app.config
    user = cfg.get('SMTP_USERNAME')
    pwd  = cfg.get('SMTP_PASSWORD')

    # DEV fallback: keď nemáš SMTP, ukáž link vo flashi + zaloguj
    if not user or not pwd:
        current_app.logger.info(f"[DEV] Overovací odkaz: {link}")
        try:
            # zobrazí sa po redirekte na stránke (pozri bod 2 nižšie pre |safe)
            from flask import flash
            flash(f"[DEV] Overovací odkaz: <a href='{link}'>klikni sem</a>", "success")
        except Exception:
            pass
        return  # necháme vonkajší try/except považovať to za úspech

    # produkčné odoslanie e-mailu cez SMTP
    msg = EmailMessage()
    msg['Subject'] = 'Potvrď registráciu na Muzikuj'
    msg['From'] = cfg.get('SMTP_SENDER', user or 'noreply@muzikuj.sk')
    msg['To'] = to_email
    msg.set_content(
        f"Ahoj!\n\nKlikni na tento odkaz a dokonči registráciu:\n{link}\n\n"
        "Odkaz je platný 48 hodín.\nAk si o registráciu nežiadas, správu ignoruj."
    )

    with smtplib.SMTP(cfg.get('SMTP_SERVER', 'smtp.gmail.com'), int(cfg.get('SMTP_PORT', 587))) as s:
        s.ehlo()
        s.starttls()
        s.ehlo()
        s.login(user, pwd)
        s.send_message(msg)
    
# 🔹 Registrácia
@uzivatel.route('/registracia', methods=['GET', 'POST'])
def registracia():
    if request.method == 'POST':
        typ = (request.form.get('typ_subjektu') or 'fyzicka').strip()

        # --- validácia hesiel
        heslo_raw = request.form.get('heslo', '')
        heslo2    = request.form.get('heslo2', '')
        if heslo_raw != heslo2:
            flash("Heslá sa nezhodujú.", "warning")
            return redirect(url_for('uzivatel.registracia'))
        heslo_h = generate_password_hash(heslo_raw)

        email = (request.form.get('email') or '').strip()
        obec  = (request.form.get('obec') or '').strip()

        # --- FO vs IČO polia + zamerania
        data = {
            'typ_subjektu': typ,
            'email': email,
            'heslo': heslo_h,
            'obec':  obec,
        }

        if typ == 'ico':
            organizacia_nazov = (request.form.get('organizacia_nazov') or '').strip()
            ico = (request.form.get('ico') or '').strip()
            if not organizacia_nazov or not ico:
                flash("Vyplň Názov organizácie aj IČO.", "warning")
                return redirect(url_for('uzivatel.registracia'))

            # IČO – organizačné údaje
            data.update({
                'prezyvka': organizacia_nazov,   # UI používa prezývku – dáme názov
                'meno': None, 'priezvisko': None,
                'instrument': None, 'doplnkovy_nastroj': None,

                'ico': ico,
                'organizacia_nazov': organizacia_nazov,
                'dic': (request.form.get('dic') or '').strip() or None,
                'ic_dph': (request.form.get('ic_dph') or '').strip() or None,
                'sidlo_ulica': (request.form.get('sidlo_ulica') or '').strip() or None,
                'sidlo_psc': (request.form.get('sidlo_psc') or '').strip() or None,
                'sidlo_mesto': (request.form.get('sidlo_mesto') or '').strip() or None,
                'org_zaradenie': (request.form.get('org_zaradenie') or '').strip() or None,
                'org_zaradenie_ine': (request.form.get('org_zaradenie_ine') or '').strip() or None,

                # FO-only zamerania nech sú None
                'rola': None, 'hud_oblast': None, 'hud_spec': None,
                'tanec_spec': None, 'tanec_ine': None,
                'ucitel_predmety': None, 'ucitel_ine': None,
            })

            # duplicita: email + (voliteľne názov ako prezývka)
            exist = Pouzivatel.query.filter(
                (Pouzivatel.email == email) | (Pouzivatel.prezyvka == organizacia_nazov)
            ).first()
            if exist:
                flash("Používateľ s týmto e-mailom alebo názvom už existuje.", "warning")
                return redirect(url_for('uzivatel.registracia'))

        else:
            # Fyzická osoba
            prezyvka   = (request.form.get('prezyvka') or '').strip()
            meno       = (request.form.get('meno') or '').strip() or None
            priezvisko = (request.form.get('priezvisko') or '').strip() or None
            if not prezyvka:
                flash("Prezývka je povinná pre fyzickú osobu.", "warning")
                return redirect(url_for('uzivatel.registracia'))

            # zamerania
            rola = (request.form.get('rola') or '').strip() or None
            hud_oblast = (request.form.get('hud_oblast') or '').strip() or None
            # hud_spec: priorita select->free->checkbox multi
            hud_spec = (request.form.get('hud_spec') or '').strip()
            if not hud_spec:
                hud_spec = (request.form.get('hud_spec_free') or '').strip()
            if not hud_spec:
                ms = request.form.getlist('hud_spec_multi')
                hud_spec = ','.join(ms) if ms else None

            tanec_spec_list = request.form.getlist('tanec_spec_multi')
            tanec_spec = ','.join(tanec_spec_list) if tanec_spec_list else None
            tanec_ine = (request.form.get('tanec_ine_text') or '').strip() or None

            ucitel_list = request.form.getlist('ucitel_predmety_multi')
            ucitel_predmety = ','.join(ucitel_list) if ucitel_list else None
            ucitel_ine = (request.form.get('ucitel_ine_text') or '').strip() or None

            instrument = (request.form.get('instrument') or '').strip() or None
            doplnkovy  = (request.form.get('doplnkovy_nastroj') or '').strip() or None

            data.update({
                'prezyvka': prezyvka,
                'meno': meno, 'priezvisko': priezvisko,
                'instrument': instrument, 'doplnkovy_nastroj': doplnkovy,
                'ico': None, 'organizacia_nazov': None,
                'dic': None, 'ic_dph': None, 'sidlo_ulica': None, 'sidlo_psc': None, 'sidlo_mesto': None,
                'org_zaradenie': None, 'org_zaradenie_ine': None,
                'rola': rola,
                'hud_oblast': hud_oblast,
                'hud_spec': hud_spec,
                'tanec_spec': tanec_spec,
                'tanec_ine': tanec_ine,
                'ucitel_predmety': ucitel_predmety,
                'ucitel_ine': ucitel_ine,
            })

            exist = Pouzivatel.query.filter(
                (Pouzivatel.email == email) | (Pouzivatel.prezyvka == prezyvka)
            ).first()
            if exist:
                flash("Používateľ s týmto e-mailom alebo prezývkou už existuje.", "warning")
                return redirect(url_for('uzivatel.registracia'))

        # --- podpíš dáta a pošli e-mail
        s = _make_serializer()
        token = s.dumps(data)  # obsahuje všetky polia; heslo už je hash
        link = url_for('uzivatel.over_registraciu', t=token, _external=True)

        try:
            _send_verif_email(email, link)
        except Exception:
            current_app.logger.exception("Send verification email failed")
            flash("Nepodarilo sa odoslať verifikačný e-mail. Skús neskôr.", "danger")
            return redirect(url_for('uzivatel.registracia'))

        # DEV: rovno presmeruj na overenie (bez klikania v e-maile)
        if current_app.config.get('REG_DEV_AUTOVERIFY'):
            return redirect(url_for('uzivatel.over_registraciu', t=token))

        flash("Poslali sme ti e-mail s potvrdením. Dokonči registráciu kliknutím na odkaz (48 hod.).", "success")
        return redirect(url_for('main.index'))

    # GET
    return render_template('modals/registracia.html')


# 🔒 Overenie registrácie – vytvorenie účtu z tokenu
@uzivatel.route('/registracia/overenie')
def over_registraciu():
    from flask import request
    t = request.args.get('t')
    if not t:
        flash('Chýba overovací token.', 'danger')
        return redirect(url_for('uzivatel.registracia'))

    s = _make_serializer()
    try:
        data = s.loads(t, max_age=60 * 60 * 48)  # 48 hodín
    except SignatureExpired:
        flash('Overovací odkaz vypršal. Zaregistruj sa prosím znova.', 'warning')
        return redirect(url_for('uzivatel.registracia'))
    except BadSignature:
        flash('Neplatný overovací odkaz.', 'danger')
        return redirect(url_for('uzivatel.registracia'))

    # už existuje?
    if Pouzivatel.query.filter_by(email=data['email']).first():
        flash('Účet už existuje. Skús sa prihlásiť.', 'info')
        return redirect(url_for('uzivatel.login'))

    passwd_hash = data.get('heslo')
    if not passwd_hash:
        flash('Chýba heslo v overovacom odkaze. Skús registráciu znova.', 'danger')
        return redirect(url_for('uzivatel.registracia'))

    u = Pouzivatel(
        prezyvka=data.get('prezyvka'),
        meno=data.get('meno'),
        priezvisko=data.get('priezvisko'),
        email=data['email'],
        heslo=passwd_hash,                      # ⟵ HASH z tokenu
        instrument=data.get('instrument'),
        doplnkovy_nastroj=data.get('doplnkovy_nastroj'),
        obec=data.get('obec'),
        typ_subjektu=data.get('typ_subjektu', 'fyzicka'),
        ico=data.get('ico'),
        organizacia_nazov=data.get('organizacia_nazov'),
        dic=data.get('dic'),
        ic_dph=data.get('ic_dph'),
        sidlo_ulica=data.get('sidlo_ulica'),
        sidlo_psc=data.get('sidlo_psc'),
        sidlo_mesto=data.get('sidlo_mesto'),
        org_zaradenie=data.get('org_zaradenie'),
        org_zaradenie_ine=data.get('org_zaradenie_ine'),
        rola=data.get('rola'),
        hud_oblast=data.get('hud_oblast'),
        hud_spec=data.get('hud_spec'),
        tanec_spec=data.get('tanec_spec'),
        tanec_ine=data.get('tanec_ine'),
        ucitel_predmety=data.get('ucitel_predmety'),
        ucitel_ine=data.get('ucitel_ine'),
    )
    db.session.add(u)
    db.session.commit()

    login_user(u)
    flash(f"Registrácia potvrdená. Vitaj, {u.prezyvka or u.email}!", "success")
    return redirect(url_for('uzivatel.profil'))

# 🔹 Logout
@uzivatel.route('/logout')
@login_required
def logout():
    logout_user()
    # flash správa po odhlásení
    flash("Úspešne ste sa odhlásili.", "info")  # alebo "success"
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

@uzivatel.get("/api/ico-lookup", endpoint="ico_lookup")
def ico_lookup():
    ico = (request.args.get("ico") or "").strip()
    if not re.fullmatch(r"\d{6,10}", ico):
        return jsonify({"error": "invalid_ico"}), 400

    data = lookup_ico_provider(ico)
    if not data:
        return jsonify({"error": "not_found"}), 404
    return jsonify(data)

def lookup_ico_provider(ico: str):
    """
    Sem neskôr napojíš reálny register (FinStat/RPO/ORSR).
    Zatiaľ dev MOCK, aby frontend fungoval – nič iné v aplikácii to neovplyvní.
    """
    if ico == "12345678":
        return {
            "nazov": "Muzikuj s.r.o.",
            "dic": "2020999999",
            "ic_dph": "SK2020999999",
            "ulica": "Hudobná 5",
            "psc": "82105",
            "mesto": "Bratislava",
        }
    return None
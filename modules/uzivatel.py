import os
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, abort, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from sqlalchemy.orm import joinedload
from jinja2 import TemplateNotFound
from models import Pouzivatel, db, GaleriaPouzivatel, VideoPouzivatel, Skupina, Podujatie, Reklama, Mesto
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

# 🔹 Mesta
def get_mesta_all():
    return Mesto.query.order_by(Mesto.nazov.asc()).all()

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
    import json
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

        # malá pomôcka
        def dedup_list(lst):
            return [x for x in dict.fromkeys((x or '').strip() for x in lst if (x or '').strip())]

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
                'prezyvka': organizacia_nazov,
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
                'moderator_podrola': None,
            })

            exist = Pouzivatel.query.filter(
                (Pouzivatel.email == email) | (Pouzivatel.prezyvka == organizacia_nazov)
            ).first()
            if exist:
                flash("Používateľ s týmto e-mailom alebo názvom už existuje.", "warning")
                return redirect(url_for('uzivatel.registracia'))

            # role_data prázdne (organizácia)
            data['role_data'] = json.dumps({}, ensure_ascii=False)

        else:
            # Fyzická osoba
            prezyvka   = (request.form.get('prezyvka') or '').strip()
            meno       = (request.form.get('meno') or '').strip() or None
            priezvisko = (request.form.get('priezvisko') or '').strip() or None
            if not prezyvka:
                flash("Prezývka je povinná pre fyzickú osobu.", "warning")
                return redirect(url_for('uzivatel.registracia'))

            # primárna rola
            rola = (request.form.get('rola') or '').strip() or None

            # HUDOBNÍK
            hud_oblast = (request.form.get('hud_oblast') or '').strip() or None
            hud_spec = (request.form.get('hud_spec') or '').strip()
            if not hud_spec:
                hud_spec = (request.form.get('hud_spec_free') or '').strip()
            if not hud_spec:
                hud_spec_multi = request.form.getlist('hud_spec_multi')  # ak používaš [] názvy, prispôsob
                hud_spec_multi = dedup_list(hud_spec_multi)
                hud_spec = ','.join(hud_spec_multi) if hud_spec_multi else None

            # TANEČNÍK
            tanec_spec_list = dedup_list(request.form.getlist('tanec_spec_multi'))
            tanec_spec = ','.join(tanec_spec_list) if tanec_spec_list else None
            tanec_ine = (request.form.get('tanec_ine_text') or '').strip() or None

            # MODERÁTOR
            podrola_multi = dedup_list(request.form.getlist('podrola_multi'))
            if not podrola_multi:
                one = (request.form.get('podrola') or '').strip()
                if one:
                    podrola_multi = [one]
            moderator_podrola = ','.join(podrola_multi) if podrola_multi else None

            # UČITEĽ HUDBY
            ucitel_list = dedup_list(request.form.getlist('ucitel_predmety_multi'))
            ucitel_predmety = ','.join(ucitel_list) if ucitel_list else None
            ucitel_ine = (request.form.get('ucitel_ine_text') or '').strip() or None

            # „Iné“ rola
            rola_ina = (request.form.get('rola_ina') or '').strip() or None

            # jednoduché roly (fotograf, videograf, …) – ak ich máš v registrácii
            simple_roles = dedup_list(request.form.getlist('simple_role_multi'))

            instrument = (request.form.get('instrument') or '').strip() or None
            doplnkovy  = (request.form.get('doplnkovy_nastroj') or '').strip() or None

            data.update({
                'prezyvka': prezyvka,
                'meno': meno, 'priezvisko': priezvisko,
                'instrument': instrument, 'doplnkovy_nastroj': doplnkovy,
                'ico': None, 'organizacia_nazov': None,
                'dic': None, 'ic_dph': None, 'sidlo_ulica': None, 'sidlo_psc': None, 'sidlo_mesto': None,
                'org_zaradenie': None, 'org_zaradenie_ine': None,

                # legacy stĺpce (aby bolo kompatibilné a profil to vedel čítať aj bez role_data)
                'rola': rola,
                'hud_oblast': hud_oblast,
                'hud_spec': hud_spec,
                'tanec_spec': tanec_spec,
                'tanec_ine': tanec_ine,
                'ucitel_predmety': ucitel_predmety,
                'ucitel_ine': ucitel_ine,
                'moderator_podrola': moderator_podrola,
                'rola_ina': rola_ina,
            })

            exist = Pouzivatel.query.filter(
                (Pouzivatel.email == email) | (Pouzivatel.prezyvka == prezyvka)
            ).first()
            if exist:
                flash("Používateľ s týmto e-mailom alebo prezývkou už existuje.", "warning")
                return redirect(url_for('uzivatel.registracia'))

            # ---- role_data JSON (future-proof, rovnaké ako v edite) ----
            rd = {}

            # HUDOBNÍK
            hud_spec_list = [s.strip() for s in (hud_spec or '').split(',') if s.strip()]
            if hud_oblast or hud_spec_list:
                rd['hudobnik'] = {'hud_oblast': hud_oblast, 'hud_spec': hud_spec_list}

            # TANEČNÍK
            if tanec_spec_list or (tanec_ine and tanec_ine.strip()):
                rd['tanecnik'] = {'tanec_spec': tanec_spec_list, 'tanec_ine': tanec_ine or None}

            # MODERÁTOR
            if podrola_multi:
                rd['moderator'] = {'podrola': podrola_multi}

            # UČITEĽ HUDBY (len ak má niečo vybraté)
            if ucitel_list or (ucitel_ine and ucitel_ine.strip()):
                rd['ucitel_hudby'] = {'ucitel_predmety': ucitel_list, 'ucitel_ine': ucitel_ine or None}

            # „Iné“ rola
            if rola == 'ine' and rola_ina:
                rd['ine'] = {'rola_ina': rola_ina}

            # SIMPLE roly
            if simple_roles:
                rd['simple_roles'] = simple_roles

            data['role_data'] = json.dumps(rd, ensure_ascii=False)

        # --- podpíš dáta a pošli e-mail
        s = _make_serializer()
        token = s.dumps(data)  # obsahuje všetky polia vrátane role_data; heslo už je hash
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
    return render_template('modals/registracia.html', mesta_all=get_mesta_all())


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
    flash("Úspešne ste sa odhlásili.", "info")
    return redirect(url_for('uzivatel.index'))


@uzivatel.route('/moje-konto', methods=['GET', 'POST'])
@uzivatel.route('/profil', methods=['GET', 'POST'], endpoint='profil')
@login_required
def moje_konto():
    import json
    pouzivatel = current_user

    if request.method == 'POST':
        # helpers ...
        def val(name: str, default=None):
            v = request.form.get(name, default)
            if isinstance(v, str):
                v = v.strip()
            return v if v not in ("", None) else None

        def list_from_any(*names):
            for nm in names:
                raw = request.form.getlist(nm)
                if raw:
                    seen, out = set(), []
                    for it in raw:
                        s = (it or '').strip()
                        if s and s not in seen:
                            seen.add(s); out.append(s)
                    if out:
                        return out
            return []

        def csv_join(items):
            return ",".join(items) if items else None

        # --- 0) RD načítaj RAZ ---
        try:
            rd = json.loads(pouzivatel.role_data or "{}")
            if not isinstance(rd, dict):
                rd = {}
        except Exception:
            rd = {}

        # --- základné polia ---
        for k in ("prezyvka", "meno", "priezvisko", "email", "obec", "bio"):
            setattr(pouzivatel, k, val(k, getattr(pouzivatel, k)))

        # --- primárna rola ---
        primary_role = val("rola")
        if primary_role:
            pouzivatel.rola = primary_role

        # --- SIMPLE ROLES -> rd["simple_roles"] ---
        simple_roles = request.form.getlist("simple_role_multi")
        simple_roles = [r for r in dict.fromkeys((r or "").strip() for r in simple_roles if (r or "").strip())]
        rd.pop("extra_roles", None)       # cleanup starého kľúča
        rd["simple_roles"] = simple_roles

        # --- HUDOBNÍK (legacy stĺpce)
        if any(n in request.form for n in ("hud_oblast","hud_spec[]","hud_spec_multi","hud_spec_extra")):
            pouzivatel.hud_oblast = val("hud_oblast")
            spec_list = list_from_any("hud_spec[]", "hud_spec_multi")
            spec_extra = val("hud_spec_extra")
            if spec_extra:
                spec_list.append(spec_extra)
            pouzivatel.hud_spec = csv_join(spec_list)

        # --- TANEČNÍK (legacy)
        if any(n in request.form for n in ("tanec_spec_multi","tanec_spec[]","tanec_ine_text","tanec_ine")):
            tan_list = list_from_any("tanec_spec_multi", "tanec_spec[]")
            pouzivatel.tanec_spec = csv_join(tan_list)
            pouzivatel.tanec_ine  = val("tanec_ine_text") or val("tanec_ine")

        # --- MODERÁTOR (legacy – CSV)
        if any(n in request.form for n in ("podrola_multi","podrola[]","podrola")):
            pod_list = list_from_any("podrola_multi", "podrola[]")
            if not pod_list:
                v = val("podrola")
                pod_list = [v] if v else []
            pouzivatel.moderator_podrola = csv_join(pod_list)

        # --- UČITEĽ HUDBY (legacy + uprac JSON) ---
        if any(n in request.form for n in ("ucitel_predmety_multi","ucitel_predmety[]","ucitel_ine_text","ucitel_ine")):
            uc_list = list_from_any("ucitel_predmety_multi", "ucitel_predmety[]")
            uc_ine  = val("ucitel_ine_text") or val("ucitel_ine")

            pouzivatel.ucitel_predmety = csv_join(uc_list)
            pouzivatel.ucitel_ine      = uc_ine

            # tu UPRAC rd tak, aby “Učiteľ hudby” nezostal, keď je prázdny
            if uc_list or (uc_ine and uc_ine.strip()):
                rd["ucitel_hudby"] = {
                    "ucitel_predmety": uc_list,
                    "ucitel_ine": uc_ine or None
                }
            else:
                rd.pop("ucitel_hudby", None)

        # --- „Iné“ rola (legacy)
        if "rola_ina" in request.form:
            pouzivatel.rola_ina = val("rola_ina")

        # --- typ účtu + IČO ---
        typ = val('typ_subjektu', pouzivatel.typ_subjektu or 'fyzicka') or 'fyzicka'
        pouzivatel.typ_subjektu = typ
        ico_keys = ("organizacia_nazov","ico","org_zaradenie","org_zaradenie_ine","dic","ic_dph","sidlo_ulica","sidlo_psc","sidlo_mesto")
        if typ == 'ico':
            for k in ico_keys:
                if hasattr(pouzivatel, k):
                    setattr(pouzivatel, k, val(k))
        else:
            for k in ico_keys:
                if hasattr(pouzivatel, k):
                    setattr(pouzivatel, k, None)

        # --- 1) ULOŽ upravené rd SPÄŤ do modelu (DÔLEŽITÉ!) ---
        pouzivatel.role_data = json.dumps(rd, ensure_ascii=False)

        db.session.commit()
        flash("Profil bol úspešne upravený", "success")
        return redirect(url_for('uzivatel.profil'))

    # GET – simple_roles na predvyplnenie
    try:
        rd = json.loads(pouzivatel.role_data or "{}")
        simple_roles = set(rd.get("simple_roles", [])) if isinstance(rd, dict) else set()
    except Exception:
        simple_roles = set()

    skupina = pouzivatel.skupina_clen[0] if getattr(pouzivatel, 'skupina_clen', None) else None
    galeria = skupina.galeria if skupina else []
    youtube_videa = pouzivatel.videa

    return render_profile_template(
        pouzivatel=pouzivatel,
        skupina=skupina,
        galeria=galeria,
        youtube_videa=youtube_videa,
        simple_roles=simple_roles,
        public_view=False,
        show_edit=(request.args.get('edit') == '1'),
        mesta_all=get_mesta_all(),
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
        public_view=True,
        mesta_all=get_mesta_all(),
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
# modules/dopyty.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import current_user, login_required
from models import db, Dopyt, Mesto
from datetime import datetime, timedelta, time, date
from itsdangerous import URLSafeTimedSerializer, BadSignature
import smtplib
from email.message import EmailMessage
from sqlalchemy import or_

# KATEGÓRIE (kto objednáva)
KATEGORIE = [
    ("sukromna", "Súkromná udalosť"),
    ("obec", "Obec / mesto"),
    ("firemna", "Firemná akcia"),
    ("cirkev", "Cirkevná udalosť"),
    ("skola", "Školská udalosť"),
    ("klub", "Klub / bar / gastro"),
    ("neziskovka", "Neziskovka / charita"),
    ("ine", "Iné"),
]

# TYPY akcií (niektoré sú „shared“ vo viacerých kategóriách)
TYPY = [
    # súkromná
    {"slug":"svadba","label":"Svadba","groups":["sukromna"]},
    {"slug":"oslava","label":"Oslava / jubileum","groups":["sukromna"]},
    {"slug":"stretavka","label":"Stretávka / párty","groups":["sukromna"]},
    {"slug":"krstiny","label":"Krstiny","groups":["sukromna"]},
    {"slug":"rozlucka","label":"Rozlúčka so slobodou","groups":["sukromna"]},
    {"slug":"smutocna","label":"Smútočná rozlúčka","groups":["sukromna"]},

    # shared
    {"slug":"silvester","label":"Silvester","groups":["sukromna","obec"]},
    {"slug":"ples","label":"Ples","groups":["obec","skola","firemna"]},
    {"slug":"festival","label":"Festival","groups":["obec","neziskovka","klub"]},
    {"slug":"koncert","label":"Koncert","groups":["klub","obec","neziskovka","firemna","cirkev"]},

    # obec/mesto
    {"slug":"jarmok","label":"Jarmok / hody / dedinská zábava","groups":["obec"]},
    {"slug":"dni_mesta","label":"Dni obce / mesta","groups":["obec"]},
    {"slug":"festival_obecny","label":"Obecný festival / vinobranie / dožinky","groups":["obec"]},
    {"slug":"fasangy","label":"Fašiangy / karneval","groups":["obec"]},
    {"slug":"mikulasska","label":"Mikuláš / vianočné trhy","groups":["obec"]},
    {"slug":"den_deti","label":"Deň detí","groups":["obec"]},
    {"slug":"ples_obecny","label":"Obecný ples","groups":["obec"]},

    # firemná
    {"slug":"firemny_vecierok","label":"Firemný večierok","groups":["firemna"]},
    {"slug":"teambuilding","label":"Teambuilding","groups":["firemna"]},
    {"slug":"gala","label":"Gala / ples firmy","groups":["firemna"]},
    {"slug":"otvorenie_prevadzky","label":"Otvorenie prevádzky / promo","groups":["firemna"]},
    {"slug":"konferencia","label":"Konferencia / recepcia","groups":["firemna"]},
    {"slug":"family_day","label":"Family day","groups":["firemna"]},

    # cirkev
    {"slug":"odpust_puc","label":"Odpust / púť","groups":["cirkev"]},
    {"slug":"farsky_den","label":"Farský deň","groups":["cirkev"]},
    {"slug":"prijimanie_birmovka","label":"1. sv. prijímanie / birmovka","groups":["cirkev"]},
    {"slug":"beneficny_koncert","label":"Benefičný koncert","groups":["cirkev","neziskovka"]},

    # škola
    {"slug":"stuzkova","label":"Stužková","groups":["skola"]},
    {"slug":"imatrikulacia","label":"Imatrikulácia","groups":["skola"]},
    {"slug":"skolsky_ples","label":"Školský ples","groups":["skola"]},

    # klub/bar
    {"slug":"klubovy_koncert","label":"Klubový koncert","groups":["klub"]},
    {"slug":"jam_session","label":"Jam session","groups":["klub"]},
    {"slug":"tematicky_vecer","label":"Tematický večer","groups":["klub"]},

    # neziskovka
    {"slug":"charita_beneficia","label":"Charitatívna / benefičná akcia","groups":["neziskovka"]},

    # fallbacky
    {"slug":"ine_sukromne","label":"Iné (súkromné)","groups":["sukromna"]},
    {"slug":"ine_obecne","label":"Iné (obecné)","groups":["obec"]},
    {"slug":"ine_firemne","label":"Iné (firemné)","groups":["firemna"]},
    {"slug":"ine_cirkevne","label":"Iné (cirkevné)","groups":["cirkev"]},
    {"slug":"ine_skoly","label":"Iné (školy)","groups":["skola"]},
    {"slug":"ine_klub","label":"Iné (klub/bar)","groups":["klub"]},
    {"slug":"ine_neziskovka","label":"Iné (neziskovka)","groups":["neziskovka"]},
    {"slug":"ine","label":"Iné","groups":["ine"]},
]

dopyty = Blueprint('dopyty', __name__)

# =========================
# Pomocné funkcie
# =========================

def _dopyt_end_dt(d: Dopyt) -> datetime:
    """
    Vypočíta "koniec udalosti" pre dopyt:
      - ak je cas_do -> dátum + cas_do
      - ak je len cas_od -> dátum + cas_od + 4h (rozumný default)
      - ak nie je žiadny čas -> 23:59 daného dňa
      - ak chýba dátum -> nikdy neexpiruje (datetime.max)
    """
    if not d.datum:
        return datetime.max
    if d.cas_do:
        return datetime.combine(d.datum, d.cas_do)
    if d.cas_od:
        return datetime.combine(d.datum, d.cas_od) + timedelta(hours=4)
    return datetime.combine(d.datum, time(23, 59))

def _housekeep_expired():
    """Deaktivuj (soft delete) všetky aktívne dopyty, ktorým už uplynul termín."""
    now = datetime.utcnow()
    zmenene = False
    for d in Dopyt.query.filter_by(aktivny=True).all():
        if now > _dopyt_end_dt(d):
            d.aktivny = False
            d.zmazany_at = now
            zmenene = True
    if zmenene:
        db.session.commit()

def _ts() -> URLSafeTimedSerializer:
    # Unikátna soľ pre tokeny dopytov
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="dopyt-delete")

def generate_dopyt_token(dopyt_id: int, email: str) -> str:
    return _ts().dumps({"id": dopyt_id, "email": email})

def load_dopyt_token_noage(token: str):
    """Over podpis tokenu a vráť payload bez časovej expirácii (expiráciu riešime dátumom akcie)."""
    try:
        return _ts().loads(token)
    except BadSignature:
        return None

def _send_email(to_email: str, subject: str, body_text: str) -> bool:
    """Jednoduché odoslanie e-mailu cez SMTP podľa app.config (SMTP_SERVER, SMTP_PORT, ...)."""
    cfg = current_app.config
    server = cfg.get("SMTP_SERVER")
    port = int(cfg.get("SMTP_PORT", 587))
    username = cfg.get("SMTP_USERNAME")
    password = cfg.get("SMTP_PASSWORD")
    sender   = cfg.get("SMTP_SENDER", username)

    if not (server and username and password and sender and to_email):
        current_app.logger.warning("SMTP not configured properly; skipping email send.")
        return False

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text)

    with smtplib.SMTP(server, port) as s:
        s.starttls()
        s.login(username, password)
        s.send_message(msg)
    return True


# =========================
# Zoznam dopytov (len prihlásený)
# =========================
@dopyty.route('/dopyty', methods=['GET'])
@login_required
def zobraz_dopyty():
    # uprac expirované dopyty
    _housekeep_expired()

    q = Dopyt.query.filter_by(aktivny=True)

    # filtre
    typ_akcie = (request.args.get('typ_akcie') or '').strip()
    datum_s   = (request.args.get('datum') or '').strip()
    mesto_id  = request.args.get('mesto_id', type=int)  # ak máš ešte select na mesto

    if typ_akcie:
        q = q.filter(Dopyt.typ_akcie == typ_akcie)
    if mesto_id:
        q = q.filter(Dopyt.mesto_id == mesto_id)
    if datum_s:
        try:
            d = datetime.strptime(datum_s, "%Y-%m-%d").date()
            q = q.filter(Dopyt.datum == d)
        except ValueError:
            pass

    dopyty_zoznam = (q.order_by(Dopyt.created_at.desc(), Dopyt.id.desc()).all())

    # ak šablóna ešte očakáva 'mesta', pošli ich; ak tabuľku nechceš používať, môže byť aj []
    try:
        mesta = Mesto.query.order_by(Mesto.kraj, Mesto.okres, Mesto.nazov).all()
    except Exception:
        mesta = []

    return render_template(
    'dopyty.html',
    dopyty=dopyty_zoznam,
    mesta=mesta,
    kategorie=KATEGORIE,
    typy=TYPY
)

# =========================
# Formulár na pridanie dopytu (GET)
# =========================

@dopyty.route('/dopyty/pridat', methods=['GET'])
def formular_dopyt():
    return redirect(url_for('dopyty.zobraz_dopyty', open='dopyt'))




# =========================
# Pridanie dopytu (POST)
# =========================
@dopyty.route('/pridaj_dopyt', methods=['POST'], endpoint='pridaj_dopyt_post')
def pridaj_dopyt():
    # honeypot proti spamu
    if (request.form.get('website') or '').strip():
        flash('Formulár bol zablokovaný (spam).', 'warning')
        return redirect(url_for('dopyty.zobraz_dopyty'))

    g = request.form.get

    # 1) “kto” zatiaľ nepíšeme do DB – iba front-end filter
    kto = (g('kto') or '').strip()

    # 2) typ akcie (+ vlastný pri „Iné“)
    typ_akcie = (g('typ_akcie') or '').strip()
    typ_akcie_custom = (g('typ_akcie_custom') or '').strip()
    if typ_akcie in {'ine','ine_sukromne','ine_obecne','ine_firemne','ine_cirkevne','ine_skoly','ine_klub','ine_neziskovka'} and typ_akcie_custom:
        typ_akcie = typ_akcie_custom

    # 3) dátum/čas
    datum_s   = (g('datum') or '').strip()
    cas_od_s  = (g('cas_od') or '').strip()
    cas_do_s  = (g('cas_do') or '').strip()
    datum  = datetime.strptime(datum_s, '%Y-%m-%d').date() if datum_s else None
    cas_od = datetime.strptime(cas_od_s, '%H:%M').time() if cas_od_s else None
    cas_do = datetime.strptime(cas_do_s, '%H:%M').time() if cas_do_s else None

    # 4) miesto – FK alebo voľný text
    mesto_id_raw = (g('mesto_id') or '').strip()
    mesto_id = int(mesto_id_raw) if mesto_id_raw.isdigit() else None
    miesto_txt = (g('miesto') or '').strip() or None

    # 5) CENA
    cena_typ = (g('cena_typ') or 'dohodou').strip()
    if cena_typ == 'rozpocet':
        rozpocet_s = (g('rozpocet') or '').strip().replace(',', '.')
        try:
            rozpocet = float(rozpocet_s)
        except ValueError:
            rozpocet = None
    else:
        rozpocet = None

    # 6) Ostatné
    popis = (g('popis') or '').strip() or None
    meno  = (g('meno') or '').strip() or None
    email = (g('email') or '').strip() or None

    # --- vytvor záznam (default aktivny=True) a získaj id
    novy = Dopyt(
        typ_akcie = typ_akcie or None,
        datum     = datum,
        cas_od    = cas_od,
        cas_do    = cas_do,
        mesto_id  = mesto_id,
        miesto    = (None if mesto_id else miesto_txt),
        rozpocet  = rozpocet,
        popis     = popis,
        meno      = meno,
        email     = email,
        pouzivatel_id = (current_user.id if current_user.is_authenticated else None),
        aktivny   = True
    )
    db.session.add(novy)
    db.session.flush()  # máme novy.id

    # --- auto-moderácia nad textom (bez auto-banov)
    to_check = "\n".join([x for x in [typ_akcie, popis, miesto_txt] if x])
    res = auto_moderate_text(
        text=to_check,
        entity_type="dopyt",
        entity_id=novy.id,
        recipient_id=None  # pri dopyte nie je “recipient”
    )

    # hard-block => nenecháme publikovať
    if res.get("note") == "hard-block":
        novy.aktivny = False

    # hold => čaká na schválenie (skryté z listu)
    if res.get("held"):
        novy.aktivny = False

    db.session.commit()

    # --- manažovací link (aj keď je hold/hard-block, pošleme iba majiteľovi)
    manage_url = None
    sent = False
    if novy.email:
        token = generate_dopyt_token(novy.id, novy.email)
        try:
            manage_url = url_for("dopyty.spravovat", token=token, _external=True)
        except Exception:
            manage_url = f"{request.url_root.rstrip('/')}{url_for('dopyty.spravovat', token=token)}"

        subject = "Váš dopyt bol pridaný – Muzikuj"
        status_line = ("(Čaká na schválenie moderátorom)\n\n" if not novy.aktivny else "")
        body = (
            "Dobrý deň,\n\n"
            "váš dopyt bol uložený na Muzikuj.\n"
            f"{status_line}"
            f"Spravovať / zmazať ho môžete tu:\n{manage_url}\n\n"
            "Po termíne udalosti sa dopyt automaticky deaktivuje.\n\n"
            "Pekný deň,\nMuzikuj"
        )
        sent = _send_email(novy.email, subject, body)

    # --- hlášky pre užívateľa
    if not novy.aktivny:
        flash("Dopyt bol uložený a čaká na schválenie moderátorom.", "warning")
    else:
        flash("Dopyt bol pridaný!", "success")

    if current_user.is_authenticated:
        return redirect(url_for('dopyty.zobraz_dopyty'))

    # fallback stránka, ak SMTP nie je
    if novy.email and not sent and manage_url:
        return render_template("dopyt_pridany.html", manage_url=manage_url)

    return redirect(url_for('main.index'))

# =========================
# Správa dopytu cez token (GET) + zmazanie (POST)
# =========================
@dopyty.route("/spravovat", methods=["GET"], endpoint="spravovat")
def spravovat():
    token = request.args.get("token", "")
    data = load_dopyt_token_noage(token)
    if not data:
        flash("Neplatný odkaz.", "error")
        return redirect(url_for("dopyty.zobraz_dopyty"))

    d = Dopyt.query.get(int(data["id"]))
    if not d or not d.email or d.email.lower() != (data.get("email", "").lower()):
        flash("Dopyt sa nenašiel alebo odkaz nesedí.", "error")
        return redirect(url_for("dopyty.zobraz_dopyty"))

    # Ak už uplynul termín udalosti, považuj za expirované a skry (ak ešte je aktivný)
    if datetime.utcnow() > _dopyt_end_dt(d):
        if d.aktivny:
            d.aktivny = False
            d.zmazany_at = datetime.utcnow()
            db.session.commit()
        flash("Tento dopyt už je po termíne udalosti.", "warning")
        return redirect(url_for("dopyty.zobraz_dopyty"))

    return render_template("dopyt_spravovat.html", dopyt=d, token=token)

@dopyty.route("/zmazat", methods=["POST"], endpoint="zmazat")
def zmazat():
    token = request.form.get("token", "")
    data = load_dopyt_token_noage(token)
    if not data:
        flash("Neplatný odkaz.", "error")
        return redirect(url_for("dopyty.zobraz_dopyty"))

    d = Dopyt.query.get(int(data["id"]))
    if not d or not d.email or d.email.lower() != (data.get("email", "").lower()):
        flash("Dopyt sa nenašiel alebo odkaz nesedí.", "error")
        return redirect(url_for("dopyty.zobraz_dopyty"))

    # Aj keď je po termíne, len ho deaktivuj (ak už nie je)
    if d.aktivny:
        d.aktivny = False
        d.zmazany_at = datetime.utcnow()
        db.session.commit()

    flash("Dopyt bol zmazaný.", "success")
    return redirect(url_for("dopyty.zobraz_dopyty"))

@dopyty.route('/dopyty/<int:dopyt_id>/zmazat', methods=['POST'])
@login_required
def delete_mine(dopyt_id):
    d = Dopyt.query.filter_by(id=dopyt_id, aktivny=True).first_or_404()
    if d.pouzivatel_id != current_user.id:
        abort(403)
    d.aktivny = False
    d.zmazany_at = datetime.utcnow()
    db.session.commit()
    flash('Dopyt bol zmazaný.', 'success')
    return redirect(url_for('dopyty.zobraz_dopyty'))



@dopyty.app_context_processor
def inject_novinky_dopyty():
    try:
        today = date.today()
        novinky = (Dopyt.query
            .filter(Dopyt.aktivny.is_(True), or_(Dopyt.datum == None, Dopyt.datum >= today))
            .order_by(Dopyt.id.desc())
            .limit(5)
            .all())
    except Exception:
        novinky = []
    return dict(novinky_dopyty=novinky)


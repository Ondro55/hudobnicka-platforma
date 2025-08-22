# modules/dopyty.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import current_user, login_required
from models import db, Dopyt, Mesto
from datetime import datetime, timedelta, time
from itsdangerous import URLSafeTimedSerializer, BadSignature
import smtplib
from email.message import EmailMessage

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
    # uprac staré dopyty (po termíne)
    _housekeep_expired()

    q = Dopyt.query.filter_by(aktivny=True)

    # Jednoduché filtre (bez mesta)
    typ_akcie = (request.args.get('typ_akcie') or '').strip()
    datum_s   = (request.args.get('datum') or '').strip()

    if typ_akcie:
        q = q.filter(Dopyt.typ_akcie == typ_akcie)
    if datum_s:
        try:
            d = datetime.strptime(datum_s, "%Y-%m-%d").date()
            q = q.filter(Dopyt.datum == d)
        except ValueError:
            pass

    dopyty_zoznam = q.order_by(Dopyt.datum.asc()).all()

    # 'mesta' posielame prázdne, aby šablóna nespadla (ak ešte má select na mesto).
    return render_template('dopyty.html', dopyty=dopyty_zoznam, mesta=[])


# =========================
# Formulár na pridanie dopytu (GET)
# =========================
@dopyty.route('/dopyty/pridat', methods=['GET'])
def formular_dopyt():
    mesta = Mesto.query.order_by(Mesto.kraj, Mesto.okres, Mesto.nazov).all()
    return render_template('modals/dopyt_form.html', mesta=mesta)



# =========================
# Pridanie dopytu (POST)
# =========================
@dopyty.route('/pridaj_dopyt', methods=['POST'], endpoint='pridaj_dopyt_post')
def pridaj_dopyt():
    # honeypot proti spamu
    if (request.form.get('website') or '').strip():
        flash('Formulár bol zablokovaný (spam).', 'warning')
        return redirect(url_for('dopyty.zobraz_dopyty'))

    get = request.form.get

    typ_akcie = (get('typ_akcie') or '').strip()
    datum_s   = (get('datum') or '').strip()
    cas_od_s  = (get('cas_od') or '').strip()
    cas_do_s  = (get('cas_do') or '').strip()
    rozpocet_s = (get('rozpocet') or '').strip().replace(',', '.')
    popis      = (get('popis') or '').strip()
    meno       = (get('meno') or '').strip()
    email      = (get('email') or '').strip()

    # Textové pole "miesto" (keď už nepoužívame tabuľku miest)
    miesto_txt = (get('miesto') or '').strip() or None

    # Konverzie
    datum  = datetime.strptime(datum_s, '%Y-%m-%d').date() if datum_s else None
    cas_od = datetime.strptime(cas_od_s, '%H:%M').time() if cas_od_s else None
    cas_do = datetime.strptime(cas_do_s, '%H:%M').time() if cas_do_s else None
    try:
        rozpocet = float(rozpocet_s) if rozpocet_s else None
    except ValueError:
        rozpocet = None

    novy = Dopyt(
        typ_akcie=typ_akcie or None,
        datum=datum,
        cas_od=cas_od,
        cas_do=cas_do,
        # Bez FK mesta:
        mesto_id=None,
        mesto=miesto_txt,   # textový fallback
        rozpocet=rozpocet,
        popis=popis or None,
        meno=meno or None,
        email=email or None,
        pouzivatel_id=(current_user.id if current_user.is_authenticated else None),
        aktivny=True
    )

    db.session.add(novy)
    db.session.commit()

    # Po pridaní pošli potvrdenie s linkom na správu (zmazanie)
    if novy.email:
        token = generate_dopyt_token(novy.id, novy.email)
        # _external vyžaduje SERVER_NAME/doménu; inak použi request.url_root
        try:
            manage_url = url_for("dopyty.spravovat", token=token, _external=True)
        except Exception:
            manage_url = f"{request.url_root.rstrip('/')}{url_for('dopyty.spravovat', token=token)}"

        subject = "Váš dopyt bol pridaný – Muzikuj"
        body = (
            f"Dobrý deň,\n\n"
            f"váš dopyt bol úspešne pridaný na Muzikuj.\n\n"
            f"Ak už nie je aktuálny, môžete ho sami zmazať tu:\n{manage_url}\n\n"
            f"Po termíne udalosti sa dopyt automaticky deaktivuje.\n\n"
            f"Pekný deň,\nMuzikuj"
        )
        _send_email(novy.email, subject, body)

    flash('Dopyt bol pridaný!', "success")

    if current_user.is_authenticated:
        return redirect(url_for('dopyty.zobraz_dopyty'))
    else:
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





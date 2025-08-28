from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Pouzivatel, Sprava, Report
from datetime import datetime
import smtplib
from email.message import EmailMessage
from sqlalchemy import func, or_, and_

# bezpečný import – ak utils/moderation neexistuje, app beží ďalej bez auto-flagovania
try:
    from utils.moderation import auto_moderate_text
except Exception:
    auto_moderate_text = None

spravy_bp = Blueprint("spravy", __name__, url_prefix="/spravy")


@spravy_bp.route("/", methods=["GET"], endpoint="inbox")
@login_required
def inbox():
    uid = current_user.id
    tab = request.args.get("tab") or "prijate"
    msg_id = request.args.get("id", type=int)

    # zoznamy: zobraz len to, čo NEbolo zmazané na mojej strane
    prijate  = (Sprava.query
                .filter_by(komu_id=uid, deleted_by_recipient=False)
                .order_by(Sprava.datum.desc()).all())
    odoslane = (Sprava.query
                .filter_by(od_id=uid, deleted_by_sender=False)
                .order_by(Sprava.datum.desc()).all())

    # vybraný detail – len ak patrí userovi a nie je „zmazaný na jeho strane“
    vybrana = None
    if msg_id:
        cond = or_(
            and_(Sprava.komu_id == uid, Sprava.deleted_by_recipient == False),
            and_(Sprava.od_id   == uid, Sprava.deleted_by_sender    == False),
        )
        vybrana = Sprava.query.filter(Sprava.id == msg_id, cond).first()

        # označ ako prečítané (len prijaté a nie už zmazané na mojej strane)
        if vybrana and vybrana.komu_id == uid and not vybrana.precitane:
            vybrana.precitane = True
            db.session.commit()

    # pre badge v taboch
    unread_prijate = Sprava.query.filter_by(
        komu_id=uid, precitane=False, deleted_by_recipient=False
    ).count()

    active_tab = tab if tab in ("prijate","odoslane","nova") else "prijate"
    return render_template("spravy.html",
        prijate=prijate, odoslane=odoslane,
        active_tab=active_tab, unread_prijate=unread_prijate,
        vybrana=vybrana
    )


# (voliteľne) pekná URL /spravy/sprava/<id> → presmeruje do inboxu s tabuľkou zachovanou
@spravy_bp.route("/sprava/<int:sprava_id>", methods=["GET"], endpoint="detail")
@login_required
def detail(sprava_id):
    # default do prijatých
    return redirect(url_for("spravy.inbox", tab="prijate", id=sprava_id))


@spravy_bp.route("/napisat", methods=["GET"], endpoint="napisat")
@login_required
def napisat():
    kontekst    = request.args.get("kontekst") or "direct"
    kontekst_id = request.args.get("kontekst_id")
    komu_id     = request.args.get("komu_id")
    komu_email  = request.args.get("komu_email")  # môže ísť mimo-užívateľa

    prijemca_nazov = None
    if komu_id and str(komu_id).isdigit():
        u = Pouzivatel.query.get(int(komu_id))
        if u:
            prijemca_nazov = u.prezyvka or u.email

    return render_template(
        "spravy_napisat.html",
        kontekst=kontekst, kontekst_id=kontekst_id,
        komu_id=komu_id, komu_email=komu_email,
        prijemca_nazov=prijemca_nazov
    )


def _send_email(to_email: str, subject: str, body: str) -> bool:
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
    msg.set_content(body)

    with smtplib.SMTP(server, port) as s:
        s.starttls()
        s.login(username, password)
        s.send_message(msg)
    return True


@spravy_bp.route("/odoslat", methods=["POST"], endpoint="odoslat")
@login_required
def odoslat():
    text = (request.form.get("obsah") or "").strip()
    if not text:
        flash("Správa nemôže byť prázdna.", "error")
        return redirect(request.referrer or url_for("spravy.inbox"))

    komu_id     = request.form.get("komu_id")
    komu_email  = request.form.get("komu_email")
    kontekst    = request.form.get("kontekst")
    kontekst_id = request.form.get("kontekst_id")

    # 1) Ulož správu
    s = Sprava(
        obsah=text,
        od_id=current_user.id,
        komu_id=int(komu_id) if (komu_id and str(komu_id).isdigit()) else None,
        komu_email=komu_email or None,
        inzerat_id=int(kontekst_id) if (kontekst == "inzerat" and kontekst_id and str(kontekst_id).isdigit()) else None,
        dopyt_id=int(kontekst_id)   if (kontekst == "dopyt"   and kontekst_id and str(kontekst_id).isdigit()) else None,
    )
    db.session.add(s)
    db.session.commit()

    # 2) Jemné auto-flagovanie (manuálna moderácia, žiadne blokovanie)
    if auto_moderate_text:
        try:
            res = auto_moderate_text(text)
        except TypeError:
            # keby existovala iná signatúra, fallback
            res = {"flag": False}

        if res and res.get("flag"):
            r = Report(
                reporter_id = current_user.id,  # systémovo by to mohlo byť aj None
                entity_type = "sprava",
                entity_id   = s.id,
                reason      = res.get("reason", "nevhodny_obsah"),
                details     = res.get("note", ""),
                status      = "open",
            )
            db.session.add(r)
            db.session.commit()
            # len info – správa ide normálne ďalej
            flash("Správa bola označená na manuálnu kontrolu.", "info")

    # 3) E-mail (ak máme adresu)
    if komu_email:
        subj = f"Reakcia na dopyt #{kontekst_id}" if kontekst == "dopyt" else "Správa z Muzikuj.sk"
        try:
            ok = _send_email(komu_email, subj, text)
            if ok:
                flash("Správa odoslaná aj na e-mail.", "success")
            else:
                flash("Správa uložená, ale e-mail sa nepodarilo odoslať (SMTP).", "warning")
        except Exception:
            current_app.logger.exception("Email send failed")
            flash("Správa uložená, ale e-mail sa nepodarilo odoslať.", "warning")
    else:
        flash("Správa odoslaná.", "success")

    return redirect(url_for("spravy.inbox"))


@spravy_bp.route("/zmazat", methods=["POST"], endpoint="zmazat")
@login_required
def zmazat():
    uid = current_user.id
    tab = (request.form.get("tab") or "prijate").strip()

    ids = request.form.getlist("ids")
    if not ids:
        one = request.form.get("id")
        if one:
            ids = [one]

    # bezpečný cast
    try:
        ids = [int(x) for x in ids if str(x).strip().isdigit()]
    except Exception:
        ids = []

    if not ids:
        flash("Neboli vybrané žiadne správy.", "warning")
        return redirect(url_for("spravy.inbox", tab=tab))

    msgs = Sprava.query.filter(Sprava.id.in_(ids)).all()
    count = 0
    for s in msgs:
        touched = False
        if s.od_id == uid and not s.deleted_by_sender:
            s.deleted_by_sender = True
            touched = True
        if s.komu_id == uid and not s.deleted_by_recipient:
            s.deleted_by_recipient = True
            touched = True
        if touched:
            count += 1

    if count:
        db.session.commit()
        flash(f"Zmazané {count} správy.", "success")
    else:
        flash("Nič sa nezmazalo.", "info")

    return redirect(url_for("spravy.inbox", tab=tab))


@spravy_bp.route("/find-user")
@login_required
def find_user():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify([])

    users = (Pouzivatel.query
             .filter(Pouzivatel.id != current_user.id)
             .filter(func.lower(Pouzivatel.prezyvka).like(f"%{q.lower()}%"))
             .order_by(Pouzivatel.prezyvka.asc())
             .limit(8)
             .all())

    return jsonify([{
        "id": u.id,
        "prezyvka": u.prezyvka,
        "email": u.email
    } for u in users])

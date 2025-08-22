from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Pouzivatel, Sprava
from datetime import datetime
import smtplib
from email.message import EmailMessage
from flask import current_app


spravy_bp = Blueprint("spravy", __name__, url_prefix="/spravy")

@spravy_bp.route("/", methods=["GET"], endpoint="inbox")
@login_required
def inbox():
    uid = current_user.id
    prijate = Sprava.query.filter_by(komu_id=uid).order_by(Sprava.datum.desc()).all()
    odoslane = Sprava.query.filter_by(od_id=uid).order_by(Sprava.datum.desc()).all()

    Sprava.query.filter_by(komu_id=uid, precitane=False).update({Sprava.precitane: True}, synchronize_session=False)
    db.session.commit()

    return render_template("spravy.html", prijate=prijate, odoslane=odoslane)


@spravy_bp.route("/napisat", methods=["GET"], endpoint="napisat")
@login_required
def napisat():
    kontekst    = request.args.get("kontekst") or "direct"
    kontekst_id = request.args.get("kontekst_id")
    komu_id     = request.args.get("komu_id")
    komu_email  = request.args.get("komu_email")  # ✅ pridané

    prijemca_nazov = None
    if komu_id:
        u = Pouzivatel.query.get(int(komu_id))
        if u:
            prijemca_nazov = u.prezyvka or u.email

    return render_template(
        "spravy_napisat.html",
        kontekst=kontekst, kontekst_id=kontekst_id,
        komu_id=komu_id, komu_email=komu_email,   # ✅ posúvame do šablóny
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

    # 1) Ulož do DB (aby bol záznam aj pri e-maily)
    s = Sprava(
        obsah=text,
        od_id=current_user.id,
        komu_id=int(komu_id) if komu_id else None,
        komu_email=komu_email or None,
        inzerat_id=int(kontekst_id) if (kontekst == "inzerat" and kontekst_id) else None,
        dopyt_id=int(kontekst_id)   if (kontekst == "dopyt"   and kontekst_id) else None,
    )
    db.session.add(s)
    db.session.commit()

    # 2) Ak máme e-mail, pošli e-mail
    if komu_email:
        subj = f"Reakcia na dopyt #{kontekst_id}" if kontekst == "dopyt" else "Správa z Muzikuj.sk"
        try:
            ok = _send_email(komu_email, subj, text)
            if ok:
                flash("Správa odoslaná na e-mail.", "success")
            else:
                flash("Správa uložená, ale e-mail sa nepodarilo odoslať (SMTP nenastavené).", "warning")
        except Exception:
            current_app.logger.exception("Email send failed")
            flash("Správa uložená, ale e-mail sa nepodarilo odoslať.", "warning")
    else:
        flash("Správa odoslaná.", "success")

    return redirect(url_for("spravy.inbox"))



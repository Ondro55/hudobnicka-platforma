from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Pouzivatel, Sprava, Report, Dopyt
from modules.dopyty import generate_dopyt_token, _dopyt_end_dt
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
    komu_email  = request.args.get("komu_email")

    prijemca_nazov = None
    predmet = ""  # ⬅️ default

    if kontekst == "dopyt" and kontekst_id and str(kontekst_id).isdigit():
        d = Dopyt.query.get(int(kontekst_id))
        if d:
            prijemca_nazov = d.meno or "Zadávateľ dopytu"
            predmet = f"Re: dopyt – {d.typ_akcie or 'akcia'}"   # ⬅️ jednoduchý subject bez ID
        komu_email = None  # e-mail nezobrazujeme

    elif komu_id and str(komu_id).isdigit():
        u = Pouzivatel.query.get(int(komu_id))
        if u:
            prijemca_nazov = u.prezyvka or "Používateľ"
        predmet = "Správa z Muzikuj"

    return render_template(
        "spravy_napisat.html",
        kontekst=kontekst, kontekst_id=kontekst_id,
        komu_id=komu_id, komu_email=None,
        prijemca_nazov=prijemca_nazov,
        predmet=predmet,                 # ⬅️ pošli do templatu
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
    text    = (request.form.get("obsah") or "").strip()
    predmet = (request.form.get("predmet") or "").strip()   # ⬅️ NOVÉ

    if not text:
        flash("Správa nemôže byť prázdna.", "error")
        return redirect(request.referrer or url_for("spravy.inbox"))

    komu_id     = request.form.get("komu_id")
    komu_email  = request.form.get("komu_email")  # pri dopyte ignorujeme, pošleme na dopyt.email
    kontekst    = request.form.get("kontekst")
    kontekst_id = request.form.get("kontekst_id")

    # 1) Ulož správu do DB
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

    # 2) Jemné auto-flagovanie (manuálna moderácia)
    if auto_moderate_text:
        try:
            res = auto_moderate_text(text)
        except TypeError:
            res = {"flag": False}
        if res and res.get("flag"):
            r = Report(
                reporter_id = current_user.id,
                entity_type = "sprava",
                entity_id   = s.id,
                reason      = res.get("reason", "nevhodny_obsah"),
                details     = res.get("note", ""),
                status      = "open",
            )
            db.session.add(r)
            db.session.commit()
            flash("Správa bola označená na manuálnu kontrolu.", "info")

    # 3) Poslanie e-mailu
    if kontekst == "dopyt" and (kontekst_id or "").isdigit():
        # špeciál: dopyt – posielame na e-mail z dopytu + CTA
        d = Dopyt.query.get(int(kontekst_id))
        if not d or not d.email:
            flash("Dopyt sa nenašiel alebo nemá e-mail.", "warning")
            return redirect(url_for("dopyty.zobraz_dopyty"))
        if not d.aktivny or datetime.utcnow() > _dopyt_end_dt(d):
            flash("Tento dopyt už nie je aktívny.", "warning")
            return redirect(url_for("dopyty.zobraz_dopyty"))

        # predmet – použij ten z formulára, inak jednoduchý fallback
        subj = predmet or f"Re: dopyt – {d.typ_akcie or 'akcia'}"

        # CTA odkazy
        token = generate_dopyt_token(d.id, d.email)
        try:
            agree_url  = url_for("dopyty.cta_agree",  token=token, _external=True)
            nodeal_url = url_for("dopyty.cta_no_deal", token=token, _external=True)
        except Exception:
            base = request.url_root.rstrip("/")
            agree_url  = base + url_for("dopyty.cta_agree",  token=token)
            nodeal_url = base + url_for("dopyty.cta_no_deal", token=token)

        kapela = getattr(current_user, "prezyvka", None) or getattr(current_user, "nazov", None) or "Hudobník"
        body = (
            f"Ahoj {d.meno or ''},\n\n"
            f"{kapela} vám píše k vášmu dopytu:\n\n"
            f"{text}\n\n"
            f"Ak ste sa DOHODLI, kliknite sem (dopyt skryjeme):\n{agree_url}\n\n"
            f"Ak ste sa NEDOHODLI a chcete nechať dopyt aktívny, kliknite sem:\n{nodeal_url}\n\n"
            f"Pekný deň,\nMuzikuj\n"
        )

        try:
            ok = _send_email(d.email, subj, body)
            if ok:
                if not d.cta_sent_at:
                    d.cta_sent_at = datetime.utcnow()
                    db.session.commit()
                flash("Správa odoslaná zadávateľovi e-mailom. 👍", "success")
            else:
                flash("Správa uložená, ale e-mail sa nepodarilo odoslať (SMTP).", "warning")
        except Exception:
            current_app.logger.exception("Email send failed")
            flash("Správa uložená, ale e-mail sa nepodarilo odoslať.", "warning")

        return redirect(url_for("dopyty.zobraz_dopyty"))

    # Ostatné kontexty / direct – pošli na odoslaný komu_email, ak existuje
    if komu_email:
        subj = predmet or "Správa z muzikuj.sk"
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

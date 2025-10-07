# modules/nastavenia.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, current_app
from flask_login import login_required, current_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import NotFound
from models import db, Pouzivatel   # ← dôležité: importujem aj Pouzivatel
from datetime import datetime, timedelta
import secrets, smtplib, ssl
from email.mime.text import MIMEText
from email.utils import formataddr
from urllib.parse import urljoin
from sqlalchemy import or_
import json

# /nastavenia/... (všetky cesty pod týmto prefixom)
nastavenia_bp = Blueprint("nastavenia", __name__, url_prefix="/nastavenia")

# single source of truth pre validáciu tém na backende
ALLOWED_THEMES = set(getattr(Pouzivatel, "THEMES",
                     ("system","light","dark","blue","green","red")))


@nastavenia_bp.get("")
@login_required
def prehlad():
    return render_template("nastavenia.html")

def _send_delete_email(to_email, subject, html_body):
    cfg = current_app.config
    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr(("muzikuj.sk", cfg.get("SMTP_SENDER", "noreply@muzikuj.sk")))
    msg["To"] = to_email

    context = ssl.create_default_context()
    with smtplib.SMTP(cfg["SMTP_SERVER"], cfg["SMTP_PORT"]) as server:
        server.starttls(context=context)
        server.login(cfg["SMTP_USERNAME"], cfg["SMTP_PASSWORD"])
        server.send_message(msg)

@nastavenia_bp.post("/ucet")
@login_required
def ucet():
    action = request.form.get("action")

    # ... (change_password ostáva)

    if action == "request_delete":
        # jednoduché potvrdenie na fronte: <form onsubmit="return confirm('Naozaj...')">
        confirm = request.form.get("confirm_password","")
        if not check_password_hash(current_user.heslo, confirm):
            flash("Potvrdenie heslom nesedí.", "warning")
            return redirect(url_for(".prehlad")+"#ucet")

        # nastaviť stav: čaká na potvrdenie 24h
        token = secrets.token_urlsafe(32)
        current_user.erase_token = token
        current_user.erase_requested_at = datetime.utcnow()
        current_user.erase_deadline_at = datetime.utcnow() + timedelta(hours=24)
        db.session.commit()

        # linky
        base = request.host_url
        confirm_url = urljoin(base, url_for(".erase_confirm", token=token))
        cancel_url  = urljoin(base, url_for(".erase_cancel",  token=token))

        html = f"""
        <div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:auto;line-height:1.5;">
          <h2>Je nám ľúto, že opúšťate muzikuj.sk</h2>
          <p>Ak chcete účet naozaj vymazať, kliknite na tlačidlo nižšie (platí 24 hodín).
             Pred potvrdením sa vás krátko opýtame na dôvod odchodu.</p>
          <p style="margin:20px 0">
            <a href="{confirm_url}" style="background:#b33;color:#fff;padding:12px 18px;border-radius:6px;text-decoration:none;">Potvrdiť vymazanie účtu</a>
          </p>
          <p>Ak ste o vymazanie nežiadali, môžete žiadosť <a href="{cancel_url}">zrušiť</a>.</p>
          <hr style="border:none;border-top:1px solid #eee;margin:20px 0">
          <p style="font-size:13px;color:#666;">Tento odkaz je jednorazový a vyprší o 24 hodín.</p>
        </div>
        """

        try:
            _send_delete_email(current_user.email, "Potvrdenie vymazania účtu – muzikuj.sk", html)
            flash("Verifikácia vymazania účtu vám bola poslaná na e-mail.", "info")
        except Exception as e:
            current_app.logger.error(f"Send delete email failed: {e}")
            flash("Nepodarilo sa odoslať potvrdzovací e-mail. Skúste neskôr.", "danger")
            return redirect(url_for(".prehlad")+"#ucet")

        # okamžitý logout + blokovanie ďalšieho loginu kým je pending
        logout_user()
        return redirect(url_for("uzivatel.login"))

    flash("Neznáma akcia.", "warning")
    return redirect(url_for(".prehlad")+"#ucet")

@nastavenia_bp.route("/sukromie", methods=["POST"])
@login_required
def sukromie():
    # rádia: "1" alebo "0" (fallback na "0", ak by náhodou nič neprišlo)
    verejny_val = request.form.get("verejny_ucet", "0")
    current_user.verejny_ucet = (verejny_val == "1")

    # checkbox: prítomnosť = True
    current_user.povolit_hodnotenie = bool(request.form.get("povolit_hodnotenie"))

    db.session.commit()
    flash("Súkromie uložené.", "success")
    return redirect(url_for(".prehlad") + "#sukromie")


@nastavenia_bp.post("/vzhlad")   # výsledná cesta = /nastavenia/vzhlad
@login_required
def vzhlad():
    theme = request.form.get("theme","system")
    if theme not in ALLOWED_THEMES:
        flash("Neplatná téma.", "warning")
        return redirect(url_for(".prehlad") + "#vzhlad")

    if theme != current_user.theme:
        current_user.theme = theme
        db.session.commit()

    # sync cookie mz_prefs.theme s tým, čo je v DB
    try:
        prefs = json.loads(request.cookies.get("mz_prefs") or "{}")
        if not isinstance(prefs, dict):
            prefs = {}
    except Exception:
        prefs = {}
    prefs["theme"] = theme

    resp = make_response(redirect(url_for(".prehlad") + "#vzhlad"))
    resp.set_cookie("mz_prefs", json.dumps(prefs, ensure_ascii=False),
                    max_age=365*24*3600, samesite="Lax", path="/")
    return resp

@nastavenia_bp.post("/sledovanie")
@login_required
def sledovanie():
    mode = request.form.get("follow_mode","all")
    zanre = request.form.getlist("zanre")            # ['folklor','rock',...]
    entities = request.form.getlist("entities")      # ['kapely','hudobnici',...]

    current_user.follow_mode = mode
    current_user.follow_zanre = ",".join(sorted(set(zanre)))
    current_user.follow_entities = ",".join(sorted(set(entities)))
    db.session.commit()
    flash("Preferencie sledovania uložené.", "success")
    return redirect(url_for(".prehlad") + "#sledovanie")


DELETE_REASONS = [
    ("no_use", "Už službu nevyužívam"),
    ("privacy", "Obavy o súkromie"),
    ("spam", "Príliš veľa notifikácií"),
    ("missing", "Chýbajú mi funkcie"),
    ("bugs", "Technické problémy"),
    ("other", "Iné"),
    ("no_answer", "Nechcem uviesť"),
]

def _find_user_by_token(token):
    if not token:
        return None
    return db.session.query(Pouzivatel).filter(
        Pouzivatel.erase_token == token,
        Pouzivatel.is_deleted == False
    ).first()

@nastavenia_bp.get("/vymazat/<token>")
def erase_confirm(token):
    u = _find_user_by_token(token)
    if not u or not u.erase_pending:
        flash("Odkaz na vymazanie je neplatný alebo vypršal.", "warning")
        return redirect(url_for("uzivatel.index"))
    return render_template("potvrdit_vymazanie.html", token=token, reasons=DELETE_REASONS, user=u)

@nastavenia_bp.post("/vymazat/<token>")
def erase_do(token):
    u = _find_user_by_token(token)
    if not u or not u.erase_pending:
        flash("Odkaz na vymazanie je neplatný alebo vypršal.", "warning")
        return redirect(url_for("uzivatel.index"))

    sel = request.form.getlist("reasons")
    other = (request.form.get("other_text") or "").strip()
    u.erase_feedback = json.dumps({"reasons": sel, "other": other}, ensure_ascii=False)

    # finálne vymazanie (ak nemáš 100% cascade, zvoľ radšej soft delete)
    try:
        db.session.delete(u)              # HARD DELETE
        db.session.commit()
        flash("Účet bol vymazaný. Mrzí nás, že odchádzate.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Delete user failed: {e}")
        flash("Vymazanie sa nepodarilo. Skúste neskôr alebo nás kontaktujte.", "danger")
    return redirect(url_for("uzivatel.index"))

@nastavenia_bp.get("/vymazat-zrusit/<token>")
def erase_cancel(token):
    u = _find_user_by_token(token)
    if not u:
        flash("Odkaz je neplatný alebo už bol použitý.", "warning")
        return redirect(url_for("uzivatel.index"))

    # zrušiť pending
    u.erase_token = None
    u.erase_requested_at = None
    u.erase_deadline_at = None
    db.session.commit()
    flash("Žiadosť o vymazanie bola zrušená. Účet je opäť aktívny.", "info")
    return redirect(url_for("uzivatel.login"))



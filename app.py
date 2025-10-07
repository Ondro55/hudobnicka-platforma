import os
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from flask import template_rendered, current_app, request, g
from flask import Flask, flash, redirect, url_for
from flask import session, render_template_string, make_response
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask.signals import before_render_template
import ipaddress
# DB a modely
from models import db, Pouzivatel, Mesto  # db je tu inicializované až nižšie

# Feature helpers (používaš v šablónach)
from features import has_feature, get_quota, user_plan


# -----------------------------
# APLIKÁCIA & KONFIGURÁCIA
# -----------------------------
app = Flask(__name__, static_folder="static", static_url_path="/static")



# --- GATE NASTAVENIA ---
# tvoju verejnú IP nechaj v ENV: OWNER_IP
OWNER_IP = os.getenv("OWNER_IP", "").strip()
# kód, ktorý dáš testerom
ACCESS_CODE = os.getenv("ACCESS_CODE", "muzikuj-test")
# 1 = gate zapnutý, 0 = vypnutý (dá sa prepínať bez deployu)
GATE_ENABLED = os.getenv("GATE_ENABLED", "1") == "1"

# cesty voľné pre všetkých (healthcheck, stránka s kódom, robots, statika)
OPEN_PATHS = {"/healthz", "/access", "/robots.txt"}

def _safe_ip(ip: str) -> str:
    try:
        ipaddress.ip_address(ip)
        return ip
    except Exception:
        return ""

def get_client_ip() -> str:
    # Render posiela skutočnú IP v X-Forwarded-For
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        first = xff.split(",")[0].strip()
        return _safe_ip(first) or (request.remote_addr or "")
    return request.remote_addr or ""

ACCESS_FORM_HTML = """
<!doctype html>
<html lang="sk">
<head><meta charset="utf-8"><meta name="robots" content="noindex,nofollow">
<title>Prístup – muzikuj.sk</title>
<style>
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#0f172a;color:#e2e8f0}
  .card{background:#111827;padding:24px 28px;border-radius:16px;box-shadow:0 10px 30px rgba(0,0,0,.35);min-width:320px}
  h1{font-size:20px;margin:0 0 12px}
  p{opacity:.8;margin:0 0 14px}
  input{width:100%;padding:10px 12px;border-radius:10px;border:1px solid #334155;background:#0b1220;color:#e2e8f0}
  button{margin-top:12px;width:100%;padding:10px 12px;border-radius:10px;border:0;background:#22c55e;color:#0b1220;font-weight:600;cursor:pointer}
  .err{color:#fca5a5;margin-top:10px}
</style>
</head>
<body>
  <div class="card">
    <h1>🔑 Testovací prístup</h1>
    <p>Zadajte prístupový kód.</p>
    <form method="post">
      <input name="code" placeholder="Prístupový kód" autofocus>
      <button type="submit">Vstúpiť</button>
      {% if error %}<div class="err">{{ error }}</div>{% endif %}
      {% if next %}<input type="hidden" name="next" value="{{ next }}">{% endif %}
    </form>
  </div>
</body>
</html>
"""

@app.route("/access", methods=["GET", "POST"])
def access():
    if request.method == "POST":
        code = (request.form.get("code") or "").strip()
        nxt = request.form.get("next") or "/"
        if ACCESS_CODE and code == ACCESS_CODE:
            session["guest_access_granted"] = True
            return redirect(nxt)
        return render_template_string(ACCESS_FORM_HTML, error="Nesprávny kód.", next=request.args.get("next"))
    return render_template_string(ACCESS_FORM_HTML, error=None, next=request.args.get("next"))

@app.route("/robots.txt")
def robots():
    # Počas testovania zablokuj indexáciu
    resp = make_response("User-agent: *\nDisallow: /\n", 200)
    resp.headers["Content-Type"] = "text/plain; charset=utf-8"
    return resp

@app.before_request
def gatekeeper():
    if not GATE_ENABLED:
        return  # gate je vypnutý

    p = request.path
    if p in OPEN_PATHS or p.startswith("/static/"):
        return

    # voľný vstup pre teba podľa IP
    client_ip = get_client_ip()
    if OWNER_IP and client_ip == OWNER_IP:
        return

    # hostia s už zadaným kódom (session)
    if session.get("guest_access_granted") is True:
        return

    # presmeruj na /access a po úspechu vráť na pôvodnú URL
    nxt = request.full_path if request.query_string else request.path
    return redirect(url_for("access", next=nxt))

@before_render_template.connect_via(app)
def _remember_tpl(sender, template, context, **extra):
    # beží tesne PRED renderom => uvidíš to priamo v base.html
    g._last_template = getattr(template, "name", None) or "?"

app.config["SECRET_KEY"] = "tajnykluc123"
app.config["REG_DEV_AUTOVERIFY"] = True

basedir = os.path.abspath(os.path.dirname(__file__))

# instance/ priečinok (pre SQLite a iné runtime súbory)
os.makedirs(os.path.join(basedir, "instance"), exist_ok=True)

# SQLite databáza v instance/
db_path = os.path.join(basedir, "instance", "muzikuj.db").replace("\\", "/")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Upload cesty
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "profilovky")
app.config["UPLOAD_FOLDER_INZERAT"] = os.path.join(app.root_path, "static", "galeria_inzerat")

# SMTP (vieš prepísať env premennými)
app.config.update(
    SMTP_SERVER=os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
    SMTP_PORT=int(os.environ.get("SMTP_PORT", "587")),
    SMTP_USERNAME=os.environ.get("SMTP_USERNAME"),
    SMTP_PASSWORD=os.environ.get("SMTP_PASSWORD"),
    SMTP_SENDER=os.environ.get("SMTP_SENDER", "noreply@muzikuj.sk"),
)

# -----------------------------
# DB / MIGRÁCIE / LOGIN
# -----------------------------
db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
# nastav route endpoint pre login (uprav, ak máš iný)
login_manager.login_view = "login.login"
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id: str):
    return Pouzivatel.query.get(int(user_id))


# -----------------------------
# TIMEZONE (bezpečne aj na Windows)
# -----------------------------
def _get_app_tz():
    try:
        return ZoneInfo("Europe/Bratislava")
    except ZoneInfoNotFoundError:
        try:
            import tzdata  # noqa: F401  # doplní IANA databázu, ak chýba
            return ZoneInfo("Europe/Bratislava")
        except Exception:
            return dt_timezone.utc


APP_TZ = _get_app_tz()


# -----------------------------
# Jinja filter: localtime
# -----------------------------
@app.template_filter("localtime")
def jinja_localtime(value, fmt="%d.%m.%Y %H:%M"):
    if value is None:
        return ""
    # ak je naivný datetime (UTC z DB), urob ho “aware” v UTC
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_timezone.utc)
    return value.astimezone(APP_TZ).strftime(fmt)


# -----------------------------
# CONTEXT PROCESSORS
# -----------------------------
@app.context_processor
def inject_mesta_all():
    # pri prvom spustení/migráciách môže tabuľka ešte neexistovať
    try:
        mesta = Mesto.query.order_by(Mesto.nazov.asc()).all()
    except Exception:
        mesta = []
    return dict(mesta_all=mesta)


@app.context_processor
def inject_features():
    return dict(
        has_feature=has_feature,
        get_quota=get_quota,
        user_plan=user_plan,
    )


@app.context_processor
def inject_header_badges():
    data = {"neprecitane_count": 0, "neprecitane_forum_count": 0}
    try:
        if current_user.is_authenticated:
            # SPRÁVY
            try:
                from models import Sprava

                data["neprecitane_count"] = (
                    Sprava.query.filter_by(
                        komu_id=current_user.id,
                        precitane=False,
                        deleted_by_recipient=False,
                    ).count()
                )
            except Exception:
                pass

            # FÓRUM
            try:
                from models import ForumNotification

                data["neprecitane_forum_count"] = (
                    ForumNotification.query.filter_by(
                        user_id=current_user.id, read_at=None
                    ).count()
                )
            except Exception:
                pass
    except Exception:
        pass
    return data

@app.context_processor
def inject_dev_flags():
    return {"show_tpl_badge": app.debug or current_app.config.get("SHOW_TPL_BADGE", False)}

# -----------------------------
# BEFORE REQUEST HOOKY
# -----------------------------
_last_housekeep = None
_HOUSEKEEP_INTERVAL = timedelta(minutes=10)


@app.before_request
def global_housekeep():
    global _last_housekeep
    now = datetime.utcnow()
    if _last_housekeep and (now - _last_housekeep) < _HOUSEKEEP_INTERVAL:
        return
    try:
        from modules.dopyty import _housekeep_expired
        _housekeep_expired()

        from modules.komunita import _housekeep_rychle_dopyty
        _housekeep_rychle_dopyty()

        # ⇩⇩ sem to patrí
        from modules.erase_job import run_erase_due
        cnt = run_erase_due()
        if cnt:
            app.logger.info("Anonymized %s users due to erase deadline", cnt)

        _last_housekeep = now
    except Exception as e:
        app.logger.debug(f"Housekeep skipped: {e}")

def run_erase_expired():
    from datetime import datetime
    now = datetime.utcnow()
    rows = (Pouzivatel.query
            .filter(Pouzivatel.erase_token.isnot(None))
            .filter(Pouzivatel.erase_deadline_at.isnot(None))
            .filter(Pouzivatel.erase_deadline_at < now)
            .all())
    for u in rows:
        u.erase_token = None
        u.erase_requested_at = None
        u.erase_deadline_at = None
    if rows:
        db.session.commit()


@app.before_request
def block_banned_users():
    """Zablokuj akcie pre banovaných používateľov."""
    from flask import request

    protected_prefixes = ("/spravy", "/inzerat", "/dopyty")
    if current_user.is_authenticated and current_user.is_banned:
        if request.path.startswith(protected_prefixes) and request.method in (
            "POST",
            "PUT",
            "DELETE",
        ):
            flash(
                f"Tvoj účet je dočasne zablokovaný: {current_user.banned_reason or ''}",
                "danger",
            )
            return redirect(url_for("uzivatel.profil"))

# -----------------------------
# DIAGNOSTIKA
# -----------------------------
@app.route("/_flash_test")
def _flash_test():
    flash("Flash funguje ✅", "success")
    return redirect(url_for("uzivatel.index"))


# -----------------------------
# BLUEPRINTY
# -----------------------------
from modules.uzivatel import uzivatel, profil_blueprint
from modules.dopyty import dopyty
from modules.skupina import skupina_bp
from modules.inzerat import inzerat
from modules.login import login_bp
from modules.register import register_bp
from modules.kalendar import kalendar_bp
from modules.komunita import komunita_bp
from modules.sprava import spravy_bp
from modules.moderacia import moder_bp
from modules.reporting import report_bp
from modules.forum import forum_bp
from modules.podujatie import podujatie_bp
from modules.reklama import reklama_bp
from modules.nastavenia import nastavenia_bp
from modules.ratings import ratings_bp
from modules.erase_job import run_erase_due
from routes import bp as main_blueprint

app.register_blueprint(uzivatel)
app.register_blueprint(profil_blueprint)
app.register_blueprint(dopyty)
app.register_blueprint(skupina_bp)
app.register_blueprint(inzerat)
app.register_blueprint(login_bp)
app.register_blueprint(register_bp)
app.register_blueprint(main_blueprint)
app.register_blueprint(kalendar_bp, url_prefix="/kalendar")
app.register_blueprint(komunita_bp)
app.register_blueprint(spravy_bp)
app.register_blueprint(moder_bp)
app.register_blueprint(report_bp)
app.register_blueprint(forum_bp, url_prefix="/komunita/forum")
app.register_blueprint(podujatie_bp)
app.register_blueprint(reklama_bp)
app.register_blueprint(nastavenia_bp)
app.register_blueprint(ratings_bp)


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    # po baseline DB používaj migrácie (db.create_all() netreba)
    app.run(debug=True)


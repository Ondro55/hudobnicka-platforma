import os
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, flash, redirect, url_for
from flask_login import LoginManager, current_user
from flask_migrate import Migrate

# DB a modely
from models import db, Pouzivatel, Mesto  # db je tu inicializované až nižšie

# Feature helpers (používaš v šablónach)
from features import has_feature, get_quota, user_plan


# -----------------------------
# APLIKÁCIA & KONFIGURÁCIA
# -----------------------------
app = Flask(__name__, static_folder="static", static_url_path="/static")
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


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    # po baseline DB používaj migrácie (db.create_all() netreba)
    app.run(debug=True)

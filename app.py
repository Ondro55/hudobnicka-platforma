import os
from flask import Flask
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from models import Pouzivatel, db
from datetime import timezone
from zoneinfo import ZoneInfo

# Blueprinty
from modules.uzivatel import uzivatel, profil_blueprint
from modules.dopyty import dopyty
from modules.skupina import skupina_bp
from modules.inzerat import inzerat
from modules.login import login_bp
from modules.register import register_bp
from modules.kalendar import kalendar_bp
from modules.komunita import komunita_bp
from modules.sprava import spravy_bp
from routes import bp as main_blueprint

# Aplikácia
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = 'tajnykluc123'

basedir = os.path.abspath(os.path.dirname(__file__))

# ✅ vytvor priečinok instance/, ak chýba
os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)

# ✅ DB cesta identická so seederom + normalizácia lomítok
db_path = os.path.join(basedir, 'instance', 'muzikuj.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path.replace('\\', '/')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'profilovky')
app.config['UPLOAD_FOLDER_INZERAT'] = os.path.join(app.root_path, 'static', 'galeria_inzerat')

APP_TZ = ZoneInfo("Europe/Bratislava")

app.config.update(
    SMTP_SERVER=os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
    SMTP_PORT=int(os.environ.get("SMTP_PORT", "587")),
    SMTP_USERNAME=os.environ.get("SMTP_USERNAME"),         # napr. tvoje@gmail.com
    SMTP_PASSWORD=os.environ.get("SMTP_PASSWORD"),         # app password pri 2FA
    SMTP_SENDER=os.environ.get("SMTP_SENDER", "noreply@muzikuj.sk"),
)

# Databáza a migrácia
db.init_app(app)
migrate = Migrate(app, db)

@app.context_processor
def inject_mesta_all():
    try:
        from models import Mesto
        mesta = Mesto.query.order_by(Mesto.kraj, Mesto.okres, Mesto.nazov).all()
    except Exception:
        mesta = []
    return dict(mesta_all=mesta)
# Login
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return Pouzivatel.query.get(int(user_id))

@app.context_processor
def inject_neprecitane_count():
    try:
        from models import Sprava
        if current_user.is_authenticated:
            c = Sprava.query.filter_by(
                komu_id=current_user.id, precitane=False, deleted_by_recipient=False
            ).count()
        else:
            c = 0
    except Exception:
        c = 0
    return dict(neprecitane_count=c)

@app.template_filter("localtime")
def jinja_localtime(value, fmt="%d.%m.%Y %H:%M"):
    if value is None:
        return ""
    # ak je naivný datetime (UTC z DB), urob ho “aware” v UTC
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    # konverzia do lokálnej zóny + formát
    return value.astimezone(APP_TZ).strftime(fmt)

# Blueprinty
app.register_blueprint(uzivatel)
app.register_blueprint(profil_blueprint)
app.register_blueprint(dopyty)
app.register_blueprint(skupina_bp)
app.register_blueprint(inzerat)
app.register_blueprint(login_bp)
app.register_blueprint(register_bp)
app.register_blueprint(main_blueprint)
app.register_blueprint(kalendar_bp, url_prefix='/kalendar')
app.register_blueprint(komunita_bp)
app.register_blueprint(spravy_bp)

# Spustenie
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

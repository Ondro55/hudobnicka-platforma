import os
from flask import Flask
from flask_migrate import Migrate
from flask_login import LoginManager
from models import Pouzivatel, db

# Blueprinty
from modules.uzivatel import uzivatel, profil_blueprint
from modules.dopyty import dopyty
from modules.skupina import skupina_bp
from modules.inzerat import inzerat
from modules.login import login_bp
from modules.register import register_bp
from modules.kalendar import kalendar_bp
from routes import bp as main_blueprint



# Aplikácia
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = 'tajnykluc123'

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(basedir, 'instance', 'muzikuj.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'profilovky')


# Databáza a migrácia
db.init_app(app)
migrate = Migrate(app, db)

# Login
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return Pouzivatel.query.get(int(user_id))

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


# Spustenie
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)



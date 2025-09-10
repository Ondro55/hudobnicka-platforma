import os
import sys
import logging
from logging.config import fileConfig

from alembic import context

# --- LOGGING / CONFIG ---
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")

# --- APP CONTEXT BOOTSTRAP ---
#
# Cieľ: aby env.py fungoval aj pri spustení cez `flask db ...` (kde je current_app),
# aj pri spustení cez holý `alembic ...` (kde current_app nie je).
#
from flask import current_app

def ensure_app_context():
    """
    Ak nie sme vo Flask app kontexte (spúšťaš holý `alembic`), pokús sa
    vytvoriť aplikáciu a pushnúť app_context, aby current_app existoval.
    Prispôsob cesty/importy podľa projektu, ak máš iný názov modulu.
    """
    try:
        # Ak sme spustení cez `flask db ...`, current_app už existuje.
        _ = current_app.name  # dotyk, aby to padlo, ak current_app nie je
        return
    except Exception:
        pass

    # Koreň projektu (migrations/..)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # 1) Skús app factory: from app import create_app
    flask_app = None
    try:
        from app import create_app  # noqa
        flask_app = create_app()
    except Exception:
        # 2) Skús priamy app object: from app import app
        try:
            from app import app as flask_app  # noqa
        except Exception as e:
            raise RuntimeError(
                "Nepodarilo sa naimportovať Flask aplikáciu. "
                "Skontroluj, že máš buď create_app() v app.py, alebo app = Flask(__name__)."
            ) from e

    # Pushni kontext, nech current_app existuje
    flask_app.app_context().push()

ensure_app_context()

# --- DB / METADATA ---
# Po tomto bode už máme current_app
try:
    # Ak používaš Flask-Migrate (čo vyzerá, že áno)
    target_db = current_app.extensions['migrate'].db
except Exception as e:
    raise RuntimeError(
        "Flask-Migrate nie je inicializovaný (missing Migrate(app, db) v app.py?)"
    ) from e

def get_engine():
    try:
        # Flask-SQLAlchemy < 3 / Alchemical
        return target_db.get_engine()
    except (TypeError, AttributeError):
        # Flask-SQLAlchemy >= 3
        return target_db.engine

def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace('%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')

# Dôležité: nastav Alembicu URL z app configu/engine
config.set_main_option('sqlalchemy.url', get_engine_url())

def get_metadata():
    # Alembic autogenerate potrebuje MetaData všetkých modelov
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas.get(None) or target_db.metadata
    return target_db.metadata

# --- MIGRATION RUNNERS ---

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=get_metadata(),
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode'."""
    def process_revision_directives(context_, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

conf_args = current_app.extensions['migrate'].configure_args

def process_revision_directives(context, revision, directives):
    if getattr(config.cmd_opts, 'autogenerate', False):
        script = directives[0]
        if script.upgrade_ops.is_empty():
            directives[:] = []
            logger.info('No changes in schema detected.')

if conf_args.get("process_revision_directives") is None:
    conf_args["process_revision_directives"] = process_revision_directives

connectable = get_engine()
with connectable.connect() as connection:
    # kópia + vyhodenie duplicitných kľúčov
    cfg = conf_args.copy()
    cfg.pop('compare_type', None)
    cfg.pop('compare_server_default', None)

    context.configure(
        connection=connection,
        target_metadata=get_metadata(),
        **cfg
    )

    with context.begin_transaction():
        context.run_migrations()


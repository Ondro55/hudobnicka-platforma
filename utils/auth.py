from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user

def role_required(check):
    """Základ pre všetky roly: prijme funkciu, ktorá overí current_user."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Musíš byť prihlásený.", "warning")
                return redirect(url_for("login_bp.login"))  # prispôsob ak máš iný endpoint
            if not check(current_user):
                # môžeš namiesto abort(403) dať flash + redirect
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

admin_required = role_required(lambda u: getattr(u, "is_admin", False))
mod_required   = role_required(lambda u: getattr(u, "is_admin", False) or getattr(u, "is_moderator", False))

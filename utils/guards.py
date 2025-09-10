# utils/guards.py
from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user
from features import has_feature

def feature_required(code, upsell_plan='pro'):
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or not has_feature(current_user, code):
                flash(f"Táto funkcia je dostupná v pláne {upsell_plan.upper()}.", "warning")
                return redirect(url_for('bp.index'))  # prispôsob: ak tvoj hlavný blueprint je iný
            return f(*args, **kwargs)
        return wrapper
    return deco

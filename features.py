# features.py
from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

FEATURES = {
    'free': {
        'dopyty:view': False,
        'search:visible': False,
        'calendar': False,
        'bazaar.max_items': 2,
        'gallery.max_photos': 3,
        'messages.max': 50,
        'business.tools': False,
        'invoice.pdf': False,
    },
    'pro': {
        'dopyty:view': True,
        'search:visible': True,
        'calendar': True,
        'bazaar.max_items': 20,
        'gallery.max_photos': 50,
        'messages.max': 1000,
        'business.tools': False,
        'invoice.pdf': True,
    },
    'business': {
        'dopyty:view': True,
        'search:visible': True,
        'calendar': True,
        'bazaar.max_items': 50,
        'gallery.max_photos': 100,
        'messages.max': 10000,
        'business.tools': True,
        'invoice.pdf': True,
    }
}

def user_plan(user):
    if getattr(user, 'is_authenticated', False):
        # 🔓 VIP = sprav sa ako PRO (bez ohľadu na plan v DB)
        if getattr(user, 'is_vip', False):
            return 'pro'
        return getattr(user, 'plan', 'free') or 'free'
    return 'guest'

def has_feature(user, key):
    # 🔓 admin vidí všetko
    if getattr(user, 'is_admin', False):
        return True
    # 🔓 VIP = sprav sa ako PRO
    if getattr(user, 'is_vip', False):
        return FEATURES['pro'].get(key, False)
    plan = user_plan(user)
    return FEATURES.get(plan, {}).get(key, False)

def get_quota(user, key, default=0):
    # 🔓 admin bez limitov
    if getattr(user, 'is_admin', False):
        return 10_000_000
    # 🔓 VIP = PRO limity
    if getattr(user, 'is_vip', False):
        return FEATURES['pro'].get(key, default)
    plan = user_plan(user)
    return FEATURES.get(plan, {}).get(key, default)



def _home_url():
    # skús viaceré názvy domovskej route – uprav, ak máš inú
    for ep in ('bp.index', 'main.index', 'routes.index', 'uzivatel.index', 'index'):
        try:
            return url_for(ep)
        except Exception:
            continue
    return '/'

def feature_required(code, upsell_plan='pro'):
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # 🔓 admin obíde zámok
            if getattr(current_user, 'is_admin', False):
                return f(*args, **kwargs)
            if not current_user.is_authenticated or not has_feature(current_user, code):
                flash(f"Táto funkcia je dostupná v pláne {upsell_plan.upper()}.", "warning")
                return redirect(_home_url())
            return f(*args, **kwargs)
        return wrapper
    return deco


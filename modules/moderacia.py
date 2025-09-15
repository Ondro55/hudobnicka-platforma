# modules/moderacia.py
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import current_user, login_required
from models import db, Report, ModerationLog, Pouzivatel, Dopyt, Sprava, Inzerat, Reklama, ReklamaReport
from datetime import datetime, timedelta
from utils.auth import admin_required, mod_required
from sqlalchemy.orm import joinedload

moder_bp = Blueprint("moderacia", __name__, url_prefix="/admin")

MIN_ACCOUNT_AGE_DAYS = 7
HOLD_UNTRUSTED = True  # podrž na schválenie, ak neoverený/nový a zásah je vážnejší

def staff_required():
    if not (current_user.is_authenticated and (current_user.is_admin or current_user.is_moderator)):
        abort(403)

@moder_bp.before_request
def _guard():
    staff_required()

@moder_bp.get('/queue')
def queue():
    """Základná fronta nahlásení."""
    status = request.args.get('status','open')
    q = Report.query
    if status != 'all':
        q = q.filter(Report.status==status)
    reports = q.order_by(Report.created_at.desc()).limit(200).all()
    return render_template('admin/mod_queue.html', reports=reports)

def _log(action, target_type, target_id, note=''):
    db.session.add(ModerationLog(actor_id=current_user.id, action=action,
                                 target_type=target_type, target_id=target_id, note=note))

@moder_bp.post('/report/<int:rid>/resolve')
@mod_required
def resolve_report(rid):
    r = Report.query.get_or_404(rid)
    r.status = 'resolved'
    r.resolved_at = datetime.utcnow()
    r.resolved_by = current_user
    r.resolution_note = request.form.get('note','')
    _log('resolve', r.entity_type, r.entity_id, r.resolution_note)
    db.session.commit()
    flash('Nahlásenie označené ako vyriešené.', 'success')
    return redirect(url_for('moderacia.queue'))

@moder_bp.post('/report/<int:rid>/ignore')
@mod_required
def ignore_report(rid):
    r = Report.query.get_or_404(rid)
    r.status = 'ignored'
    r.resolved_at = datetime.utcnow()
    r.resolved_by = current_user
    r.resolution_note = request.form.get('note','')
    _log('ignore', r.entity_type, r.entity_id, r.resolution_note)
    db.session.commit()
    flash('Nahlásenie ignorované.', 'info')
    return redirect(url_for('moderacia.queue'))

# ---- Moderátorské akcie nad entitou (príklad pre Dopyt; analogicky pre Inzerat/Sprava) ----
@moder_bp.post('/dopyt/<int:id>/hide')
@mod_required
def hide_dopyt(id):
    d = Dopyt.query.get_or_404(id)
    d.aktivny = False; d.zmazany_at = datetime.utcnow()
    _log('hide', 'dopyt', id, 'Skryté moderátorom')
    db.session.commit()
    flash('Dopyt skrytý.', 'success')
    return redirect(url_for('moderacia.queue'))

@moder_bp.post('/user/<int:uid>/warn')
@mod_required
def warn_user(uid):
    u = Pouzivatel.query.get_or_404(uid)
    u.strikes_count = (u.strikes_count or 0) + 1
    _log('warn', 'user', uid, 'Varovanie')
    db.session.commit()
    flash('Používateľ upozornený (strike +1).', 'success')
    return redirect(url_for('moderacia.queue'))

@moder_bp.post('/user/<int:uid>/tempban')
@mod_required
def tempban_user(uid):
    days = int(request.form.get('days', 7))
    reason = request.form.get('reason','Porušenie pravidiel')
    u = Pouzivatel.query.get_or_404(uid)
    u.banned_until = datetime.utcnow() + timedelta(days=days)
    u.banned_reason = reason
    _log('tempban', 'user', uid, f'{days} dní: {reason}')
    db.session.commit()
    flash(f'Používateľ zabanovaný na {days} dní.', 'success')
    return redirect(url_for('moderacia.queue'))

@moder_bp.post('/user/<int:uid>/permban')
@mod_required
def permban_user(uid):
    reason = request.form.get('reason','Závažné porušenie pravidiel')
    u = Pouzivatel.query.get_or_404(uid)
    u.banned_until = datetime.max
    u.banned_reason = reason
    _log('permban', 'user', uid, reason)
    db.session.commit()
    flash('Používateľ trvalo zabanovaný.', 'success')
    return redirect(url_for('moderacia.queue'))

@moder_bp.get("/")
@admin_required
def dashboard():
    from sqlalchemy import func
    reports_open = Report.query.filter_by(status='open').count()
    reports_all = Report.query.count()
    users_banned = Pouzivatel.query.filter(Pouzivatel.banned_until.isnot(None)).count()
    users_with_strikes = Pouzivatel.query.filter((Pouzivatel.strikes_count > 0)).count()
    dopyty_active = Dopyt.query.filter_by(aktivny=True).count()
    return render_template(
        "admin/dashboard.html",
        reports_open=reports_open,
        reports_all=reports_all,
        users_banned=users_banned,
        users_with_strikes=users_with_strikes,
        dopyty_active=dopyty_active,
    )

@moder_bp.post("/moder/akcia")   # /admin/moder/akcia
@mod_required
def nejaka_mod_akcia():
    # vykonaj akciu, vráť redirect/flash
    return "OK"

def is_trusted(user: Pouzivatel | None) -> bool:
    if not user:
        return False
    if getattr(user, "is_admin", False) or getattr(user, "is_moderator", False):
        return True
    if getattr(user, "strikes_count", 0) > 0:
        return False
    reg = getattr(user, "datum_registracie", None)
    if not reg:
        return False
    return (datetime.utcnow() - reg) >= timedelta(days=MIN_ACCOUNT_AGE_DAYS)

def had_two_way_contact(a_id: int, b_id: int, days: int = 14) -> bool:
    """Bola obojsmerná komunikácia za posledné dni? (DM kontext = menšia šanca na 'nežiaduci návrh')"""
    if not a_id or not b_id:
        return False
    cutoff = datetime.utcnow() - timedelta(days=days)
    # aspoň jedna správa A->B a jedna B->A
    ab = db.session.query(Sprava.id).filter(Sprava.od_id==a_id, Sprava.komu_id==b_id, Sprava.datum>=cutoff).first()
    ba = db.session.query(Sprava.id).filter(Sprava.od_id==b_id, Sprava.komu_id==a_id, Sprava.datum>=cutoff).first()
    return bool(ab and ba)

def enqueue_report(entity_type: str, entity_id: int, reason: str, details: str, reporter_id: int | None = None):
    r = Report(
        reporter_id = reporter_id,
        entity_type = entity_type,
        entity_id   = entity_id,
        reason      = reason,
        details     = details,
        status      = "open"
    )
    db.session.add(r)
    db.session.commit()
    return r

@moder_bp.route('/reklamy/nahlasenia', methods=['GET'])
@login_required
def reklamy_reports():
    if not (current_user.is_admin or current_user.is_moderator):
        abort(403)
    reps = (ReklamaReport.query
            .options(
                joinedload(ReklamaReport.reklama),
                joinedload(ReklamaReport.reporter)
            )
            .filter_by(handled=False)
            .order_by(ReklamaReport.created_at.asc())
            .all())
    return render_template('moder_reklamy_reports.html', reports=reps)


@moder_bp.route('/reklamy/report/<int:rid>/<action>', methods=['POST'])
@login_required
def reklamy_report_action(rid, action):
    if not (current_user.is_admin or current_user.is_moderator):
        abort(403)
    rep = ReklamaReport.query.get_or_404(rid)
    ad = Reklama.query.get(rep.reklama_id)

    if action == 'keep':
        rep.action = 'keep'

    elif action == 'pause' and ad:
        # Minimal pauza: ukonči zobrazovanie hneď teraz
        ad.end_dt = datetime.utcnow()
        rep.action = 'pause'

    elif action == 'remove' and ad:
        # Zmaž súbor aj záznam
        try:
            if ad.foto_nazov:
                p = os.path.join(current_app.root_path, 'static', 'reklamy', ad.foto_nazov)
                if os.path.exists(p):
                    os.remove(p)
            db.session.delete(ad)
        except Exception:
            pass
        rep.action = 'remove'

    else:
        abort(400)

    rep.handled = True
    rep.handled_by = current_user.id
    rep.handled_at = datetime.utcnow()
    db.session.commit()
    flash('Nahlásenie spracované.', 'success')
    return redirect(url_for('moderacia.reklamy_reports'))

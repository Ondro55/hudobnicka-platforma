# modules/reporting.py
from flask import Blueprint, request, redirect, url_for, flash
from flask_login import current_user, login_required
from models import db, Report

report_bp = Blueprint('report', __name__)

@report_bp.post('/report')
@login_required
def create_report():
    entity_type = (request.form.get('entity_type') or '').strip()
    entity_id   = request.form.get('entity_id', type=int)
    reason      = (request.form.get('reason') or 'ine').strip()
    details     = (request.form.get('details') or '').strip()

    if not entity_type or not entity_id:
        flash('Chýbajú údaje nahlásenia.', 'danger')
        return redirect(request.referrer or url_for('main.index'))

    r = Report(
        reporter_id=current_user.id,
        entity_type=entity_type, entity_id=entity_id,
        reason=reason, details=details
    )
    db.session.add(r); db.session.commit()
    flash('Ďakujeme, nahlásenie bolo odoslané moderátorom.', 'success')
    return redirect(request.referrer or url_for('main.index'))

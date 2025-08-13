# modules/dopyty.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from models import db, Dopyt
from datetime import datetime

dopyty = Blueprint('dopyty', __name__)

@dopyty.route('/dopyty')
@login_required  # ✅ IBA prihláseným
def zobraz_dopyty():
    vsetky = Dopyt.query.order_by(Dopyt.datum.asc()).all()
    return render_template('dopyty.html', dopyty=vsetky)

@dopyty.route('/pridaj_dopyt', methods=['POST'])
def pridaj_dopyt():
    # honeypot proti spamu
    if (request.form.get('website') or '').strip():
        flash('Formulár bol zablokovaný (spam).', 'warning')
        return redirect(url_for('dopyty.zobraz_dopyty'))

    typ_akcie = request.form.get('typ_akcie')
    datum = request.form.get('datum')
    cas_od = request.form.get('cas_od')
    cas_do = request.form.get('cas_do')

    # miesto skladáme z kraj/okres/obec (v HTML nie je jedno pole "miesto")
    kraj  = request.form.get('kraj')
    okres = request.form.get('okres')
    obec  = request.form.get('obec')
    miesto = ", ".join([x for x in [obec, okres, kraj] if x])

    rozpocet = request.form.get('rozpocet')
    popis    = request.form.get('popis')
    meno     = request.form.get('meno')
    email    = request.form.get('email')

    # konverzie
    from datetime import datetime
    datum  = datetime.strptime(datum,  '%Y-%m-%d').date() if datum else None
    cas_od = datetime.strptime(cas_od, '%H:%M').time()    if cas_od else None
    cas_do = datetime.strptime(cas_do, '%H:%M').time()    if cas_do else None
    rozpocet = float(rozpocet) if (rozpocet or '').strip() else None

    novy = Dopyt(
        typ_akcie=typ_akcie,
        datum=datum,
        cas_od=cas_od,
        cas_do=cas_do,
        miesto=miesto,
        rozpocet=rozpocet,
        popis=popis,
        meno=meno,
        email=email,
        pouzivatel_id=(current_user.id if current_user.is_authenticated else None)
    )
    db.session.add(novy)
    db.session.commit()
    flash('Dopyt bol pridaný!', "success")
    return redirect(url_for('dopyty.zobraz_dopyty'))

@dopyty.route('/dopyty/pridat', methods=['GET'])
def formular_dopyt():
    return render_template('dopyt.html')


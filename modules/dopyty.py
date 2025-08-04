# modules/dopyty.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Dopyt
from datetime import datetime

dopyty = Blueprint('dopyty', __name__)

@dopyty.route('/dopyty')
def zobraz_dopyty():
    vsetky = Dopyt.query.order_by(Dopyt.datum.asc()).all()
    return render_template('dopyty.html', dopyty=vsetky)

@dopyty.route('/pridaj_dopyt', methods=['POST'])
def pridaj_dopyt():
    typ_akcie = request.form['typ_akcie']
    datum = request.form.get('datum')
    cas_od = request.form.get('cas_od')
    cas_do = request.form.get('cas_do')
    miesto = request.form.get('miesto')
    rozpocet = request.form.get('rozpocet')
    popis = request.form.get('popis')

    # Konverzia dátumov a časov na správne formáty
    datum = datetime.strptime(datum, '%Y-%m-%d').date() if datum else None
    cas_od = datetime.strptime(cas_od, '%H:%M').time() if cas_od else None
    cas_do = datetime.strptime(cas_do, '%H:%M').time() if cas_do else None

    novy = Dopyt(
        typ_akcie=typ_akcie,
        datum=datum,
        cas_od=cas_od,
        cas_do=cas_do,
        miesto=miesto,
        rozpocet=int(rozpocet) if rozpocet else None,
        popis=popis
    )
    db.session.add(novy)
    db.session.commit()
    flash('Dopyt bol pridaný!', "info")
    return redirect(url_for('dopyty.zobraz_dopyty'))

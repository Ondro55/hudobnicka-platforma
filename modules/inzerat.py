# modules/inzerat.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Inzerat
from flask_login import current_user, login_required

inzerat = Blueprint('inzerat', __name__)

@inzerat.route('/pridaj-inzerat', methods=['GET', 'POST'])
@login_required
def pridaj_inzerat():
    if request.method == 'POST':
        novy_inzerat = Inzerat(
            typ=request.form.get('typ'),
            kategoria=request.form.get('kategoria'),
            mesto=request.form.get('mesto'),
            doprava=request.form.get('doprava'),
            cena=float(request.form.get('cena', 0)),
            popis=request.form.get('popis'),
            pouzivatel_id=current_user.id
        )
        db.session.add(novy_inzerat)
        db.session.commit()
        flash("Inzerát bol úspešne pridaný!", "success")
        return redirect(url_for('inzerat.moj_bazar'))

    return render_template('pridaj_inzerat.html')


@inzerat.route('/moj-bazar')
@login_required
def moj_bazar():
    moje_inzeraty = Inzerat.query.filter_by(pouzivatel_id=current_user.id).order_by(Inzerat.datum.desc()).all()
    return render_template('moj_bazar.html', inzeraty=moje_inzeraty)


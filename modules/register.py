# modules/register.py
from flask import Blueprint, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
from flask_login import login_user
from models import db, Pouzivatel
from flask import flash


register_bp = Blueprint('register', __name__)

@register_bp.route('/register', methods=['POST'])
def registracia():
    prezyvka = request.form['prezyvka']
    meno = request.form.get('meno')
    priezvisko = request.form.get('priezvisko')
    email = request.form['email']
    heslo = request.form['heslo']
    heslo2 = request.form['heslo2']
    instrument = request.form.get('instrument')
    doplnkovy_nastroj = request.form.get('doplnkovy_nastroj')
    obec = request.form.get('obec')

    if heslo != heslo2:
        flash("Heslá sa nezhodujú ❌", "danger")
        return redirect(url_for('main.index', zobraz_formular='uzivatel'))

    if Pouzivatel.query.filter_by(email=email).first():
        flash("Tento email už je zaregistrovaný ❌", "danger")
        return redirect(url_for('main.index', zobraz_formular='uzivatel'))

    nove_heslo = generate_password_hash(heslo)
    novy = Pouzivatel(
        prezyvka=prezyvka,
        meno=meno,
        priezvisko=priezvisko,
        email=email,
        heslo=nove_heslo,
        instrument=instrument,
        doplnkovy_nastroj=doplnkovy_nastroj,
        obec=obec
    )

    db.session.add(novy)
    db.session.commit()

    login_user(novy)
    session['user_id'] = novy.id
    session['prezyvka'] = novy.prezyvka

    flash(f"Vitaj, {prezyvka} 👋", "success")
    return redirect(url_for('uzivatel.profil'))


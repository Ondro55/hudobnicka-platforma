from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user
from models import Pouzivatel
from flask import flash

login_bp = Blueprint("login_bp", __name__)

@login_bp.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    heslo = request.form.get('heslo')

    pouzivatel = Pouzivatel.query.filter_by(email=email).first()

    if pouzivatel and pouzivatel.over_heslo(heslo):
        if getattr(pouzivatel, 'erase_pending', False):
            flash('Účet má aktívnu žiadosť o vymazanie. Skontrolujte e-mail a potvrďte alebo zrušte žiadosť (platí 24 h).', 'warning')
            return redirect(url_for('index', zobraz_formular='prihlasenie'))
        login_user(pouzivatel)
        return redirect(url_for('uzivatel.profil'))


@login_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index', zobraz_formular='prihlasenie'))


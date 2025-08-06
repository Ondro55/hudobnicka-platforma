from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask import url_for
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Pouzivatel(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    prezyvka = db.Column(db.String(50), unique=True, nullable=False)
    meno = db.Column(db.String(100))
    priezvisko = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    heslo = db.Column(db.String(200), nullable=False)
    instrument = db.Column(db.String(100))
    doplnkovy_nastroj = db.Column(db.String(100))
    bio = db.Column(db.Text)
    obec = db.Column(db.String(100)) 
    datum_registracie = db.Column(db.DateTime, default=datetime.utcnow)
    aktivny = db.Column(db.Boolean, default=True)
    profil_fotka = db.Column(db.String(200))

    galeria = db.relationship('GaleriaPouzivatel', back_populates='pouzivatel', lazy=True, cascade='all, delete-orphan')
    videa = db.relationship('VideoPouzivatel', back_populates='pouzivatel', lazy=True, cascade='all, delete-orphan')

    def over_heslo(self, zadane_heslo):
        return check_password_hash(self.heslo, zadane_heslo)

    def nastav_heslo(self, heslo):
        self.heslo = generate_password_hash(heslo)

    @property
    def profil_fotka_url(self):
        if self.profil_fotka:
            return url_for('static', filename=f'profil_fotky/{self.profil_fotka}')
        else:
            return url_for('static', filename='img/default-profil.jpg')


class Inzerat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    typ = db.Column(db.String(50))
    kategoria = db.Column(db.String(50))
    mesto = db.Column(db.String(100))
    doprava = db.Column(db.String(50))
    cena = db.Column(db.Float)
    popis = db.Column(db.Text)
    datum = db.Column(db.DateTime, default=datetime.utcnow)

    mesto_id = db.Column(db.Integer, db.ForeignKey('mesto.id', name='fk_inzerat_mesto'), nullable=True)
    mesto_objekt = db.relationship('Mesto', backref='inzeraty')

    pouzivatel_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False)
    pouzivatel = db.relationship('Pouzivatel', backref='inzeraty')

    fotky = db.relationship('FotoInzerat', backref='inzerat', cascade='all, delete-orphan')


class FotoInzerat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nazov_suboru = db.Column(db.String(200), nullable=False)
    inzerat_id = db.Column(db.Integer, db.ForeignKey('inzerat.id'), nullable=False)


# 🧩 Pomocná tabuľka pre Many-to-Many medzi skupina a Pouzivatel
skupina_clenovia = db.Table('skupina_clenovia',
    db.Column('skupina_id', db.Integer, db.ForeignKey('skupina.id')),
    db.Column('pouzivatel_id', db.Integer, db.ForeignKey('pouzivatel.id'))
)


class Dopyt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meno = db.Column(db.String(100))
    email = db.Column(db.String(120))
    typ_akcie = db.Column(db.String(100))
    miesto = db.Column(db.String(100))
    datum = db.Column(db.Date)
    cas_od = db.Column(db.Time)
    cas_do = db.Column(db.Time)
    popis = db.Column(db.Text)
    rozpocet = db.Column(db.Float)

    pouzivatel_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False)
    pouzivatel = db.relationship('Pouzivatel', backref='dopyty')


class Skupina(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nazov = db.Column(db.String(100), nullable=False)
    zaner = db.Column(db.String(100))
    mesto = db.Column(db.String(100))
    email = db.Column(db.String(120))
    web = db.Column(db.String(255))
    popis = db.Column(db.Text)
    profil_fotka_skupina = db.Column(db.String(120), nullable=True)
    datum_vytvorenia = db.Column(db.DateTime, default=datetime.utcnow)

    zakladatel_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False)
    zakladatel = db.relationship('Pouzivatel', backref='kapely_zalozene')

    clenovia = db.relationship('Pouzivatel', secondary=skupina_clenovia, backref='skupina_clen')

    galeria = db.relationship('GaleriaSkupina', back_populates='skupina', cascade='all, delete-orphan')
    videa = db.relationship('VideoSkupina', back_populates='skupina', cascade='all, delete-orphan')


class GaleriaPouzivatel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nazov_suboru = db.Column(db.String(200), nullable=False)
    pouzivatel_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False)

    pouzivatel = db.relationship('Pouzivatel', back_populates='galeria')


class VideoPouzivatel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    youtube_url = db.Column(db.String(255), nullable=False)
    popis = db.Column(db.String(255))
    pouzivatel_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False)

    pouzivatel = db.relationship('Pouzivatel', back_populates='videa')


class GaleriaSkupina(db.Model):
    __tablename__ = 'galeria_skupina'

    id = db.Column(db.Integer, primary_key=True)
    nazov_suboru = db.Column(db.String(200), nullable=False)
    skupina_id = db.Column(db.Integer, db.ForeignKey('skupina.id'), nullable=False)

    skupina = db.relationship('Skupina', back_populates='galeria')


class VideoSkupina(db.Model):
    __tablename__ = 'video_skupina'

    id = db.Column(db.Integer, primary_key=True)
    youtube_url = db.Column(db.String(300), nullable=False)
    popis = db.Column(db.String(200))
    skupina_id = db.Column(db.Integer, db.ForeignKey('skupina.id'), nullable=False)

    skupina = db.relationship('Skupina', back_populates='videa')

# Kalendar#
class Udalost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nazov = db.Column(db.String(100), nullable=False)
    popis = db.Column(db.Text)
    datum = db.Column(db.Date, nullable=False)
    cas_od = db.Column(db.Time, nullable=True)
    cas_do = db.Column(db.Time, nullable=True)
    miesto = db.Column(db.String(150), nullable=True)
    poznamka = db.Column(db.Text, nullable=True)
    celodenne = db.Column(db.Boolean, default=False)

    pouzivatel_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=True)
    pouzivatel = db.relationship('Pouzivatel', backref='udalosti')

    skupina_id = db.Column(db.Integer, db.ForeignKey('skupina.id'), nullable=True)
    skupina = db.relationship('Skupina', backref='udalosti')

class Mesto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nazov = db.Column(db.String(100), nullable=False)
    okres = db.Column(db.String(100), nullable=True)
    kraj = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f"{self.nazov} ({self.okres}, {self.kraj})"

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask import url_for
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

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

    is_admin = db.Column(db.Boolean, default=False)
    is_moderator = db.Column(db.Boolean, default=False)

    strikes_count = db.Column(db.Integer, default=0, nullable=False)
    banned_until = db.Column(db.DateTime, nullable=True)
    banned_reason = db.Column(db.String(255), nullable=True)

    typ_subjektu = db.Column(db.String(10), default='fyzicka')  # 'fyzicka' | 'ico'
    ico = db.Column(db.String(20), nullable=True)
    organizacia_nazov = db.Column(db.String(150), nullable=True)

    def over_heslo(self, zadane_heslo):
        return check_password_hash(self.heslo, zadane_heslo)

    def nastav_heslo(self, heslo):
        self.heslo = generate_password_hash(heslo)

    @property
    def profil_fotka_url(self):
        if self.profil_fotka:
            return url_for('static', filename=f'profilovky/{self.profil_fotka}')
        return url_for('static', filename='profilovky/default.png')
    @property
    def profil_url(self):
        """Bezpečne vygeneruje link na verejný profil používateľa (podľa toho, čo máš v appke)."""
        candidates = [
            ('profil.detail',       {'user_id': self.id}),
            ('profil.view',         {'user_id': self.id}),
            ('uzivatel.profil_detail', {'id': self.id}),
            ('uzivatel.profil_public', {'id': self.id}),
        ]
        for endpoint, params in candidates:
            try:
                return url_for(endpoint, **params)
            except Exception:
                continue
        # fallback – aspoň na vlastný profil alebo nič
        try:
            return url_for('uzivatel.profil')
        except Exception:
            return '#'
    @property
    def is_banned(self) -> bool:
        return self.banned_until is not None and datetime.utcnow() < self.banned_until

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
    miesto = db.Column(db.String(100))  # voľný text
    datum = db.Column(db.Date)
    cas_od = db.Column(db.Time)
    cas_do = db.Column(db.Time)
    popis = db.Column(db.Text)
    rozpocet = db.Column(db.Float)

    # FK na tabuľku miest
    mesto_id = db.Column(db.Integer, db.ForeignKey('mesto.id'), nullable=True)
    mesto_ref = db.relationship('Mesto')  # PREMENOVANÉ z `mesto` -> `mesto_ref`

    aktivny = db.Column(db.Boolean, default=True)
    zmazany_at = db.Column(db.DateTime, nullable=True)

    pouzivatel_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=True)
    pouzivatel = db.relationship('Pouzivatel', backref='dopyty')

    # nové časové stopy
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


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

class Sprava(db.Model):
    __tablename__ = "spravy"
    id = db.Column(db.Integer, primary_key=True)
    obsah = db.Column(db.Text, nullable=False)
    datum = db.Column(db.DateTime, default=datetime.utcnow)

    od_id   = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False)
    komu_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=True)  # <- zmenené na True
    komu_email = db.Column(db.String(255), nullable=True)  # <- NOVÉ

    deleted_by_sender    = db.Column(db.Boolean, default=False)
    deleted_by_recipient = db.Column(db.Boolean, default=False)

    inzerat_id = db.Column(db.Integer, db.ForeignKey('inzerat.id'), nullable=True)
    dopyt_id   = db.Column(db.Integer, db.ForeignKey('dopyt.id'),   nullable=True)

    precitane = db.Column(db.Boolean, default=False)
    
    od   = db.relationship('Pouzivatel', foreign_keys=[od_id])
    komu = db.relationship('Pouzivatel', foreign_keys=[komu_id])
    inzerat = db.relationship('Inzerat', backref='spravy')

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=True)
    reporter = db.relationship('Pouzivatel', foreign_keys=[reporter_id])

    entity_type = db.Column(db.String(30), nullable=False)  # 'sprava' | 'inzerat' | 'dopyt' | 'profil'
    entity_id   = db.Column(db.Integer, nullable=False)

    reason = db.Column(db.String(50), nullable=False)  # 'obtažovanie','spam','nevhodny_obsah','fake','ine'
    details = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(20), default='open', nullable=False)  # 'open' | 'resolved' | 'ignored'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'))
    resolved_by = db.relationship('Pouzivatel', foreign_keys=[resolved_by_id])
    resolution_note = db.Column(db.Text, nullable=True)

class ModerationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False)
    actor = db.relationship('Pouzivatel')
    action = db.Column(db.String(50), nullable=False)   # 'hide','warn','tempban','permban','delete','restore'
    target_type = db.Column(db.String(30), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class SkupinaPozvanka(db.Model):
    __tablename__ = 'skupina_pozvanka'

    id          = db.Column(db.Integer, primary_key=True)
    token       = db.Column(db.String(64), unique=True, nullable=False)
    stav        = db.Column(db.String(12), default='pending', nullable=False)  # pending/accepted/revoked/expired
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at  = db.Column(db.DateTime)

    skupina_id  = db.Column(db.Integer, db.ForeignKey('skupina.id'), nullable=False)
    pozvany_id  = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False)
    pozval_id   = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False)

    skupina     = db.relationship('Skupina', backref='pozvanky')
    pozvany     = db.relationship('Pouzivatel', foreign_keys=[pozvany_id])
    pozval      = db.relationship('Pouzivatel', foreign_keys=[pozval_id])

    def is_valid(self) -> bool:
        if self.stav != 'pending':
            return False
        if self.expires_at and datetime.utcnow() >= self.expires_at:
            return False
        return True

# --- MODELY FÓRA ---

# Ak máš inde definované:
# from yourapp.models import Pouzivatel   # <- uprav podľa tvojej appky

class ForumCategory(db.Model):
    __tablename__ = "forum_category"
    id = db.Column(db.Integer, primary_key=True)
    nazov = db.Column(db.String(80), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=True, unique=True)

    topics = db.relationship("ForumTopic", back_populates="kategoria", cascade="all, delete")

class ForumTopic(db.Model):
    __tablename__ = "forum_topic"
    id = db.Column(db.Integer, primary_key=True)
    nazov = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    vytvorene_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    aktivita_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # vzťahy
    autor_id = db.Column(db.Integer, db.ForeignKey("pouzivatel.id"), nullable=True)  # premenuj FK ak treba
    kategoria_id = db.Column(db.Integer, db.ForeignKey("forum_category.id"), nullable=True)

    autor = db.relationship("Pouzivatel")  # premenuj podľa seba
    kategoria = db.relationship("ForumCategory", back_populates="topics")
    posts = db.relationship("ForumPost", back_populates="topic", cascade="all, delete-orphan")

    @property
    def pocet_odpovedi(self) -> int:
        # jednoduché – na štart stačí; neskôr vieme nahradiť agregáciou
        return len(self.posts) if self.posts is not None else 0

class ForumPost(db.Model):
    __tablename__ = "forum_post"
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    vytvorene_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_answer = db.Column(db.Boolean, default=False, nullable=False)

    autor_id = db.Column(db.Integer, db.ForeignKey("pouzivatel.id"), nullable=True)  # premenuj FK ak treba
    topic_id = db.Column(db.Integer, db.ForeignKey("forum_topic.id"), nullable=False, index=True)

    autor = db.relationship("Pouzivatel")  # premenuj podľa seba
    topic = db.relationship("ForumTopic", back_populates="posts")

class TopicWatch(db.Model):
    __tablename__ = "forum_topic_watch"
    # kto sleduje akú tému
    user_id = db.Column(db.Integer, db.ForeignKey("pouzivatel.id"), primary_key=True)   # premenuj podľa seba
    topic_id = db.Column(db.Integer, db.ForeignKey("forum_topic.id"), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class RychlyDopyt(db.Model):
    __tablename__ = "rychly_dopyt"

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    mesto_id = db.Column(db.Integer, db.ForeignKey("mesto.id"), nullable=True, index=True)
    mesto_ref = db.relationship("Mesto")

    autor_id = db.Column(db.Integer, db.ForeignKey("pouzivatel.id"), nullable=True, index=True)
    autor = db.relationship("Pouzivatel")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    plati_do = db.Column(db.DateTime, nullable=False, index=True)

    aktivny = db.Column(db.Boolean, default=True, nullable=False, index=True)
    archived_at = db.Column(db.DateTime, nullable=True)

    def is_active(self) -> bool:
        return self.aktivny and (self.plati_do is None or datetime.utcnow() < self.plati_do)
    

class ForumNotification(db.Model):
    __tablename__ = 'forum_notification'
    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), index=True, nullable=False)
    topic_id  = db.Column(db.Integer, index=True, nullable=False)
    post_id   = db.Column(db.Integer, index=True, nullable=False)
    reason    = db.Column(db.String(32))         # 'reply', 'watch', 'mention'
    created_at= db.Column(db.DateTime, default=datetime.utcnow)
    read_at   = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'post_id', name='uq_forumnotif_user_post'),  # žiadne duplikáty
    )

    def __repr__(self):
            return f"<ForumNotification user={self.user_id} post={self.post_id} reason={self.reason}>"
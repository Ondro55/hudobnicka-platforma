# modules/komunita.py
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user, login_required
from sqlalchemy import or_, func  # + func
from models import db, Pouzivatel, ForumCategory, ForumTopic, TopicWatch, RychlyDopyt, Mesto
from models import ForumPost

komunita_bp = Blueprint("komunita", __name__, template_folder="../templates")

@komunita_bp.route("/komunita")
def hub():
    tab = request.args.get("tab", "ludia")
    ctx = dict(active_tab=tab)

    if tab == "ludia":
        users = Pouzivatel.query.order_by(Pouzivatel.prezyvka.asc()).all()
        ctx["users"] = users

    elif tab == "rychly-dopyt":
        q_text = (request.args.get("q") or "").strip()
        mesto_id = request.args.get("mesto", type=int)
        view = request.args.get("view")

        q = RychlyDopyt.query.filter(
            RychlyDopyt.aktivny.is_(True),
            RychlyDopyt.plati_do > datetime.utcnow()
        )
        if q_text:
            like = f"%{q_text}%"
            q = q.filter(RychlyDopyt.text.ilike(like))
        if mesto_id:
            q = q.filter(RychlyDopyt.mesto_id == mesto_id)
        if view == "mine" and getattr(current_user, "is_authenticated", False):
            q = q.filter(RychlyDopyt.autor_id == current_user.id)

        rychle = q.order_by(RychlyDopyt.created_at.desc()).limit(100).all()
        ctx["rychle_dopyty"] = rychle

    elif tab == "forum":
        kategoria_id = request.args.get("kategoria", type=int)
        sort = request.args.get("sort", "activity")
        view = request.args.get("view")

        q = ForumTopic.query
        if kategoria_id:
            q = q.filter(ForumTopic.kategoria_id == kategoria_id)

        # „Moje“ pohľady
        if view and getattr(current_user, "is_authenticated", False):
            if view == "mine":
                q = q.filter(ForumTopic.autor_id == current_user.id)
            elif view == "replied":
                q = q.join(ForumPost, ForumPost.topic_id == ForumTopic.id) \
                     .filter(ForumPost.autor_id == current_user.id) \
                     .distinct(ForumTopic.id)
            elif view == "watching":
                q = q.join(TopicWatch, TopicWatch.topic_id == ForumTopic.id) \
                     .filter(TopicWatch.user_id == current_user.id)

        # Zoradenie
        if sort == "newest":
            q = q.order_by(ForumTopic.vytvorene_at.desc())
        elif sort == "answers":
            # subquery s počtom odpovedí na tému
            answers_sq = db.session.query(
                ForumPost.topic_id.label("tid"),
                func.count(ForumPost.id).label("answers_count")
            ).group_by(ForumPost.topic_id).subquery()

            q = q.outerjoin(answers_sq, answers_sq.c.tid == ForumTopic.id) \
                 .order_by(func.coalesce(answers_sq.c.answers_count, 0).desc(),
                           ForumTopic.aktivita_at.desc())
        else:
            # default: podľa poslednej aktivity
            q = q.order_by(ForumTopic.aktivita_at.desc())

        topics = q.limit(50).all()
        categories = ForumCategory.query.order_by(ForumCategory.nazov.asc()).all()

        selected_id = request.args.get("t", type=int)
        selected_topic = ForumTopic.query.get(selected_id) if selected_id else None

        watched_ids = set()
        if getattr(current_user, "is_authenticated", False):
            watched_ids = {
                r.topic_id for r in TopicWatch.query.filter_by(user_id=current_user.id).all()
            }

        ctx.update(categories=categories,
                   topics=topics,
                   selected_topic=selected_topic,
                   watched_ids=watched_ids)

    return render_template("komunita.html", **ctx)

# --- Rýchly dopyt: vytvorenie ---
@komunita_bp.route("/komunita/rychly-dopyt/nova", methods=["POST"])
@login_required
def qd_create():
    text = (request.form.get("text") or "").strip()
    if not text:
        flash("Napíš krátku správu.", "warning")
        return redirect(url_for("komunita.hub", tab="rychly-dopyt"))

    # rate-limit: 1 rýchly dopyt / 5 minút
    recent_cnt = RychlyDopyt.query \
        .filter(RychlyDopyt.autor_id == current_user.id,
                RychlyDopyt.created_at >= datetime.utcnow() - timedelta(minutes=5)) \
        .count()
    if recent_cnt:
        flash("Skús to prosím o pár minút – aby sme predišli spamu.", "warning")
        return redirect(url_for("komunita.hub", tab="rychly-dopyt"))

    # limit dĺžky (ochrana UX + spam)
    if len(text) > 500:
        text = text[:500]

    mesto_id = request.form.get("mesto_id", type=int)
    ttl_days = request.form.get("ttl_days", type=int) or 30
    if ttl_days not in (7, 14, 30):
        ttl_days = 30

    now = datetime.utcnow()
    qd = RychlyDopyt(
        text=text,
        mesto_id=mesto_id,
        autor_id=current_user.id,
        created_at=now,
        plati_do=now + timedelta(days=ttl_days),
        aktivny=True,
    )
    db.session.add(qd)
    db.session.commit()

    flash("Rýchly dopyt bol pridaný.", "success")
    return redirect(url_for("komunita.hub", tab="rychly-dopyt"))

# --- Rýchly dopyt: zmazanie (len autor alebo admin/mod) ---
@komunita_bp.route("/komunita/rychly-dopyt/<int:qd_id>/delete", methods=["POST"])
@login_required
def qd_delete(qd_id: int):
    qd = RychlyDopyt.query.get_or_404(qd_id)

    if qd.autor_id != current_user.id and not getattr(current_user, "is_moderator", False) and not getattr(current_user, "is_admin", False):
        abort(403)

    # soft delete (archivácia)
    qd.aktivny = False
    qd.archived_at = datetime.utcnow()
    db.session.commit()

    flash("Rýchly dopyt bol odstránený.", "info")
    return redirect(url_for("komunita.hub", tab="rychly-dopyt"))

# --- Housekeeping: automatická archivácia expirovaných ---
def _housekeep_rychle_dopyty():
    now = datetime.utcnow()
    expired = RychlyDopyt.query.filter(
        RychlyDopyt.aktivny.is_(True),
        RychlyDopyt.plati_do <= now
    ).all()
    if not expired:
        return
    for r in expired:
        r.aktivny = False
        r.archived_at = now
    db.session.commit()

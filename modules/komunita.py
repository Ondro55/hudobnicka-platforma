# modules/komunita.py
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user, login_required
from sqlalchemy import or_, func
from models import db, Pouzivatel, ForumTopic, TopicWatch, RychlyDopyt
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

        ctx["rychle_dopyty"] = q.order_by(RychlyDopyt.created_at.desc()).limit(100).all()

    elif tab == "forum":
        q_text = (request.args.get("q") or "").strip()
        sort = request.args.get("sort", "activity")
        view = request.args.get("view")

        q = ForumTopic.query

        # fulltext-lite: názov + telo
        if q_text:
            like = f"%{q_text}%"
            q = q.filter(or_(ForumTopic.nazov.ilike(like),
                             ForumTopic.body.ilike(like)))

        # moje pohľady
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

        # zoradenie
        if sort == "newest":
            q = q.order_by(ForumTopic.vytvorene_at.desc())
        elif sort == "answers":
            answers_sq = db.session.query(
                ForumPost.topic_id.label("tid"),
                func.count(ForumPost.id).label("answers_count")
            ).group_by(ForumPost.topic_id).subquery()

            q = q.outerjoin(answers_sq, answers_sq.c.tid == ForumTopic.id) \
                 .order_by(func.coalesce(answers_sq.c.answers_count, 0).desc(),
                           ForumTopic.aktivita_at.desc())
        else:
            q = q.order_by(ForumTopic.aktivita_at.desc())

        topics = q.limit(50).all()
        selected_id = request.args.get("t", type=int)
        selected_topic = ForumTopic.query.get(selected_id) if selected_id else None

        # ⭐️ BOD 6: automaticky označ notifikácie k vybranej téme ako prečítané
        if selected_topic and getattr(current_user, "is_authenticated", False):
            try:
                from models import ForumNotification
                (ForumNotification.query
                    .filter_by(user_id=current_user.id,
                            topic_id=selected_topic.id,
                            read_at=None)
                    .update({"read_at": datetime.utcnow()}, synchronize_session=False))
                db.session.commit()
            except Exception:
                pass

        watched_ids = set()
        if getattr(current_user, "is_authenticated", False):
            watched_ids = {
                r.topic_id for r in TopicWatch.query.filter_by(user_id=current_user.id).all()
            }

        ctx.update(topics=topics, selected_topic=selected_topic, watched_ids=watched_ids)

    # ✅ jediné spoločné return pre všetky taby
    return render_template("komunita.html", **ctx)

# --- RÝCHLY DOPYT: vytvorenie + zavretie ------------------------------------
@komunita_bp.post("/komunita/rychly-dopyt/create")
@login_required
def rychly_dopyt_create():
    from models import RychlyDopyt
    text = (request.form.get("text") or "").strip()
    mesto_id = request.form.get("mesto_id", type=int)
    platnost_dni = request.form.get("platnost_dni", type=int) or 14

    if not text:
        flash("Zadaj text dopytu.", "warning")
        return redirect(url_for("komunita.hub", tab="rychly-dopyt"))

    # anti-spam: max 1 dopyt / 2 min
    two_min_ago = datetime.utcnow() - timedelta(minutes=2)
    recent = (RychlyDopyt.query
              .filter(RychlyDopyt.autor_id == current_user.id,
                      RychlyDopyt.created_at >= two_min_ago)
              .count())
    if recent:
        flash("Skús to prosím o chvíľu (antispam).", "warning")
        return redirect(url_for("komunita.hub", tab="rychly-dopyt"))

    rd = RychlyDopyt(
        text=text,
        autor_id=current_user.id,
        mesto_id=mesto_id if mesto_id else None,
        created_at=datetime.utcnow(),
        plati_do=(datetime.utcnow() + timedelta(days=max(1, min(60, platnost_dni)))),
        aktivny=True
    )
    db.session.add(rd)
    db.session.commit()
    flash("Dopyt bol pridaný.", "success")
    return redirect(url_for("komunita.hub", tab="rychly-dopyt"))

@komunita_bp.post("/komunita/rychly-dopyt/<int:rd_id>/close")
@login_required
def rychly_dopyt_close(rd_id):
    from models import RychlyDopyt
    rd = RychlyDopyt.query.get_or_404(rd_id)
    if rd.autor_id != current_user.id and not (getattr(current_user, "is_admin", False) or getattr(current_user, "is_moderator", False)):
        abort(403)
    rd.aktivny = False
    db.session.commit()
    flash("Dopyt bol označený ako vybavený.", "success")
    return redirect(url_for("komunita.hub", tab="rychly-dopyt"))

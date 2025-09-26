# modules/ratings.py
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import func, and_
from models import db, Pouzivatel, UserRating

ratings_bp = Blueprint("ratings", __name__, url_prefix="/api/ratings")

# Konštanty pre bayes priemer (m – prior mean, C – váha prioru)
BAYES_M = 4.0   # „očakávaný“ priemer bez dát
BAYES_C = 5.0   # sila prioru (koľko „virtuálnych“ hlasov)

# throttle: jeden update na ten istý pár za X sekúnd
MIN_UPDATE_INTERVAL = 60  # sekúnd


def _recompute_user_aggregates(user_id: int) -> dict:
    """Prepočíta sumár pre ratee_id a zapíše do Pouzivatel.*. Vráti dict so sumárom."""
    q = (db.session.query(
            func.count(UserRating.id),
            func.coalesce(func.sum(UserRating.stars), 0)
        )
        .filter(
            UserRating.ratee_id == user_id,
            UserRating.status == "active",
            UserRating.stars.isnot(None)
        ))

    count, stars_sum = q.first() or (0, 0)
    count = int(count or 0)
    stars_sum = float(stars_sum or 0)

    avg = (stars_sum / count) if count > 0 else 0.0
    bayes = ((BAYES_C * BAYES_M) + stars_sum) / ((BAYES_C + count) if (BAYES_C + count) > 0 else 1.0)

    # histogram (1..5)
    hist_rows = (db.session.query(UserRating.stars, func.count(UserRating.id))
                 .filter(
                     UserRating.ratee_id == user_id,
                     UserRating.status == "active",
                     UserRating.stars.isnot(None)
                 )
                 .group_by(UserRating.stars)
                 .all())
    histogram = {i: 0 for i in range(1, 6)}
    for s, c in hist_rows:
        if s in histogram:
            histogram[int(s)] = int(c)

    # zapíš do Pouzivatel
    u = Pouzivatel.query.get(user_id)
    if u:
        u.rating_count = count
        u.rating_sum = int(stars_sum)
        u.rating_avg = float(avg)
        u.rating_bayes = float(bayes)
        db.session.commit()

    return {
        "count": count, "sum": stars_sum, "avg": avg, "bayes": bayes,
        "histogram": [histogram[i] for i in range(1, 6)]
    }


def _can_rate_user(ratee: Pouzivatel) -> tuple[bool, str]:
    if not current_user.is_authenticated:
        return False, "Musíš byť prihlásený."
    if ratee is None or not ratee.is_active:
        return False, "Používateľ neexistuje alebo je neaktívny."
    if current_user.id == ratee.id:
        return False, "Nemôžeš hodnotiť sám seba."
    if not ratee.povolit_hodnotenie:
        return False, "Tento profil hodnotenie neumožňuje."
    return True, ""


@ratings_bp.get("/summary")
def summary():
    """Sumár pre profil (AJ pre neprihlásených). Vracia aj tvoje vlastné hodnotenie, ak si prihlásený."""
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "missing user_id"}), 400

    u = Pouzivatel.query.get(user_id)
    if not u:
        return jsonify({"error": "not_found"}), 404

    # aggregate – ber zo stĺpcov (sú aktuálne), prípadne fallback pre výpočet
    if u.rating_count is None:
        agg = _recompute_user_aggregates(user_id)
        count, avg, bayes, histogram = agg["count"], agg["avg"], agg["bayes"], agg["histogram"]
    else:
        count = int(u.rating_count or 0)
        avg = float(u.rating_avg or 0.0)
        bayes = float(u.rating_bayes or 0.0)
        # ak chceš histogram, dopočítaj:
        hist_rows = (db.session.query(UserRating.stars, func.count(UserRating.id))
                     .filter(UserRating.ratee_id == user_id,
                             UserRating.status == "active",
                             UserRating.stars.isnot(None))
                     .group_by(UserRating.stars).all())
        hist = {i: 0 for i in range(1, 6)}
        for s, c in hist_rows:
            if s in hist: hist[int(s)] = int(c)
        histogram = [hist[i] for i in range(1, 6)]

    your = None
    if current_user.is_authenticated:
        r = (UserRating.query
             .filter_by(rater_id=current_user.id, ratee_id=user_id)
             .first())
        if r and r.status == "active":
            your = {"stars": r.stars, "recommend": bool(r.recommend)}

    can, reason = _can_rate_user(u)
    return jsonify({
        "user_id": user_id,
        "allow_rating": can,
        "deny_reason": reason,
        "count": count,
        "avg": avg,
        "bayes": bayes,
        "histogram": histogram,
        "your_rating": your
    })


MIN_REASON_LEN = 10  # krátky, ale zmysluplný dôvod

@ratings_bp.post("/rate")
@login_required
def rate():
    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    ratee_id = data.get("ratee_id", None)
    stars = data.get("stars", None)
    recommend = data.get("recommend", None)
    category_key = (data.get("category_key") or "").strip() or None

    if not isinstance(ratee_id, int):
        return jsonify({"error": "missing_or_invalid_ratee_id"}), 400

    ratee = Pouzivatel.query.get(ratee_id)
    can, deny = _can_rate_user(ratee)
    if not can:
        return jsonify({"error": "not_allowed", "reason": deny}), 403

    if stars is not None:
        try:
            stars = int(stars)
        except Exception:
            return jsonify({"error": "invalid_stars"}), 400
        if stars < 1 or stars > 5:
            return jsonify({"error": "invalid_stars"}), 400

    if recommend is not None and not isinstance(recommend, bool):
        return jsonify({"error": "invalid_recommend"}), 400

    # 🔴 Povinný dôvod pri 1–2 hviezdičkách
    if stars is not None and stars <= 2 and len(reason) < MIN_REASON_LEN:
        return jsonify({"error": "note_required", "min_len": MIN_REASON_LEN}), 400

    existing = (UserRating.query
                .filter_by(rater_id=current_user.id, ratee_id=ratee_id)
                .first())

    if existing:
        # anti-blikanie
        if existing.updated_at and (datetime.utcnow() - existing.updated_at).total_seconds() < MIN_UPDATE_INTERVAL:
            return jsonify({"error": "too_frequent"}), 429

        if stars is not None:
            existing.stars = stars
        if recommend is not None:
            existing.recommend = recommend
        if category_key is not None:
            existing.category_key = category_key
        # uložiť dôvod len keď príde (neprepisovať na prázdno)
        if reason:
            existing.note = reason

        existing.status = "active"
        existing.updated_at = datetime.utcnow()
        db.session.commit()
    else:
        r = UserRating(
            ratee_id=ratee_id,
            rater_id=current_user.id,
            recommend=bool(recommend) if recommend is not None else False,
            stars=stars,
            category_key=category_key,
            note=reason or None,  # 🟢 uložíme dôvod
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.session.add(r)
        db.session.commit()

    agg = _recompute_user_aggregates(ratee_id)

    return jsonify({
        "ok": True,
        "ratee_id": ratee_id,
        "your_rating": {
            "stars": stars if stars is not None else (existing.stars if existing else None),
            "recommend": (recommend if recommend is not None else (existing.recommend if existing else False))
        },
        "summary": {
            "count": agg["count"],
            "avg": agg["avg"],
            "bayes": agg["bayes"],
            "histogram": agg["histogram"]
        }
    })


@ratings_bp.post("/remove")
@login_required
def remove():
    """„Zmaž“ svoje hodnotenie (soft-delete). JSON: {ratee_id:int}"""
    data = request.get_json(silent=True) or {}
    ratee_id = data.get("ratee_id", None)
    if not isinstance(ratee_id, int):
        return jsonify({"error": "missing_or_invalid_ratee_id"}), 400

    r = (UserRating.query
         .filter_by(rater_id=current_user.id, ratee_id=ratee_id, status="active")
         .first())
    if not r:
        return jsonify({"ok": True})  # nič na zmazanie = OK (idempotentné)

    r.status = "removed"
    r.updated_at = datetime.utcnow()
    db.session.commit()

    agg = _recompute_user_aggregates(ratee_id)
    return jsonify({
        "ok": True,
        "summary": {
            "count": agg["count"],
            "avg": agg["avg"],
            "bayes": agg["bayes"],
            "histogram": agg["histogram"]
        }
    })

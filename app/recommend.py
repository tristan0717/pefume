from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
import json, re

from .models import Recommendation
from .db import db
from .weather_utils import get_weather_data, get_weather
from .recommender import get_recommender

# ───────────────── 번역 유틸 (쿼리만 영어로) ─────────────────
try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None  # 라이브러리 미설치/오류 시 폴백

def translate_query_to_english(text: str) -> str:
    """
    한국어/혼합 입력을 영어로 번역. 실패하면 원문 반환.
    """
    text = (text or "").strip()
    if not text or GoogleTranslator is None:
        return text
    try:
        # source='auto'로 한국어/영어 혼합도 안전 처리
        return GoogleTranslator(source="auto", target="en").translate(text)
    except Exception:
        # 네트워크/쿼터/라이브러리 오류 시 원문 그대로 사용
        return text
# ─────────────────────────────────────────────────────────────

rec_bp = Blueprint('recommend', __name__, template_folder="../templates")


@rec_bp.route('/')
def home():
    return render_template('index.html')
    
@rec_bp.route('/discover', endpoint='discover', methods=['GET'])
@login_required
def discover():
    return render_template('discover.html')


@rec_bp.route('/recommend', methods=['POST'])
@login_required
def recommend():
    """
    입력:
      - 문장형: { "query": "...", "lat": float, "lon": float }
      - 또는:   { "user_cat": "...", "user_note": "...", "lat": float, "lon": float }
    """
    try:
        js = request.get_json() or {}
        query_ko = (js.get('query')     or '').strip()
        user_cat = (js.get('user_cat')  or '').strip()
        user_note= (js.get('user_note') or '').strip()

        # 문장이 없으면 cat+note를 합쳐서 '한국어 원문' 쿼리 생성
        if not query_ko:
            query_ko = " ".join([x for x in [user_cat, user_note] if x]).strip()

        # 날씨 정보
        lat = js.get('lat'); lon = js.get('lon')
        if lat is not None and lon is not None:
            wj   = get_weather_data(lat, lon)
            desc = ((wj or {}).get("weather") or [{}])[0].get("description", "")
            wstr = get_weather(lat, lon)
        else:
            desc = ""
            wstr = "날씨 정보를 가져올 수 없습니다."

        # ✅ 추천기는 '영문 쿼리'로 호출 (오직 쿼리만 번역)
        query_en = translate_query_to_english(query_ko)
        recsys = get_recommender()
        recs = recsys.recommend(query=query_en, weather_desc=desc, k=10)

        # ✅ any-매칭 필터는 '사용자 원문(한국어) 쿼리' 기준으로 우선 정렬
        def _simple_tokens(s: str):
            s = (s or "").lower()
            s = re.sub(r"[^0-9a-zA-Z\uac00-\ud7a3]+", " ", s)
            toks = [w for w in s.split() if w]
            return list(dict.fromkeys(toks))

        kws = _simple_tokens(query_ko)
        if kws:
            def _has_any(item):
                blob = " ".join([
                    str(item.get("Categorys") or "").lower(),
                    str(item.get("Note") or "").lower()
                ])
                return any(kw in blob for kw in kws)

            prioritized = [r for r in recs if _has_any(r)]
            others      = [r for r in recs if not _has_any(r)]
            if prioritized:
                recs = (prioritized + others)[:5]

        # 이력 저장(사용자에게 보이는 쿼리는 원문 유지)
        if query_ko and not user_cat:  user_cat  = query_ko
        if query_ko and not user_note: user_note = query_ko

        rec = Recommendation(
            user_id=current_user.id,
            user_cat=user_cat,
            user_note=user_note,
            weather_desc=desc,
            results_json=json.dumps(recs, ensure_ascii=False)
        )
        db.session.add(rec)
        db.session.commit()

        return jsonify(
            weather=wstr,
            weather_description=desc,
            response=recs,
            meta={"query_used_en": query_en}  # 디버깅용: 서버가 사용한 영문 쿼리(원하면 제거)
        ), 200

    except Exception as e:
        current_app.logger.exception("Error in /recommend")
        return jsonify(error="recommend_failed", detail=str(e)), 500


@rec_bp.route('/history')
@login_required
def history():
    rows = (Recommendation.query
            .filter_by(user_id=current_user.id)
            .order_by(Recommendation.queried_at.desc())
            .all())

    history_view = []
    for r in rows:
        # results_json 파싱
        try:
            items = json.loads(r.results_json) or []
        except Exception:
            items = []

        # 화면용으로 상위 5개만 추림
        pretty_items = []
        for p in items[:5]:
            pretty_items.append({
                "brand":     p.get("Brand"),
                "name":      p.get("Name"),
                "year":      p.get("Year"),
                "categorys": p.get("Categorys"),
                "note":      p.get("Note"),
                "picture":   p.get("Picture"),
            })

        history_view.append({
            "queried_at":   r.queried_at,
            "user_cat":     r.user_cat,
            "user_note":    r.user_note,
            "weather_desc": r.weather_desc,
            "items_list":   pretty_items,  # 템플릿에서 순회할 리스트
            "raw_items":    items,         # 원본 JSON (옵션)
        })

    return render_template('history.html', history=history_view)

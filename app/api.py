# app/api.py
import os
import json
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from dotenv import load_dotenv

from .weather_utils import get_weather, get_weather_data
from .recommend import recommend as recommend_view
from .models import Recommendation

load_dotenv()

api_bp = Blueprint('api', __name__)


@api_bp.route('/weather', methods=['POST'])
def weather():
    """
    요청 JSON: { "lat": float, "lon": float }
    응답 JSON: { "city": str, "temp": str, "description": str }
    """
    js = request.get_json() or {}
    lat, lon = js.get('lat'), js.get('lon')
    if lat is None or lon is None:
        return jsonify(error="위도·경도가 필요합니다"), 400

    w = get_weather(lat, lon)

    # ✨ 보강: get_weather가 dict를 주는 경우도 지원
    if isinstance(w, dict):
        city = w.get("city") or w.get("name") or ""
        # temp는 문자열/숫자 어떤 형태라도 문자열로 통일
        t = w.get("temp")
        if t is None:
            t = w.get("temperature")
        if t is None and isinstance(w.get("main"), dict):
            t = w["main"].get("temp")
        temp = str(t) if t is not None else ""
        desc = w.get("description") or w.get("weather") or ""
        # OpenWeather 스타일 weather[0].description 대응
        if not desc and isinstance(w.get("weather"), list) and w["weather"] and isinstance(w["weather"][0], dict):
            desc = w["weather"][0].get("description", "")
        return jsonify({"city": city, "temp": temp, "description": desc})

    # 기존 문자열 포맷을 그대로 파싱하여 반환 (프런트 호환)
    if isinstance(w, str):
        try:
            return jsonify({
                "city":        w.split("의 현재 날씨")[0],
                "temp":        w.split("기온은 ")[1].split("°C")[0],
                "description": w.split("현재 날씨는 ")[1].split("이며")[0]
            })
        except Exception:
            # 포맷 변경 등 예외 시 원문 전달
            return jsonify(city="", temp="", description="", raw=w)

    # 그 외 형식은 문자열로 덤프하여 raw로 반환
    return jsonify(city="", temp="", description="", raw=str(w))


@api_bp.route('/generate-custom-fragrance', methods=['POST'])
def generate_custom_fragrance():
    """
    요청 JSON:
      { "user_cat": str, "user_note": str, "weather": str, "notes": [str, ...] }
    응답 JSON:
      { "generated_note": str }  # 프론트에서 이 문자열을 그대로 렌더
    """
    js = request.get_json() or {}
    user_cat  = (js.get('user_cat') or '').strip()
    user_note = (js.get('user_note') or '').strip()
    weather   = (js.get('weather')   or '').strip()
    notes     = js.get('notes') or []

    prompt = f"""
당신은 전문 조향사입니다. 아래 정보를 반영해 새로운 향수를 제안하세요.
- 선호 카테고리: {user_cat}
- 취향 노트: {user_note}
- 현재 날씨: {weather}
- 추천 목록에서 수집된 노트 후보: {notes}

반드시 다음 JSON만 출력하세요 (코드펜스나 추가 설명 금지):
{{
  "name": "<짧은 한국어/영문 이름 1~2단어>",
  "category": "<한국어 카테고리(예: 시트러스, 아로마틱, 우디, 플로럴, 머스크, 앰버리, 그린, 스파이시, 오리엔탈, 푸제르 등)>",
  "mood": "<향의 분위기/컨셉(한국어)>",
  "top": ["노트1","노트2","노트3"],
  "middle": ["노트1","노트2","노트3"],
  "base": ["노트1","노트2","노트3"],
  "description": "<50~120자 정도 한국어 설명>"
}}
주의:
- 가능한 한 제공된 notes에서 우선 선택하고, 부족하면 보완 노트를 소량 추가하세요.
- top/middle/base는 각각 3~6개 사이.
- 추가 설명 없이 JSON만 출력하세요.
    """.strip()

    api_key = os.getenv("GENAI_API_KEY")

    try:
        if not api_key:
            raise RuntimeError("GENAI_API_KEY not set")

        import google.generativeai as genai  # pip install google-generativeai
        genai.configure(api_key=api_key)
        # ✨ 수정: 1.5 → 2.5 (v1beta에서 1.5 일부 generateContent 미지원 404 방지)
        model = genai.GenerativeModel("gemini-2.5-flash")
        resp = model.generate_content(prompt)
        text = (resp.text or "").strip()
        if not text:
            raise RuntimeError("Empty model response")

        return jsonify(generated_note=text), 200

    except Exception as e:
        # 폴백: 라이브러리/키/네트워크 문제 등에서도 프런트는 흐름 확인 가능
        mock = """{
  "name": "Citrus Veil",
  "category": "시트러스",
  "mood": "상큼하고 맑은 초여름 바람",
  "top": ["Bergamot", "Grapefruit", "Lemon"],
  "middle": ["Jasmine", "Neroli", "Lavender"],
  "base": ["Musk", "Cedarwood", "Amber"],
  "description": "시트러스 중심의 투명한 구조에 플로럴의 부드러움을 더해 산뜻하게 마무리됩니다."
}"""
        return jsonify(generated_note=mock, error=str(e)), 200


@api_bp.route('/api/my-recommendations', methods=['GET'])
@login_required
def my_recommendations():
    """
    상단바 '내 향수' 드롭다운용 최근 추천 요약.
    각 추천 기록에서 첫 번째 아이템만 뽑아 간단 목록으로 반환.

    쿼리 파라미터:
      ?limit=N  (기본 5)
    응답 JSON:
      { "items": [ { "Brand": str, "Name": str, "Year": int|None }, ... ] }
    """
    try:
        limit = int(request.args.get('limit', 5))
    except Exception:
        limit = 5

    recs = (Recommendation.query
            .filter_by(user_id=current_user.id)
            .order_by(Recommendation.queried_at.desc())
            .limit(limit)
            .all())

    items = []
    for r in recs:
        try:
            arr = json.loads(r.results_json) or []
            if arr:
                first = arr[0]
                items.append({
                    "Brand": first.get("Brand"),
                    "Name": first.get("Name"),
                    "Year": first.get("Year"),
                })
        except Exception:
            # 개별 파싱 실패는 건너뛰기
            continue

    return jsonify(items=items), 200

@api_bp.route("/my/recent", methods=["GET"])
@login_required
def my_recent():
  # 최근 10개 추천
  q = (Recommendation.query
       .filter_by(user_id=current_user.id)
       .order_by(Recommendation.queried_at.desc())
       .limit(10)
       .all())
  items = []
  for rec in q:
      # items_list 또는 items 필드에서 미리보기 3개 추출
      items_json = []
      try:
          items_json = rec.items_list or rec.items or []
      except Exception:
          items_json = []
      preview = []
      if isinstance(items_json, list):
          for p in items_json[:3]:
              if not isinstance(p, dict):
                  continue
              brand = (p.get("Brand") or p.get("brand") or "")
              name  = (p.get("Name")  or p.get("name")  or "")
              year  = (p.get("Year")  or p.get("year")  or "")
              preview.append({"brand": brand, "name": name, "year": year})
      items.append({
          "id": rec.id,
          "queried_at": rec.queried_at.isoformat() if rec.queried_at else "",
          "user_cat": rec.user_cat or "",
          "weather_desc": rec.weather_desc or "",
          "preview": preview
      })
  return jsonify({"items": items})
  

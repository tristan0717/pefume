Daily Perfume — AI 기반 개인 맞춤 향수 추천

자연어 한 줄로 “비 오는 날 포근한 머스크”, “출근용 산뜻한 시트러스”처럼 입력하면,
텍스트/노트/카테고리 기반 유사도와 현재 날씨를 반영해 향수를 추천하고,
Gemini로 “AI 생성 향수 노트”까지 만들어주는 Flask 웹앱입니다.
	•	대화형 인터페이스(채팅처럼 위로 쌓이는 피드)
	•	“더보기/접기”로 결과 페이징
	•	노트에 마우스오버 시 노트 이미지 팝업
	•	최근 추천 히스토리 & 드롭다운
	•	로그인/회원가입

  Demo 흐름
	1.	로그인/회원가입 → 2) /discover 페이지
	2.	입력창에 자연어로 취향/상황 입력 → 4) 상단에 내 말풍선 생성
	3.	아래에 추천 5개 표시(+ 더보기/접기), 곧이어 AI 생성 향수 1개가 이어서 표시
	4.	링크에 마우스를 올리면 해당 향수의 Top/Middle/Base 노트 이미지 팝업

  Tech Stack
	•	Web: Flask, Flask-Login, SQLAlchemy, Alembic
	•	Frontend: HTML/CSS/Vanilla JS (팝업/애니메이션/대화 피드)
	•	AI: Google Generative AI (Gemini 2.5 Flash)
	•	Recsys: TF-IDF + Cosine Similarity (노트/카테고리/설명 기반)
	•	Weather: OpenWeather (또는 호환 응답)
	•	DB: SQL(개발) / RDB 호환 (운영 전환 가능)

  f_project/
├─ app/
│  ├─ __init__.py           # create_app(), 블루프린트 등록
│  ├─ api.py                # /weather, /generate-custom-fragrance, /my/recent
│  ├─ recommend.py          # /discover, /recommend, /history
│  ├─ recommender.py        # get_recommender(): TF-IDF + cosine
│  ├─ weather_utils.py      # get_weather(), get_weather_data()
│  ├─ images.py             # /note-img/<slug>  (노트 이미지 정적 제공)
│  ├─ models.py             # User, Recommendation
│  ├─ db.py                 # db, migrate (SQLAlchemy/Alembic glue)
│  ├─ auth/                 # login/register/logout blueprint
│  └─ ...
├─ templates/
│  ├─ base.html
│  ├─ index.html
│  ├─ discover.html         # 대화형 UI
│  └─ history.html
├─ static/
│  ├─ style.css
│  └─ script.js             # 팝업/날씨칩/대화피드/“더보기·접기”
├─ uploads/                 # (옵션) 데이터/이미지
├─ config.py
├─ requirements.txt
├─ manage.py
└─ README.md  

주요 라우트 & API

화면 라우트 (Blueprint: recommend)
	•	GET / → index.html (홈)
	•	GET /discover → 대화형 추천 페이지 (로그인 필요)
	•	GET /history → 내 최근 추천 기록(상위 5개씩 미리보기)

API (Blueprint: api)
	•	POST /weather
Req: { "lat": float, "lon": float }
Res: { "city": str, "temp": str, "description": str }
	•	POST /generate-custom-fragrance

import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

# .env 로드
load_dotenv()

# 경로들(프로젝트 루트 기준)
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(PROJECT_DIR, "static")
PICTURE_DIR = os.path.join(STATIC_DIR, "picture")


def _build_mysql_uri() -> str:
    """
    .env에 DB 접속 정보가 모두 있을 때만 MySQL URI 생성.
    하나라도 없으면 빈 문자열 반환(= 폴백용으로 SQLite 사용).
    """
    user = os.getenv("DB_USER")
    pwd_raw = os.getenv("DB_PASS", "")
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME")

    if not (user and name):
        return ""  # 필수 값 빠지면 MySQL 사용 안 함

    pwd = quote_plus(pwd_raw)  # 특수문자 안전 처리
    return f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{name}?charset=utf8mb4"


class Config:
    # --- 기본 시크릿키 ---
    SECRET_KEY = os.getenv("SECRET_KEY") or "dev-secret"

    # --- 정적/이미지 경로 설정(백엔드/프론트 공용) ---
    STATIC_DIR = STATIC_DIR
    PICTURE_DIR = PICTURE_DIR
    NOTE_IMAGE_ALLOWED_EXTS = ["webp", "jpg", "jpeg", "png"]  # 프론트와 일치
    NOTE_IMAGE_PLACEHOLDER = os.path.join(PICTURE_DIR, "_placeholder.jpg")

    # --- DB 연결 (MySQL 우선, 실패 시 SQLite 폴백) ---
    _MYSQL_URI = _build_mysql_uri()
    if _MYSQL_URI:
        SQLALCHEMY_DATABASE_URI = _MYSQL_URI
    else:
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(PROJECT_DIR, "app.db")

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # (선택) 로그 보기 원하면 .env에 SQLALCHEMY_ECHO=1
    SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO", "0") in ("1", "true", "True")

    # --- 외부 API 키(있는 경우에만 사용) ---
    # 예: GENAI_API_KEY, WEATHER_API_KEY 등
    GENAI_API_KEY = os.getenv("GENAI_API_KEY", "")
    WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")

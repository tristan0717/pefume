import os
from flask import Flask
from flask import Flask, render_template
from flask_login import LoginManager

from .db import db, migrate
from .models import User
from .auth import auth_bp
from .recommend import rec_bp
from .api import api_bp
from config import Config
from .images import images_bp


def create_app():
    # 프로젝트 루트(…/f_project)
    proj_dir = os.path.dirname(os.path.abspath(os.path.join(__file__, os.pardir)))

    app = Flask(
        __name__,
        static_folder=os.path.join(proj_dir, "static"),
        template_folder=os.path.join(proj_dir, "templates"),
    )

    # 1) 환경/설정 로드
    app.config.from_object(Config)

    # 2) 필수 설정 누락 시 안전한 기본값 채우기
    #    - DB URI가 없다면 프로젝트 루트의 app.db를 사용
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(proj_dir, "app.db")
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("SECRET_KEY", os.environ.get("SECRET_KEY", "dev-secret-change-me"))

    # 3) DB & 마이그레이션 초기화
    db.init_app(app)
    migrate.init_app(app, db)

    # 4) 로그인 매니저
    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # 5) 블루프린트 등록
    app.register_blueprint(api_bp)   # /weather 등
    app.register_blueprint(auth_bp)  # /auth/*
    app.register_blueprint(images_bp)
    app.register_blueprint(rec_bp)   # /, /recommend, /history
    
    # (선택) 노트 이미지 정적 라우트 블루프린트가 있다면 등록
    # from .images import images_bp
    # app.register_blueprint(images_bp)

    return app

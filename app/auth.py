from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User
from .db import db

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        email = request.form['email'].lower()
        pw    = request.form['password']

        if User.query.filter_by(email=email).first():
            flash('이미 등록된 이메일입니다.', 'danger')
            return redirect(url_for('auth.register'))

        # scrypt 미지원 환경 대응: PBKDF2-SHA256으로 명시
        hashed = generate_password_hash(pw, method='pbkdf2:sha256', salt_length=16)
        user = User(email=email, password=hashed)

        db.session.add(user)
        db.session.commit()
        flash('회원가입 성공! 로그인 해주세요.', 'success')
        return redirect(url_for('recommend.home'))

    return render_template('register.html')

@auth_bp.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].lower()
        pw    = request.form['password']
        user  = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, pw):
            login_user(user)
        else:
            flash('로그인 실패: 이메일 또는 비밀번호 확인', 'danger')

        return redirect(url_for('recommend.home'))

    # GET 요청 시 메인으로 리디렉트
    return redirect(url_for('recommend.home'))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('recommend.home'))


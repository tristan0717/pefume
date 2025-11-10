# app/images.py
from __future__ import annotations
import os
import unicodedata
from flask import Blueprint, current_app, send_from_directory

images_bp = Blueprint("images_bp", __name__)  # url_prefix 없음: /note-img/<slug>

# 서버가 지원할 확장자 우선순위 (앞순위가 먼저 탐색)
NOTE_IMG_EXTS = ("webp", "jpg", "jpeg", "png")


def _static_picture_dir() -> str:
    """
    이미지 폴더 경로를 반환.
    기본값: <프로젝트>/static/picture
    필요하다면 app.config['PICTURE_DIR'] 로 오버라이드 가능.
    """
    # current_app.static_folder == "<프로젝트>/static"
    base = current_app.config.get("PICTURE_DIR")
    if base:
        return base
    return os.path.join(current_app.static_folder, "picture")


def _slugify(text: str) -> str:
    """
    프론트와 동일한 규칙으로 슬러그화.
    (NFKD 정규화 -> ASCII 탈락 -> 소문자 -> 비영숫자 '-' 치환 -> 연속 '-' 정리)
    """
    s = unicodedata.normalize("NFKD", str(text))
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    out = []
    for ch in s:
        out.append(ch if ch.isalnum() else "-")
    s = "".join(out)
    s = "-".join(part for part in s.split("-") if part)
    return s


def _resolve_note_image(slug: str) -> tuple[str, str]:
    """
    주어진 slug에 대해 실제 파일명을 찾아서 반환한다.
    (dir_path, filename) 튜플을 리턴. 없으면 플레이스홀더를 리턴.
    """
    dir_path = _static_picture_dir()

    # 1) 정확히 같은 이름의 파일부터 (확장자 우선순위대로)
    for ext in NOTE_IMG_EXTS:
        candidate = f"{slug}.{ext}"
        full = os.path.join(dir_path, candidate)
        if os.path.exists(full):
            return dir_path, candidate

    # 2) 파일명 대소문자/유니코드 차이를 느슨하게 매칭
    try:
        names = os.listdir(dir_path)
    except FileNotFoundError:
        names = []

    slug_lower = slug.lower()
    for name in names:
        base, ext = os.path.splitext(name)
        if ext.lstrip(".").lower() in NOTE_IMG_EXTS and _slugify(base) == slug_lower:
            return dir_path, name

    # 3) 최종 플레이스홀더 (반드시 프로젝트에 두세요)
    placeholder = "_placeholder.jpg"
    return dir_path, placeholder


@images_bp.route("/note-img/<path:slug>")
def note_img(slug: str):
    """
    프론트는 언제나 /note-img/<slug> 로만 요청.
    서버가 확장자를 찾아서 1회 응답으로 보내며, 없으면 플레이스홀더(200).
    """
    dir_path, filename = _resolve_note_image(slug)

    resp = send_from_directory(directory=dir_path, path=filename, conditional=True)
    # 강한 캐시(이미지 교체가 거의 없다는 가정)
    resp.cache_control.public = True
    resp.cache_control.max_age = 60 * 60 * 24 * 365  # 1년
    # ETag / Last-Modified는 send_from_directory가 세팅
    return resp

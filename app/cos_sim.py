import pandas as pd, ast
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- 캐시 ---
_DF = None
_CAT_V, _NOTE_V = None, None
_CAT_M, _NOTE_M = None, None

def _norm_list_or_json(s):
    if s is None: return ""
    t = str(s).strip()
    try:
        v = ast.literal_eval(t)
        if isinstance(v, dict):
            bag = []
            for k in ("top","middle","base","middleNotes","baseNotes","topNotes"):
                if k in v and isinstance(v[k], list): bag += v[k]
            if not bag:
                for k, vv in v.items():
                    if isinstance(vv, list): bag += vv
            return " ".join(map(str, bag))
        if isinstance(v, list):
            return " ".join(map(str, v))
    except Exception:
        pass
    return t

def load_perfume_data(file_path: str):
    global _DF, _CAT_V, _NOTE_V, _CAT_M, _NOTE_M
    if _DF is not None:
        return _DF

    df = pd.read_csv(file_path)
    # 불필요 컬럼 제거
    drop_cols = [c for c in df.columns if c.startswith("Unnamed")]
    df = df.drop(columns=drop_cols, errors="ignore")

    # 텍스트 정규화
    df["CatText"]  = df["Categorys"].astype(str).map(_norm_list_or_json)
    df["NoteText"] = df["Note"].astype(str).map(_norm_list_or_json)
    # 연도 정리
    if "Year" in df.columns:
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")

    # 벡터라이저/행렬 한 번만 생성
    _CAT_V  = TfidfVectorizer()
    _NOTE_V = TfidfVectorizer()
    _CAT_M  = _CAT_V.fit_transform(df["CatText"])
    _NOTE_M = _NOTE_V.fit_transform(df["NoteText"])

    _DF = df
    return _DF

def calculate_cosine_similarity(user_cat, user_note, perfume_data, weather_desc=None):
    if perfume_data is None:
        return []

    # 캐시에서 벡터라이저/행렬 사용
    global _CAT_V, _NOTE_V, _CAT_M, _NOTE_M
    user_cat_vec  = _CAT_V.transform([user_cat or ""])
    user_note_vec = _NOTE_V.transform([user_note or ""])
    cat_sim  = cosine_similarity(user_cat_vec,  _CAT_M).flatten()
    note_sim = cosine_similarity(user_note_vec, _NOTE_M).flatten()

    if weather_desc:
        weather_vec = _CAT_V.transform([weather_desc])
        weather_sim = cosine_similarity(weather_vec, _CAT_M).flatten()
        final_sim   = (cat_sim + note_sim + weather_sim) / 3
    else:
        final_sim   = (cat_sim + note_sim) / 2

    perfume_data = perfume_data.copy()
    perfume_data["similarity"] = final_sim
    top5 = perfume_data.sort_values("similarity", ascending=False).head(5).copy()
    top5["Year"] = top5["Year"].where(~top5["Year"].isna(), None)
    return top5[["Brand","Name","Year","Picture","Categorys","Note"]].to_dict(orient="records")

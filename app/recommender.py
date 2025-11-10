import os, re, json, random
from functools import lru_cache
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

import numpy as np
import pandas as pd

# semantic
from sentence_transformers import SentenceTransformer
import faiss

# lexical
from rank_bm25 import BM25Okapi

from flask import current_app

# ---------------- 설정 ----------------
DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
FORCE_DEVICE  = os.getenv("EMBEDDING_DEVICE", "cpu")  # CPU 강제 (meta tensor 버그 회피)

RANDOM_SEED = int(os.getenv("REC_RANDOM_SEED", "42"))
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# 가중치
W_SEMANTIC = float(os.getenv("W_SEMANTIC", "0.6"))
W_BM25     = float(os.getenv("W_BM25",     "0.25"))
W_WEATHER  = float(os.getenv("W_WEATHER",  "0.15"))

TOPN_CANDIDATES = int(os.getenv("TOPN_CANDIDATES", "30"))  # 1차 후보
RETURN_K        = int(os.getenv("RETURN_K", "5"))          # 최종 개수
MMR_LAMBDA      = float(os.getenv("MMR_LAMBDA", "0.7"))    # 다양화 강도

# ---------------- 유틸 ----------------
def _tokenize_ko_en(text: str) -> List[str]:
    t = (text or "").lower()
    t = re.sub(r"[^0-9a-zA-Z\uac00-\ud7a3]+", " ", t)
    return [w for w in t.split() if w]

def _safe_normalize(mat: np.ndarray) -> np.ndarray:
    if mat is None or mat.size == 0:
        return mat
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-9, norms)
    return mat / norms

def _mmr(doc_embeddings: np.ndarray,
         query_embedding: np.ndarray,
         candidates_idx: List[int],
         top_k: int,
         lambda_coef: float = 0.7) -> List[int]:
    """Maximal Marginal Relevance (cosine + 강한 방어로직)."""
    if not candidates_idx:
        return []
    if len(candidates_idx) <= top_k:
        return candidates_idx[:top_k]

    if doc_embeddings is None or doc_embeddings.size == 0:
        return candidates_idx[:top_k]
    if query_embedding is None or query_embedding.size == 0:
        return candidates_idx[:top_k]

    try:
        D = np.asarray(doc_embeddings[candidates_idx], dtype=np.float32, order="C")
        q = np.asarray(query_embedding, dtype=np.float32).reshape(1, -1)
    except Exception:
        return candidates_idx[:top_k]

    D = _safe_normalize(D)
    q = _safe_normalize(q)

    D = np.clip(np.nan_to_num(D, nan=0.0, posinf=0.0, neginf=0.0), -1.0, 1.0)
    q = np.clip(np.nan_to_num(q, nan=0.0, posinf=0.0, neginf=0.0), -1.0, 1.0)

    with np.errstate(all="ignore"):
        sim_to_query = (D @ q.T).ravel()
        sim_between  = (D @ D.T)

    sim_to_query = np.nan_to_num(sim_to_query, nan=0.0, posinf=0.0, neginf=0.0)
    sim_between  = np.nan_to_num(sim_between,  nan=0.0, posinf=0.0, neginf=0.0)

    selected = []
    remaining = list(range(len(candidates_idx)))

    first = int(np.argmax(sim_to_query)) if sim_to_query.size else 0
    selected.append(first)
    if first in remaining:
        remaining.remove(first)

    while len(selected) < top_k and remaining:
        best_idx = None
        best_score = -1e9
        for r in remaining:
            relevance = float(sim_to_query[r]) if r < sim_to_query.size else 0.0
            diversity = float(np.max(sim_between[r, selected])) if sim_between.size else 0.0
            if not np.isfinite(relevance): relevance = 0.0
            if not np.isfinite(diversity): diversity = 0.0
            mmr_score = lambda_coef * relevance - (1 - lambda_coef) * diversity
            if mmr_score > best_score:
                best_score, best_idx = mmr_score, r
        if best_idx is None:
            break
        selected.append(best_idx)
        remaining.remove(best_idx)

    return [candidates_idx[i] for i in selected[:top_k]]

def _weather_tags_kor(desc: str) -> List[str]:
    d = (desc or "").lower()
    tags = []
    if any(k in d for k in ["rain", "비", "소나기", "drizzle"]): tags += ["clean", "fresh", "musk", "aquatic"]
    if any(k in d for k in ["cloud", "구름", "overcast"]):     tags += ["powdery", "soft", "cozy"]
    if any(k in d for k in ["sun", "맑", "clear"]):            tags += ["citrus", "green", "aromatic", "floral"]
    if any(k in d for k in ["snow", "눈", "cold"]):            tags += ["amber", "woody", "spicy"]
    if any(k in d for k in ["haze", "mist", "안개"]):          tags += ["herbal", "tea", "soft"]
    return tags

def _weather_match_score(note_text: str, weather_desc: str) -> float:
    tags = _weather_tags_kor(weather_desc)
    if not tags:
        return 0.0
    t = " " + (note_text or "").lower() + " "
    c = sum(1 for tag in tags if f" {tag} " in t)
    return min(1.0, c / max(1, len(tags)))

# ---------------- 데이터/인덱스 ----------------
@dataclass
class Doc:
    idx: int
    brand: str
    name: str
    year: Optional[int]
    text: str
    raw: Dict

class Recommender:
    def __init__(self, csv_path: str, model_name: str = DEFAULT_MODEL, device: str = FORCE_DEVICE):
        self.csv_path = csv_path
        self.model_name = model_name
        self.device = device
        self.model: Optional[SentenceTransformer] = None
        self.docs: List[Doc] = []
        self.embeddings: Optional[np.ndarray] = None
        self.faiss: Optional[faiss.IndexFlatIP] = None
        self.bm25: Optional[BM25Okapi] = None
        self._load()

    def _load(self):
        df = pd.read_csv(self.csv_path)
        for col in list(df.columns):
            if col.startswith("Unnamed"):
                df = df.drop(columns=[col])

        def norm_list_or_json(val):
            s = "" if (val is None or (isinstance(val, float) and np.isnan(val))) else str(val)
            if s and (s.strip().startswith("{") or s.strip().startswith("[")):
                try:
                    v = json.loads(s)
                    if isinstance(v, dict):
                        bag = []
                        for k in ("top","middle","base","middleNotes","baseNotes","topNotes","Categorys","Note"):
                            if k in v and isinstance(v[k], list):
                                bag += [str(x) for x in v[k]]
                        if not bag:
                            for _, vv in v.items():
                                if isinstance(vv, list): bag += [str(x) for x in vv]
                        return " ".join(bag)
                    if isinstance(v, list):
                        return " ".join([str(x) for x in v])
                except Exception:
                    pass
            return s

        cat_text  = df.get("Categorys", pd.Series([""]*len(df))).map(norm_list_or_json).fillna("")
        note_text = df.get("Note", pd.Series([""]*len(df))).map(norm_list_or_json).fillna("")
        full_text = (cat_text + " " + note_text).str.strip()

        docs = []
        for i, row in df.iterrows():
            year = None
            if "Year" in row and pd.notna(row["Year"]):
                try: year = int(row["Year"])
                except Exception: year = None
            docs.append(Doc(
                idx=i,
                brand=str(row.get("Brand", "")) if pd.notna(row.get("Brand", "")) else "",
                name=str(row.get("Name", "")) if pd.notna(row.get("Name", "")) else "",
                year=year,
                text=str(full_text.iloc[i]) if pd.notna(full_text.iloc[i]) else "",
                raw=row.to_dict(),
            ))
        self.docs = docs

        if not self.docs:
            self.embeddings = np.zeros((0, 384), dtype="float32")
            self.faiss = faiss.IndexFlatIP(384)
            self.bm25 = BM25Okapi([[]])
            return

        self.model = SentenceTransformer(self.model_name, device=self.device)
        corpus = [d.text for d in self.docs]
        if corpus:
            emb = self.model.encode(
                corpus,
                batch_size=64,
                show_progress_bar=False,
                normalize_embeddings=True
            )
            self.embeddings = np.asarray(emb, dtype="float32")
        else:
            self.embeddings = np.zeros((0, 384), dtype="float32")

        dim = self.embeddings.shape[1] if self.embeddings.size else 384
        index = faiss.IndexFlatIP(dim)
        if self.embeddings.size:
            index.add(self.embeddings)
        self.faiss = index

        tokenized = [_tokenize_ko_en(d.text) for d in self.docs]
        self.bm25 = BM25Okapi(tokenized if tokenized else [[]])

    def search(self, query: str, weather_desc: str = "", topn: int = TOPN_CANDIDATES) -> List[Tuple[int, float]]:
        query = (query or "").strip()
        if not query or self.faiss is None or self.embeddings is None or self.bm25 is None:
            return []

        q_emb = self.model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0].astype("float32")
        if not np.isfinite(q_emb).all():
            return []

        D, I = self.faiss.search(q_emb.reshape(1, -1), max(1, min(topn, len(self.docs))))
        sem_scores = D[0] if D.size else np.array([])
        sem_idx    = I[0] if I.size else np.array([], dtype=int)

        bm25_scores = self.bm25.get_scores(_tokenize_ko_en(query)) if len(self.docs) else np.array([])
        bm25_dict = {i: float(bm25_scores[i]) for i in range(len(self.docs))} if bm25_scores.size else {}
        bm25_max = max([v for v in bm25_dict.values()] + [1e-9])
        bm25_norm = {i: (bm25_dict.get(i, 0.0) / bm25_max) for i in range(len(self.docs))}

        weather_norm = {}
        for i in sem_idx:
            txt = self.docs[int(i)].text if int(i) < len(self.docs) else ""
            weather_norm[int(i)] = _weather_match_score(txt, weather_desc)

        scored = []
        for i, s in zip(sem_idx, sem_scores):
            i = int(i)
            hybrid = (
                W_SEMANTIC * float(s) +
                W_BM25     * float(bm25_norm.get(i, 0.0)) +
                W_WEATHER  * float(weather_norm.get(i, 0.0))
            )
            scored.append((i, hybrid))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:topn]

    def rerank_mmr(self, query: str, candidates: List[Tuple[int, float]], k: int = RETURN_K) -> List[int]:
        if not candidates:
            return []
        idxs = [int(i) for i, _ in candidates]
        q_emb = self.model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0].astype("float32")
        if not np.isfinite(q_emb).all():
            return idxs[:k]
        return _mmr(self.embeddings, q_emb, idxs, k, lambda_coef=MMR_LAMBDA)

    def recommend(self, query: str, weather_desc: str = "", k: int = RETURN_K) -> List[Dict]:
        candidates = self.search(query, weather_desc, topn=TOPN_CANDIDATES)
        if not candidates:
            return []

        mmr_idxs = self.rerank_mmr(query, candidates, k=k)
        if not mmr_idxs:
            mmr_idxs = [i for i, _ in candidates[:k]]

        final_idxs = list(mmr_idxs[:k])
        if len(candidates) > k:
            pool = [i for i, _ in candidates[k: min(len(candidates), k+10)]]
            if pool:
                pick = random.choice(pool)
                final_idxs[-1] = int(pick)

        out = []
        for i in final_idxs:
            if i < 0 or i >= len(self.docs):
                continue
            d = self.docs[int(i)]
            row = d.raw

            def _safe(val):
                if val is None:
                    return None
                if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
                    return None
                return val

            out.append({
                "Brand":     _safe(d.brand),
                "Name":      _safe(d.name),
                "Year":      _safe(d.year),
                "Picture":   _safe(row.get("Picture")),
                "Categorys": _safe(row.get("Categorys")),
                "Note":      _safe(row.get("Note")),
            })
        return out


# 싱글턴 캐시
@lru_cache(maxsize=1)
def get_recommender() -> Recommender:
    csv_path = os.path.normpath(os.path.join(current_app.root_path, "..", "per_data.csv"))
    return Recommender(csv_path, model_name=DEFAULT_MODEL, device=FORCE_DEVICE)

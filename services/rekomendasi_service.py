import hashlib
import json
import math
import re
from datetime import datetime
from typing import Optional
import joblib
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize
from sqlmodel import Session, select, text
from models.rekomendasi_model import RiwayatRekomendasi, UserAccount, UserFavorite

print("Memuat model AI (Multi-Feature CBF + Multi-Label Logistic Regression)...")
model_bundle = joblib.load("ai_movie_model.pkl")
clf_model = model_bundle["classifier"]
mlb_classes = list(model_bundle["mlb_classes"])
genre_threshold = float(model_bundle.get("genre_threshold", 0.55))
overview_embeddings = model_bundle["overview_embeddings"]
genre_matrix = model_bundle["genre_matrix"]
cbf_item_vectors = model_bundle["cbf_item_vectors"]
movies_df = model_bundle["movies_df"]
model_metrics = model_bundle["metrics"]

# Indeks cepat judul film (lowercase) -> indeks baris dataframe untuk lookup CBF & favorit
title_to_idx = {}
for idx_row, title_val in enumerate(movies_df["names"].tolist()):
    key = str(title_val).strip().lower()
    if key not in title_to_idx:
        title_to_idx[key] = idx_row

sbert_model = SentenceTransformer("all-MiniLM-L6-v2")
print("Model AI siap digunakan!")


def clean_text(raw_text: str) -> str:
    cleaned = str(raw_text).lower()
    cleaned = re.sub(r"[^a-z0-9\s.,!?\']", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def get_ai_info():
    return model_metrics


def get_available_genres():
    return mlb_classes


def pastikan_struktur_tabel(session: Session):
    """Memastikan kolom user_id & tabel user_favorite tersedia di PostgreSQL"""
    try:
        session.exec(
            text("ALTER TABLE riwayat_rekomendasi ADD COLUMN IF NOT EXISTS user_id INTEGER;")
        )
        session.exec(
            text(
                """
                CREATE TABLE IF NOT EXISTS user_favorite (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    movie_title VARCHAR NOT NULL,
                    movie_date VARCHAR DEFAULT '-',
                    movie_genre VARCHAR DEFAULT '-',
                    movie_score DOUBLE PRECISION DEFAULT 0.0,
                    waktu_favorit VARCHAR NOT NULL
                );
                """
            )
        )
        session.commit()
    except Exception:
        session.rollback()

def _format_movie_dict(idx: int, similarity_pct: Optional[float] = None, rank: Optional[int] = None):
    row = movies_df.iloc[idx]
    item = {
        "names": str(row["names"]),
        "date_x": str(row["date_x"]),
        "release_year": int(row.get("release_year", 0)),
        "score": round(float(row["score"]), 1),
        "genre": str(row["genre"]),
        "main_genre": str(row.get("main_genre", row["genre"])),
        "overview": str(row["overview"]),
        "crew": str(row["crew"]),
        "orig_lang": str(row["orig_lang"]),
        "country": str(row["country"]),
    }
    if rank is not None:
        item["rank"] = int(rank)
    if similarity_pct is not None:
        item["similarity"] = round(float(similarity_pct), 1)
    return item


# ==========================================
# FUNGSI AUTENTIKASI & MANAJEMEN AKUN USER
# ==========================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def register_user(session: Session, nama_lengkap: str, username: str, email: str, password: str):
    username_clean = username.strip().lower()
    email_clean = email.strip().lower()

    existing_user = session.exec(
        select(UserAccount).where(
            (UserAccount.username == username_clean) | (UserAccount.email == email_clean)
        )
    ).first()
    if existing_user:
        return None, "Username atau Email sudah terdaftar. Silakan gunakan yang lain."

    new_user = UserAccount(
        nama_lengkap=nama_lengkap.strip(),
        username=username_clean,
        email=email_clean,
        password_hash=hash_password(password),
        waktu_daftar=datetime.now().strftime("%d-%m-%Y %H:%M"),
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return new_user, None


def authenticate_user(session: Session, identifier: str, password: str):
    ident_clean = identifier.strip().lower()
    pw_hash = hash_password(password)

    user = session.exec(
        select(UserAccount).where(
            ((UserAccount.username == ident_clean) | (UserAccount.email == ident_clean))
            & (UserAccount.password_hash == pw_hash)
        )
    ).first()
    return user


def reset_password_user(session: Session, username: str, email: str, new_password: str):
    u_clean = username.strip().lower()
    e_clean = email.strip().lower()

    user = session.exec(
        select(UserAccount).where(
            (UserAccount.username == u_clean) & (UserAccount.email == e_clean)
        )
    ).first()
    if not user:
        return False, "Kombinasi Username dan Email tidak ditemukan."

    user.password_hash = hash_password(new_password)
    session.add(user)
    session.commit()
    return True, "Password berhasil diperbarui! Silakan login dengan password baru."


def get_user_by_id(session: Session, user_id: int):
    return session.get(UserAccount, user_id)


def update_user_profile(
    session: Session, user_id: int, nama_lengkap: str, email: str, new_password: str = ""
):
    user = session.get(UserAccount, user_id)
    if not user:
        return None, "Akun tidak ditemukan."

    email_clean = email.strip().lower()
    cek_email = session.exec(
        select(UserAccount).where(
            (UserAccount.email == email_clean) & (UserAccount.id != user_id)
        )
    ).first()
    if cek_email:
        return None, "Email tersebut sudah digunakan oleh akun lain."

    user.nama_lengkap = nama_lengkap.strip()
    user.email = email_clean
    if new_password.strip():
        user.password_hash = hash_password(new_password.strip())

    session.add(user)
    session.commit()
    session.refresh(user)
    return user, "Profil berhasil diperbarui!"


# ==========================================
# FUNGSI FAVORIT & PERSONALISASI CBF (USER PROFILE VECTOR)
# ==========================================
def get_user_favorites(session: Session, user_id: int):
    pastikan_struktur_tabel(session)
    records = session.exec(
        select(UserFavorite)
        .where(UserFavorite.user_id == user_id)
        .order_by(UserFavorite.id.desc())
    ).all()
    return records


def get_user_favorite_titles(session: Session, user_id: int):
    favs = get_user_favorites(session, user_id)
    return {f.movie_title.strip().lower() for f in favs}


def toggle_user_favorite(session: Session, user_id: int, movie_title: str):
    pastikan_struktur_tabel(session)
    title_clean = movie_title.strip()
    existing = session.exec(
        select(UserFavorite).where(
            (UserFavorite.user_id == user_id)
            & (UserFavorite.movie_title == title_clean)
        )
    ).first()

    if existing:
        session.delete(existing)
        session.commit()
        return False, f'"{title_clean}" dihapus dari daftar favorit Anda.'

    idx = title_to_idx.get(title_clean.lower())
    if idx is not None:
        row = movies_df.iloc[idx]
        m_title = str(row["names"])
        m_date = str(row["date_x"])
        m_genre = str(row["genre"])
        m_score = round(float(row["score"]), 1)
    else:
        m_title = title_clean
        m_date = "-"
        m_genre = "-"
        m_score = 0.0

    new_fav = UserFavorite(
        user_id=user_id,
        movie_title=m_title,
        movie_date=m_date,
        movie_genre=m_genre,
        movie_score=m_score,
        waktu_favorit=datetime.now().strftime("%d-%m-%Y %H:%M"),
    )
    session.add(new_fav)
    session.commit()
    return True, f'"{m_title}" ditambahkan ke favorit untuk personalisasi CBF!'


def delete_favorite_by_id(session: Session, user_id: int, fav_id: int):
    pastikan_struktur_tabel(session)
    fav = session.get(UserFavorite, fav_id)
    if fav and fav.user_id == user_id:
        session.delete(fav)
        session.commit()
        return True
    return False


def get_personalized_recommendations(
    session: Session,
    user_id: int,
    nama_user: Optional[str] = None,
    top_n: int = 8,
):
    """
    Membentuk User Profile Vector (rata-rata vektor CBF film favorit atau riwayat pencarian)
    untuk menghasilkan rekomendasi personal khusus akun aktif.
    """
    pastikan_struktur_tabel(session)
    favs = get_user_favorites(session, user_id)

    fav_indices = []
    for fav in favs:
        idx = title_to_idx.get(fav.movie_title.strip().lower())
        if idx is not None:
            fav_indices.append(idx)

    # Prioritas 1: Bangun User Profile Vector dari film yang difavoritkan user
    if fav_indices:
        profile_vec = np.mean(cbf_item_vectors[fav_indices], axis=0, keepdims=True)
        profile_vec = normalize(profile_vec, norm="l2")

        sims = cosine_similarity(profile_vec, cbf_item_vectors)[0]
        # Kecualikan film yang sudah difavoritkan agar muncul rekomendasi baru
        for ex_idx in fav_indices:
            sims[ex_idx] = -1.0

        top_indices = sims.argsort()[-top_n:][::-1]
        recs = [
            _format_movie_dict(
                int(idx),
                similarity_pct=max(0.0, min(float(sims[idx]) * 100.0, 100.0)),
                rank=r,
            )
            for r, idx in enumerate(top_indices, start=1)
        ]
        # Ringkasan genre favorit dari daftar favorit user
        genre_counts = {}
        for idx in fav_indices:
            for g in movies_df.iloc[idx]["genre_list"]:
                genre_counts[g] = genre_counts.get(g, 0) + 1
        top_genres = [
            g for g, _ in sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        ]
        source_info = (
            f"Profil CBF dari {len(fav_indices)} film favorit Anda"
            + (f" (Minat utama: {', '.join(top_genres)})" if top_genres else "")
        )
        return {
            "is_personalized": True,
            "source_type": "favorites",
            "source_info": source_info,
            "fav_count": len(fav_indices),
            "recommendations": recs,
        }

    # Prioritas 2: Jika belum ada favorit, bangun profil dari riwayat pencarian akun
    riwayat = get_all_rekomendasi(session, user_id=user_id, nama_user=nama_user)
    if riwayat:
        history_indices = []
        for item in riwayat[:3]:
            for d in item["detail_list"][:3]:
                idx = title_to_idx.get(str(d.get("names", "")).strip().lower())
                if idx is not None and idx not in history_indices:
                    history_indices.append(idx)

        if history_indices:
            profile_vec = np.mean(cbf_item_vectors[history_indices], axis=0, keepdims=True)
            profile_vec = normalize(profile_vec, norm="l2")
            sims = cosine_similarity(profile_vec, cbf_item_vectors)[0]

            top_indices = sims.argsort()[-top_n:][::-1]
            recs = [
                _format_movie_dict(
                    int(idx),
                    similarity_pct=max(0.0, min(float(sims[idx]) * 100.0, 100.0)),
                    rank=r,
                )
                for r, idx in enumerate(top_indices, start=1)
            ]
            return {
                "is_personalized": True,
                "source_type": "history",
                "source_info": f"Profil CBF otomatis dari {min(len(riwayat), 3)} riwayat pencarian terakhir Anda (Tambahkan ♥ Favorit agar makin akurat)",
                "fav_count": 0,
                "recommendations": recs,
            }

    # Cold-Start User: belum punya favorit maupun riwayat
    return {
        "is_personalized": False,
        "source_type": "cold_start",
        "source_info": "Belum ada profil selera. Tandai minimal 1 film sebagai ♥ Favorit di halaman Cari Film atau lakukan pencarian AI.",
        "fav_count": 0,
        "recommendations": [],
    }

def get_split_personalized_recommendations(
    session: Session,
    user_id: int,
    nama_user: Optional[str] = None,
    top_n: int = 15,
):
    """
    Menghasilkan 2 daftar rekomendasi CBF terpisah untuk halaman /untuk-anda:
    1. Berdasarkan daftar film favorit (User Profile Vector 461-Dim: 65% Overview + 25% Genre + 10% Kru)
    2. Berdasarkan riwayat pencarian overview (Rata-rata vektor Sentence-BERT + keselarasan 13 Genre)
    """
    pastikan_struktur_tabel(session)

    # ---------------------------------------------------------
    # A. REKOMENDASI BERDASARKAN FILM FAVORIT (user_favorite)
    # ---------------------------------------------------------
    favs = get_user_favorites(session, user_id)
    fav_indices = []
    for fav in favs:
        idx = title_to_idx.get(fav.movie_title.strip().lower())
        if idx is not None and idx not in fav_indices:
            fav_indices.append(idx)

    if fav_indices:
        fav_profile_vec = np.mean(cbf_item_vectors[fav_indices], axis=0, keepdims=True)
        fav_profile_vec = normalize(fav_profile_vec, norm="l2")

        fav_sims = cosine_similarity(fav_profile_vec, cbf_item_vectors)[0]
        # Kecualikan film yang sudah difavoritkan agar selalu muncul rekomendasi baru
        for ex_idx in fav_indices:
            fav_sims[ex_idx] = -1.0

        top_fav_idx = fav_sims.argsort()[-top_n:][::-1]
        fav_recs = [
            _format_movie_dict(
                int(idx),
                similarity_pct=max(0.0, min(float(fav_sims[idx]) * 100.0, 100.0)),
                rank=r,
            )
            for r, idx in enumerate(top_fav_idx, start=1)
        ]

        genre_counts = {}
        for idx in fav_indices:
            for g in movies_df.iloc[idx]["genre_list"]:
                genre_counts[g] = genre_counts.get(g, 0) + 1
        top_fav_genres = [
            g for g, _ in sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        ]

        by_favorites = {
            "has_data": True,
            "count_source": len(fav_indices),
            "top_genres": top_fav_genres,
            "source_info": (
                f"Dibentuk dari {len(fav_indices)} film favorit Anda"
                + (f" • Minat dominan: {', '.join(top_fav_genres)}" if top_fav_genres else "")
            ),
            "recommendations": fav_recs,
        }
    else:
        by_favorites = {
            "has_data": False,
            "count_source": 0,
            "top_genres": [],
            "source_info": "Anda belum menandai film favorit. Klik tombol ♥ Favorit di halaman Cari Film agar baris ini aktif.",
            "recommendations": [],
        }

    # ---------------------------------------------------------
    # B. REKOMENDASI BERDASARKAN RIWAYAT PENCARIAN OVERVIEW
    # ---------------------------------------------------------
    riwayat = get_all_rekomendasi(session, user_id=user_id, nama_user=nama_user)
    unique_overviews = []
    seen_q = set()
    for item in riwayat:
        q_clean = clean_text(item.get("input_overview", ""))
        if q_clean and q_clean not in seen_q:
            seen_q.add(q_clean)
            unique_overviews.append(q_clean)
        if len(unique_overviews) >= 5:
            break

    if unique_overviews:
        # Rata-rata vektor semantik Sentence-BERT dari maksimal 5 pencarian overview terbaru
        q_vecs = sbert_model.encode(unique_overviews, convert_to_numpy=True).astype(np.float32)
        q_vecs_norm = normalize(q_vecs, norm="l2")
        overview_profile_vec = normalize(
            np.mean(q_vecs_norm, axis=0, keepdims=True), norm="l2"
        )

        # Prediksi kecenderungan 13 genre asli dari profil pencarian overview
        proba_array = clf_model.predict_proba(overview_profile_vec)[0]
        sorted_g_idx = proba_array.argsort()[::-1]

        genre_query_vec = np.zeros((1, len(mlb_classes)), dtype=np.float32)
        for idx_g, p_val in enumerate(proba_array):
            if p_val >= max(0.40, genre_threshold - 0.10):
                genre_query_vec[0, idx_g] = float(p_val)
        if np.sum(genre_query_vec) == 0:
            genre_query_vec[0, int(sorted_g_idx[0])] = 1.0
        genre_query_vec = normalize(genre_query_vec, norm="l2")

        top_hist_genres = [
            mlb_classes[i] for i in sorted_g_idx[:3] if proba_array[i] >= 0.40
        ]
        if not top_hist_genres:
            top_hist_genres = [mlb_classes[int(sorted_g_idx[0])]]

        # Weighted Cosine Similarity (75% Semantik Overview + 25% Genre Asli)
        sim_ov = cosine_similarity(overview_profile_vec, overview_embeddings)[0]
        sim_gn = cosine_similarity(genre_query_vec, genre_matrix)[0]
        weighted_hist_sim = np.clip((0.75 * sim_ov) + (0.25 * sim_gn), 0.0, 1.0)

        top_hist_idx = weighted_hist_sim.argsort()[-top_n:][::-1]
        hist_recs = [
            _format_movie_dict(
                int(idx),
                similarity_pct=max(0.0, min(float(weighted_hist_sim[idx]) * 100.0, 100.0)),
                rank=r,
            )
            for r, idx in enumerate(top_hist_idx, start=1)
        ]

        by_history = {
            "has_data": True,
            "count_source": len(unique_overviews),
            "top_genres": top_hist_genres,
            "source_info": (
                f"Dibentuk dari {len(unique_overviews)} riwayat pencarian overview terbaru Anda"
                f" • Kecenderungan tema: {', '.join(top_hist_genres)}"
            ),
            "recommendations": hist_recs,
        }
    else:
        by_history = {
            "has_data": False,
            "count_source": 0,
            "top_genres": [],
            "source_info": "Anda belum pernah melakukan pencarian sinopsis di halaman Prediksi AI.",
            "recommendations": [],
        }

    return {
        "by_favorites": by_favorites,
        "by_history": by_history,
    }

# ==========================================
# FUNGSI REKOMENDASI CBF QUERY & ITEM-TO-ITEM
# ==========================================
def hitung_rekomendasi_cbf_query(input_overview: str, top_n: int = 10):
    """
    Content-Based Filtering berbasis input sinopsis:
    1. Ekstraksi fitur semantik overview (Sentence-BERT 384-Dim)
    2. Klasifikasi Multi-Label 13 Genre Asli IMDb (OneVsRest Logistic Regression)
    3. Pencocokan Weighted Cosine Similarity (75% Semantik Overview + 25% Keselarasan Genre)
    """
    cleaned_query = clean_text(input_overview)

    # 1. Vektor semantik overview
    query_vec = sbert_model.encode([cleaned_query], convert_to_numpy=True).astype(np.float32)
    query_norm = normalize(query_vec, norm="l2")

    # 2. Klasifikasi Multi-Label 13 Genre Asli
    proba_array = clf_model.predict_proba(query_norm)[0]
    sorted_genre_idx = proba_array.argsort()[::-1]

    predicted_genres = [
        (mlb_classes[i], float(proba_array[i] * 100.0))
        for i in sorted_genre_idx
        if proba_array[i] >= genre_threshold
    ][:3]

    # Fallback jika tidak ada genre yang melampaui threshold
    if not predicted_genres:
        top_i = int(sorted_genre_idx[0])
        predicted_genres = [(mlb_classes[top_i], float(proba_array[top_i] * 100.0))]

    label_genre = ", ".join([f"{g} ({p:.1f}%)" for g, p in predicted_genres])

    # Bangun vektor probabilitas genre untuk keselarasan konten CBF
    genre_query_vec = np.zeros((1, len(mlb_classes)), dtype=np.float32)
    for idx_g, p_val in enumerate(proba_array):
        if p_val >= max(0.40, genre_threshold - 0.10):
            genre_query_vec[0, idx_g] = float(p_val)
    if np.sum(genre_query_vec) == 0:
        genre_query_vec[0, int(sorted_genre_idx[0])] = 1.0
    genre_query_vec = normalize(genre_query_vec, norm="l2")

    # 3. Weighted Cosine Similarity (75% Semantik Cerita + 25% Genre Asli)
    sim_overview = cosine_similarity(query_norm, overview_embeddings)[0]
    sim_genre = cosine_similarity(genre_query_vec, genre_matrix)[0]
    weighted_sim = np.clip((0.75 * sim_overview) + (0.25 * sim_genre), 0.0, 1.0)

    top_indices = weighted_sim.argsort()[-top_n:][::-1]
    return label_genre, weighted_sim, top_indices


def get_similar_movies_by_title(movie_title: str, top_n: int = 10):
    """Item-to-Item Multi-Feature CBF (65% Overview + 25% Genre + 10% Kru)"""
    idx = title_to_idx.get(movie_title.strip().lower())
    if idx is None:
        return None, []

    target_movie = _format_movie_dict(idx)
    sims = cosine_similarity(cbf_item_vectors[idx : idx + 1], cbf_item_vectors)[0]
    sims[idx] = -1.0  # Kecualikan film itu sendiri

    top_indices = sims.argsort()[-top_n:][::-1]
    similar_list = [
        _format_movie_dict(
            int(cand_idx),
            similarity_pct=max(0.0, min(float(sims[cand_idx]) * 100.0, 100.0)),
            rank=r,
        )
        for r, cand_idx in enumerate(top_indices, start=1)
    ]
    return target_movie, similar_list


# ==========================================
# FUNGSI KATALOG PENCARIAN MULTI-FILTER (/cari)
# ==========================================
def search_catalog_movies(
    q: str = "",
    genre=None,
    year_range: str = "all",
    min_score: float = 0.0,
    sort_by: str = "title_asc",
    page: int = 1,
    per_page: int = 18,
):
    filtered = movies_df

    # 1. Filter kata kunci (judul, pemeran/kru, atau overview)
    q_clean = q.strip().lower()
    if q_clean:
        mask_q = (
            filtered["names"].str.lower().str.contains(q_clean, regex=False, na=False)
            | filtered["crew"].str.lower().str.contains(q_clean, regex=False, na=False)
            | filtered["overview"].str.lower().str.contains(q_clean, regex=False, na=False)
        )
        filtered = filtered[mask_q]

    # 2. Filter Multi-Genre (Logika AND: film harus memiliki SEMUA genre yang dipilih)
    selected_genres = []
    if isinstance(genre, list):
        selected_genres = [
            g.strip() for g in genre if g and g.strip().lower() != "all"
        ]
    elif isinstance(genre, str) and genre.strip() and genre.strip().lower() != "all":
        selected_genres = [genre.strip()]

    if selected_genres:
        selected_set = {g.lower() for g in selected_genres}
        filtered = filtered[
            filtered["genre_list"].apply(
                lambda gl: selected_set.issubset({str(x).strip().lower() for x in gl})
            )
        ]

    # 3. Filter rentang tahun rilis
    if year_range == "2020_plus":
        filtered = filtered[filtered["release_year"] >= 2020]
    elif year_range == "2010_2019":
        filtered = filtered[(filtered["release_year"] >= 2010) & (filtered["release_year"] <= 2019)]
    elif year_range == "2000_2009":
        filtered = filtered[(filtered["release_year"] >= 2000) & (filtered["release_year"] <= 2009)]
    elif year_range == "before_2000":
        filtered = filtered[(filtered["release_year"] > 0) & (filtered["release_year"] < 2000)]

    # 4. Filter minimal rating IMDb
    if min_score > 0:
        filtered = filtered[filtered["score"] >= float(min_score)]

    # 5. Pengurutan katalog (Default: Judul A - Z)
    if sort_by == "score_desc":
        filtered = filtered.sort_values(by=["score", "release_year"], ascending=[False, False])
    elif sort_by == "year_desc":
        filtered = filtered.sort_values(by=["release_year", "score"], ascending=[False, False])
    elif sort_by == "score_asc":
        filtered = filtered.sort_values(by=["score", "names"], ascending=[True, True])
    else:
        filtered = filtered.sort_values(
            by="names",
            ascending=True,
            key=lambda col: col.astype(str).str.lower(),
        )

    total_results = len(filtered)
    total_pages = max(1, math.ceil(total_results / per_page))
    current_page = max(1, min(int(page), total_pages))

    start = (current_page - 1) * per_page
    end = start + per_page
    page_df = filtered.iloc[start:end]

    movies_page = []
    for _, row in page_df.iterrows():
        movies_page.append({
            "names": str(row["names"]),
            "date_x": str(row["date_x"]),
            "release_year": int(row.get("release_year", 0)),
            "score": round(float(row["score"]), 1),
            "genre": str(row["genre"]),
            "main_genre": str(row.get("main_genre", row["genre"])),
            "overview": str(row["overview"]),
            "crew": str(row["crew"]),
            "orig_lang": str(row["orig_lang"]),
            "country": str(row["country"]),
        })

    return {
        "movies": movies_page,
        "total_results": total_results,
        "total_pages": total_pages,
        "current_page": current_page,
    }


# ==========================================
# FUNGSI CRUD RIWAYAT PREDIKSI PER AKUN
# ==========================================
def create_rekomendasi(
    session: Session,
    nama_user: str,
    input_overview: str,
    user_id: Optional[int] = None,
):
    pastikan_struktur_tabel(session)
    label_genre, weighted_sim, top_indices = hitung_rekomendasi_cbf_query(
        input_overview, top_n=10
    )

    rekomendasi_list = []
    for rank, idx in enumerate(top_indices, start=1):
        sim_percent = round(min(float(weighted_sim[idx]) * 100.0, 100.0), 1)
        rekomendasi_list.append(_format_movie_dict(int(idx), similarity_pct=sim_percent, rank=rank))

    rekomendasi_list.sort(key=lambda x: (x["similarity"], x["score"]), reverse=True)
    judul_ringkas = []
    for idx_rank, item_film in enumerate(rekomendasi_list, start=1):
        item_film["rank"] = idx_rank
        judul_ringkas.append(f"{idx_rank}. {item_film['names']} ({item_film['similarity']}%)")

    waktu_sekarang = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    data_baru = RiwayatRekomendasi(
        user_id=user_id,
        nama_user=nama_user,
        input_overview=input_overview,
        prediksi_genre=label_genre,
        top_judul_film=" | ".join(judul_ringkas[:3]),
        detail_rekomendasi=json.dumps(rekomendasi_list),
        waktu_pencarian=waktu_sekarang,
    )
    session.add(data_baru)
    session.commit()
    session.refresh(data_baru)
    return data_baru


def get_all_rekomendasi(
    session: Session,
    user_id: Optional[int] = None,
    nama_user: Optional[str] = None,
):
    pastikan_struktur_tabel(session)

    if user_id is not None and nama_user:
        statement = (
            select(RiwayatRekomendasi)
            .where(
                (RiwayatRekomendasi.user_id == user_id)
                | (
                    (RiwayatRekomendasi.user_id == None)
                    & (RiwayatRekomendasi.nama_user == nama_user)
                )
            )
            .order_by(RiwayatRekomendasi.id.desc())
        )
    elif user_id is not None:
        statement = (
            select(RiwayatRekomendasi)
            .where(RiwayatRekomendasi.user_id == user_id)
            .order_by(RiwayatRekomendasi.id.desc())
        )
    else:
        statement = select(RiwayatRekomendasi).order_by(RiwayatRekomendasi.id.desc())

    records = session.exec(statement).all()
    hasil = []
    for item in records:
        detail_list = json.loads(item.detail_rekomendasi)
        detail_list.sort(
            key=lambda x: (float(x.get("similarity", 0)), float(x.get("score", 0))),
            reverse=True,
        )
        for r_idx, d_item in enumerate(detail_list, start=1):
            d_item["rank"] = r_idx

        top_3_judul = " | ".join(
            [f"{d['rank']}. {d['names']} ({d['similarity']}%)" for d in detail_list[:3]]
        )

        hasil.append({
            "id": item.id,
            "user_id": item.user_id,
            "nama_user": item.nama_user,
            "input_overview": item.input_overview,
            "prediksi_genre": item.prediksi_genre,
            "top_judul_film": top_3_judul,
            "detail_list": detail_list,
            "waktu_pencarian": item.waktu_pencarian,
        })
    return hasil


def delete_rekomendasi(
    session: Session,
    item_id: int,
    user_id: Optional[int] = None,
    nama_user: Optional[str] = None,
):
    record = session.get(RiwayatRekomendasi, item_id)
    if not record:
        return False

    if user_id is not None:
        if record.user_id not in (None, user_id) and record.nama_user != nama_user:
            return False

    session.delete(record)
    session.commit()
    return True


def delete_all_rekomendasi(
    session: Session,
    user_id: Optional[int] = None,
    nama_user: Optional[str] = None,
):
    pastikan_struktur_tabel(session)

    if user_id is not None:
        records = session.exec(
            select(RiwayatRekomendasi).where(
                (RiwayatRekomendasi.user_id == user_id)
                | (
                    (RiwayatRekomendasi.user_id == None)
                    & (RiwayatRekomendasi.nama_user == nama_user)
                )
            )
        ).all()
        for r in records:
            session.delete(r)
        session.commit()

        sisa_data = session.exec(select(RiwayatRekomendasi)).first()
        if not sisa_data:
            session.exec(text("TRUNCATE TABLE riwayat_rekomendasi RESTART IDENTITY;"))
            session.commit()
    else:
        session.exec(text("TRUNCATE TABLE riwayat_rekomendasi RESTART IDENTITY;"))
        session.commit()

    return True
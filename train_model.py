import re
import warnings
import joblib
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.decomposition import TruncatedSVD
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    f1_score,
    hamming_loss,
    precision_score,
    recall_score,
)
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer, normalize

warnings.filterwarnings("ignore", category=ConvergenceWarning)

TARGET_GENRES = [
    "Action",
    "Adventure",
    "Animation",
    "Comedy",
    "Crime",
    "Drama",
    "Family",
    "Fantasy",
    "Horror",
    "Mystery",
    "Romance",
    "Science Fiction",
    "Thriller",
]


def clean_text(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s.,!?\']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_year(date_val: str) -> int:
    match = re.search(r"\b(19\d{2}|20\d{2})\b", str(date_val))
    return int(match.group(1)) if match else 0


def parse_genres(genre_str: str):
    parts = [g.strip() for g in str(genre_str).replace("\xa0", " ").split(",")]
    return [g for g in parts if g in TARGET_GENRES]


print("=== 1. MEMBACA & MEMBERSIHKAN DATASET IMDB ===")
df = pd.read_csv("imdb_movies.csv")
total_awal = len(df)

# Hapus baris kosong & film dengan rating IMDb 0.0 (belum rilis / belum ada rating)
df = df.dropna(subset=["names", "overview", "genre", "score"]).copy()
df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0.0)
df = df[df["score"] > 0].copy()

df["names"] = df["names"].astype(str).str.strip()
df["genre"] = df["genre"].astype(str).str.replace("\xa0", " ").str.strip()
df["clean_overview"] = df["overview"].apply(clean_text)
df["name_key"] = df["names"].str.lower().str.replace(r"[^a-z0-9]", "", regex=True)

# Hapus duplikasi berdasarkan judul & overview
df = (
    df.sort_values(by="score", ascending=False)
    .drop_duplicates(subset=["name_key", "clean_overview"], keep="first")
    .reset_index(drop=True)
)

# Ekstrak daftar genre asli (Multi-Label)
df["genre_list"] = df["genre"].apply(parse_genres)
df = df[df["genre_list"].map(len) > 0].reset_index(drop=True)

df["date_x"] = df["date_x"].fillna("-").astype(str).str.strip()
df["release_year"] = df["date_x"].apply(extract_year)
df["crew"] = df["crew"].fillna("Tidak ada data pemeran").astype(str).str.strip()
df["orig_lang"] = df["orig_lang"].fillna("-").astype(str).str.strip()
df["country"] = df["country"].fillna("-").astype(str).str.strip()
df["main_genre"] = df["genre_list"].apply(lambda x: x[0])

# Metadata teks (Genre + Pemeran/Kru) untuk fitur konten CBF
df["metadata_text"] = (
    df["genre"].str.replace(",", " ") + " " + df["crew"].str.replace(",", " ")
).apply(clean_text)

print(f"Total data awal                  : {total_awal} baris")
print(f"Total film bersih (Score > 0)    : {len(df)} film")
print(f"Jumlah kelas Genre Multi-Label   : {len(TARGET_GENRES)} genre asli IMDb\n")

print("=== 2. EKSTRAKSI FITUR KONTEN (SENTENCE-BERT + TF-IDF METADATA) ===")
sbert_model = SentenceTransformer("all-MiniLM-L6-v2")

print("-> Mengekstrak vektor semantik Overview (Sentence-BERT 384-Dim)...")
overview_embeddings = sbert_model.encode(
    df["clean_overview"].tolist(),
    show_progress_bar=True,
    convert_to_numpy=True,
).astype(np.float32)
overview_norm = normalize(overview_embeddings, norm="l2").astype(np.float32)

print("-> Mengekstrak vektor Multi-Label Genre (MultiLabelBinarizer)...")
mlb = MultiLabelBinarizer(classes=TARGET_GENRES)
Y_multilabel = mlb.fit_transform(df["genre_list"])
genre_norm = normalize(Y_multilabel.astype(np.float32), norm="l2").astype(np.float32)

print("-> Mengekstrak vektor Metadata Genre + Crew (TF-IDF + TruncatedSVD 64-Dim)...")
tfidf_meta = TfidfVectorizer(max_features=2000, stop_words="english")
meta_tfidf = tfidf_meta.fit_transform(df["metadata_text"])
n_svd = min(64, meta_tfidf.shape[1] - 1)
svd_meta = TruncatedSVD(n_components=n_svd, random_state=42)
meta_svd = svd_meta.fit_transform(meta_tfidf).astype(np.float32)
meta_norm = normalize(meta_svd, norm="l2").astype(np.float32)

# Vektor Terpadu Multi-Feature CBF:
# 65% Semantik Overview (SBERT) + 25% Genre Asli + 10% Metadata Kru/Pemeran
# Karena tiap komponen sudah L2-normalized, dot product antar vektor = weighted cosine similarity!
cbf_item_vectors = np.hstack([
    np.sqrt(0.65) * overview_norm,
    np.sqrt(0.25) * genre_norm,
    np.sqrt(0.10) * meta_norm,
]).astype(np.float32)
cbf_item_vectors = normalize(cbf_item_vectors, norm="l2").astype(np.float32)

print(f"Dimensi vektor terpadu CBF       : {cbf_item_vectors.shape[1]} dimensi per film\n")

print("=== 3. TRAINING KLASIFIKASI MULTI-LABEL GENRE (ONE-VS-REST LOGISTIC REGRESSION) ===")
indices = np.arange(len(df))
train_idx, test_idx = train_test_split(indices, test_size=0.2, random_state=42)

X_train = overview_norm[train_idx]
X_test = overview_norm[test_idx]
Y_train = Y_multilabel[train_idx]
Y_test = Y_multilabel[test_idx]

clf = OneVsRestClassifier(
    LogisticRegression(
        solver="lbfgs",
        C=3.0,
        max_iter=1000,
        class_weight="balanced",
        random_state=42,
    )
)
clf.fit(X_train, Y_train)

print("\n=== 4. EVALUASI MODEL KLASIFIKASI GENRE (TESTING SET 20%) ===")
Y_proba = clf.predict_proba(X_test)
# Threshold 0.55 menjaga keseimbangan Precision dan Recall pada class_weight='balanced'
GENRE_THRESHOLD = 0.55
Y_pred = (Y_proba >= GENRE_THRESHOLD).astype(int)

# Pastikan setiap film uji minimal memiliki 1 prediksi genre tertinggi
for i in range(len(Y_pred)):
    if Y_pred[i].sum() == 0:
        Y_pred[i, int(np.argmax(Y_proba[i]))] = 1

hamming_acc = (1.0 - hamming_loss(Y_test, Y_pred)) * 100
prec_weighted = precision_score(Y_test, Y_pred, average="weighted", zero_division=0) * 100
rec_weighted = recall_score(Y_test, Y_pred, average="weighted", zero_division=0) * 100
f1_weighted = f1_score(Y_test, Y_pred, average="weighted", zero_division=0) * 100
f1_micro = f1_score(Y_test, Y_pred, average="micro", zero_division=0) * 100
cls_report = classification_report(
    Y_test, Y_pred, target_names=mlb.classes_, zero_division=0
)

print(f"Hamming Accuracy (Ketepatan Label) : {hamming_acc:.2f}%")
print(f"Precision (Weighted)               : {prec_weighted:.2f}%")
print(f"Recall (Weighted)                  : {rec_weighted:.2f}%")
print(f"F1-Score (Weighted)                : {f1_weighted:.2f}%")
print(f"F1-Score (Micro)                   : {f1_micro:.2f}%")
print("\nClassification Report Multi-Label (13 Genre Asli IMDb):\n", cls_report)

print("=== 5. EVALUASI SISTEM REKOMENDASI CBF (PRECISION@10 & HIT RATE@10) ===")
# Menguji 300 film dari testing set terhadap seluruh katalog menggunakan CBF
eval_sample_idx = test_idx[: min(300, len(test_idx))]
precision_at_10_scores = []
hit_at_10_scores = []

sim_eval_matrix = cosine_similarity(cbf_item_vectors[eval_sample_idx], cbf_item_vectors)
for row_pos, movie_i in enumerate(eval_sample_idx):
    sims = sim_eval_matrix[row_pos].copy()
    sims[movie_i] = -1.0  # Kecualikan film itu sendiri
    top10_idx = sims.argsort()[-10:][::-1]

    true_genres = set(df.iloc[movie_i]["genre_list"])
    relevant_count = 0
    for cand_j in top10_idx:
        cand_genres = set(df.iloc[cand_j]["genre_list"])
        if len(true_genres & cand_genres) > 0:
            relevant_count += 1

    precision_at_10_scores.append(relevant_count / 10.0)
    hit_at_10_scores.append(1.0 if relevant_count > 0 else 0.0)

mean_p10 = float(np.mean(precision_at_10_scores) * 100)
hit_rate_10 = float(np.mean(hit_at_10_scores) * 100)
print(f"Precision@10 (Relevansi Top-10 CBF): {mean_p10:.2f}%")
print(f"Hit Rate@10                        : {hit_rate_10:.2f}%\n")

print("\n=== MENYIMPAN BUNDLE MODEL KE ai_movie_model.pkl ===")
movies_metadata = df[
    [
        "names",
        "date_x",
        "release_year",
        "score",
        "genre",
        "main_genre",
        "genre_list",
        "overview",
        "crew",
        "orig_lang",
        "country",
    ]
].copy()

model_bundle = {
    "classifier": clf,
    "mlb_classes": list(mlb.classes_),
    "genre_threshold": GENRE_THRESHOLD,
    "overview_embeddings": overview_norm,
    "genre_matrix": genre_norm,
    "cbf_item_vectors": cbf_item_vectors,
    "tfidf_meta": tfidf_meta,
    "svd_meta": svd_meta,
    "movies_df": movies_metadata,
    "metrics": {
        "total_raw": total_awal,
        "total_clean": len(df),
        "train_size": len(train_idx),
        "test_size": len(test_idx),
        "num_genres": len(mlb.classes_),
        "genres_list": list(mlb.classes_),
        "accuracy": round(hamming_acc, 2),
        "precision": round(prec_weighted, 2),
        "recall": round(rec_weighted, 2),
        "f1_score": round(f1_weighted, 2),
        "micro_f1": round(f1_micro, 2),
        "precision_at_10": round(mean_p10, 2),
        "hit_rate_10": round(hit_rate_10, 2),
        "classification_report": cls_report,
    },
}

joblib.dump(model_bundle, "ai_movie_model.pkl", compress=3)
print("Berhasil menyimpan model terpadu ke: ai_movie_model.pkl")
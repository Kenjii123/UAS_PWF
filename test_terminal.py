import re
import joblib
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

print("=" * 75)
print("   MEMUAT MODEL AI CINEMIND (MURNI 3 ALGORITMA AWAL)")
print("   1. Sentence-BERT (all-MiniLM-L6-v2)")
print("   2. Logistic Regression Classifier")
print("   3. Cosine Similarity Matching")
print("=" * 75)

# 1. Load bundle model dari file .pkl
model_bundle = joblib.load("ai_movie_model.pkl")
clf_model = model_bundle["classifier"]
movie_embeddings = model_bundle["embeddings"]
movies_df = model_bundle["movies_df"]
metrics = model_bundle["metrics"]

sbert_model = SentenceTransformer("all-MiniLM-L6-v2")


def clean_text(text: str) -> str:
    """Preprocessing standar (identik dengan train_model.py)"""
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s.,!?\']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tampilkan_metrik():
    print("\n" + "=" * 75)
    print("   RINGKASAN EVALUASI MODEL & DATASET (HASIL RE-TRAINING)")
    print("=" * 75)
    print(f"Total Baris Awal CSV     : {metrics['total_raw']} baris")
    print(f"Total Film Unik Bersih   : {metrics['total_clean']} film")
    print(f"Sampel Klasifikasi Genre : {metrics['train_size']} Train / {metrics['test_size']} Test")
    print(f"Jumlah Kelas Macro-Genre : {metrics['num_genres']} Kategori ({', '.join(metrics['genres_list'])})")
    print("-" * 75)
    print(f"Accuracy Score           : {metrics['accuracy']}%")
    print(f"Precision (Weighted)     : {metrics['precision']}%")
    print(f"Recall (Weighted)        : {metrics['recall']}%")
    print(f"F1-Score (Weighted)      : {metrics['f1_score']}%")
    print("-" * 75)
    print("Classification Report:\n")
    print(metrics["classification_report"])
    print("=" * 75)


def jalankan_prediksi(input_overview: str, top_n: int = 10):
    print("\n" + "=" * 75)
    print("   HASIL ANALISIS & REKOMENDASI FILM (200 EPOCH + GENRE-GUIDED)")
    print("=" * 75)
    print(f'Input Overview :\n"{input_overview}"')

    cleaned_query = clean_text(input_overview)
    query_vec = sbert_model.encode([cleaned_query], convert_to_numpy=True)

    proba_array = clf_model.predict_proba(query_vec)[0]
    classes_list = list(clf_model.classes_)
    pred_idx = int(np.argmax(proba_array))
    pred_genre = classes_list[pred_idx]
    pred_prob = float(proba_array[pred_idx] * 100)

    print("-" * 75)
    print(f"Prediksi Genre (Logistic Regression) : {pred_genre} (Confidence: {pred_prob:.1f}%)")
    print("-" * 75)

    genre_prob_map = {classes_list[i]: float(proba_array[i]) for i in range(len(classes_list))}
    movie_genre_weights = movies_df["main_genre"].map(genre_prob_map).fillna(0.25).to_numpy()

    context_embeddings = model_bundle.get("context_embeddings", movie_embeddings)
    sim_overview = cosine_similarity(query_vec, movie_embeddings)[0]
    sim_context = cosine_similarity(query_vec, context_embeddings)[0]
    base_sim = np.maximum(sim_overview, sim_context)

    combined_scores = np.where(
        sim_overview >= 0.98,
        sim_overview,
        (0.85 * base_sim) + (0.15 * movie_genre_weights * base_sim),
    )
    top_indices = combined_scores.argsort()[-top_n:][::-1]

    print(f"TOP {top_n} REKOMENDASI FILM (COSINE SIMILARITY + GENRE ALIGNMENT):\n")
    for rank, idx in enumerate(top_indices, start=1):
        row = movies_df.iloc[idx]
        sim_percent = round(min(float(base_sim[idx]) * 100, 100.0), 1)
        overview_singkat = (
            row["overview"][:130] + "..." if len(str(row["overview"])) > 130 else row["overview"]
        )

        print(f"#{rank:<2} | {row['names']} ({row['date_x']})")
        print(f"    Kemiripan : {sim_percent}%  |  Skor IMDb: {row['score']}/100  |  Genre: {row['genre']}")
        print(f"    Overview  : {overview_singkat}")
        print("-" * 75)

# Daftar skenario uji cepat untuk demonstrasi ke dosen
DEMO_CASES = {
    "1": (
        "Uji Exact Match 100% (Overview Asli Film Frozen di Dataset)",
        "Young princess Anna of Arendelle dreams about finding true love at her sister Elsa’s coronation. Fate takes her on a dangerous journey in an attempt to end the eternal winter that has fallen over the kingdom. She's accompanied by ice delivery man Kristoff, his reindeer Sven, and snowman Olaf. On an adventure where she will find out what friendship, courage, family, and true love really means.",
    ),
    "2": (
        "Uji Overview Singkat #1 (Putri dengan kekuatan es & musim dingin abadi)",
        "An animated family adventure about a young princess and her sister whose magical ice powers trap their kingdom in an eternal winter.",
    ),
    "3": (
        "Uji Overview Singkat #2 (Dokter bedah belajar sihir & portal dimensi)",
        "After a career-ending car crash, a brilliant neurosurgeon travels to a mysterious temple to heal his hands and learns the mystic arts of magic and alternate dimensions.",
    ),
    "4": (
        "Uji Overview Singkat #3 (Astronot menjelajahi lubang cacing di luar angkasa)",
        "A team of astronauts and space explorers travel through a wormhole in space to find a new habitable planet and save humanity from extinction.",
    ),
}


def main():
    tampilkan_metrik()

    while True:
        print("\nMENU PENGUJIAN TERMINAL (PRESENTASI PROGRES):")
        print("  [1] Demo 1: Uji Overview Sama Persis Dataset (Bukti Kemiripan 100%)")
        print("  [2] Demo 2: Uji Kalimat Singkat - Princess Ice Powers (Target: Frozen)")
        print("  [3] Demo 3: Uji Kalimat Singkat - Surgeon & Mystic Arts (Target: Doctor Strange)")
        print("  [4] Demo 4: Uji Kalimat Singkat - Wormhole & Space (Target: Interstellar)")
        print("  [5] Input Overview Bebas (Ketik / Paste Sendiri dalam Bahasa Inggris)")
        print("  [6] Tampilkan Ulang Metrik Evaluasi & Classification Report")
        print("  [0] Keluar dari Program")

        pilihan = input("\nPilih menu [0-6]: ").strip()

        if pilihan in DEMO_CASES:
            judul_demo, teks_demo = DEMO_CASES[pilihan]
            print(f"\n>>> Menjalankan: {judul_demo}")
            jalankan_prediksi(teks_demo, top_n=10)
        elif pilihan == "5":
            teks_manual = input("\nMasukkan overview film (Bahasa Inggris): ").strip()
            if teks_manual:
                jalankan_prediksi(teks_manual, top_n=10)
            else:
                print("[!] Input overview tidak boleh kosong.")
        elif pilihan == "6":
            tampilkan_metrik()
        elif pilihan == "0":
            print("\nPengujian selesai. Terima kasih!")
            break
        else:
            print("[!] Pilihan tidak valid, silakan masukkan angka 0 sampai 6.")


if __name__ == "__main__":
    main()
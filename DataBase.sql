CREATE TABLE IF NOT EXISTS riwayat_rekomendasi (
    id SERIAL PRIMARY KEY,
    nama_user VARCHAR(100) NOT NULL,
    input_overview TEXT NOT NULL,
    prediksi_genre VARCHAR(100) NOT NULL,
    top_judul_film VARCHAR(255) NOT NULL,
    detail_rekomendasi TEXT NOT NULL,
    waktu_pencarian VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS user_account (
    id SERIAL PRIMARY KEY,
    nama_lengkap VARCHAR(100) NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    waktu_daftar VARCHAR(50) NOT NULL
);

ALTER TABLE riwayat_rekomendasi
ADD COLUMN IF NOT EXISTS user_id INTEGER;

CREATE TABLE IF NOT EXISTS user_favorite (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    movie_title VARCHAR NOT NULL,
    movie_date VARCHAR DEFAULT '-',
    movie_genre VARCHAR DEFAULT '-',
    movie_score DOUBLE PRECISION DEFAULT 0.0,
    waktu_favorit VARCHAR NOT NULL
);
import json
import os
import threading
import urllib.parse
import urllib.request
from typing import Optional

# Tempelkan TMDB API Key (atau API Read Access Token) Anda di sini
TMDB_API_KEY = os.getenv("edf2d9f91032f5b4738140bd5a8cf794", "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJlZGYyZDlmOTEwMzJmNWI0NzM4MTQwYmQ1YThjZjc5NCIsIm5iZiI6MTc5NTUxMjMwMS44MzksInN1YiI6IjZiMDU1N2VkODM2YTM2ZDRjMzliYTg2MiIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.-oLbTJoFwu_eYRTCZvBUHkspdGr3EGjd0koACU35uKM").strip()

CACHE_FILE = "poster_cache.json"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w342"

_cache_lock = threading.Lock()
_poster_cache: dict[str, str] = {}


def _load_cache():
    global _poster_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _poster_cache = data
        except Exception:
            _poster_cache = {}


def _save_cache():
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_poster_cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


_load_cache()


def _query_tmdb(title: str, year: int = 0) -> Optional[str]:
    if not TMDB_API_KEY or TMDB_API_KEY == "PASTE_API_KEY_TMDB_ANDA_DI_SINI":
        return None

    params = {
        "query": title,
        "include_adult": "false",
        "language": "en-US",
        "page": 1,
    }
    if year and year > 1800:
        params["year"] = year

    headers = {
        "Accept": "application/json",
        "User-Agent": "CineMindAI/1.0",
    }

    # Otomatis mendukung baik API Read Access Token (v4, diawali 'eyJ') maupun API Key (v3)
    if TMDB_API_KEY.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {TMDB_API_KEY}"
    else:
        params["api_key"] = TMDB_API_KEY

    url = f"https://api.themoviedb.org/3/search/movie?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=6) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    results = payload.get("results") or []
    for item in results:
        poster_path = item.get("poster_path")
        if poster_path:
            return f"{TMDB_IMAGE_BASE}{poster_path}"
    return ""


def get_movie_poster_url(title: str, year: int = 0) -> Optional[str]:
    title_clean = title.strip()
    if not title_clean:
        return None

    cache_key = f"{title_clean.lower()}|{int(year or 0)}"

    # 1. Cek cache lokal terlebih dahulu (instan tanpa panggil API)
    with _cache_lock:
        if cache_key in _poster_cache:
            cached_val = _poster_cache[cache_key]
            return cached_val if cached_val else None

    if not TMDB_API_KEY or TMDB_API_KEY == "PASTE_API_KEY_TMDB_ANDA_DI_SINI":
        return None

    # 2. Jika belum ada di cache, cari ke TMDB (Judul + Tahun, fallback Judul saja)
    try:
        poster_url = _query_tmdb(title_clean, year=year)
        if poster_url == "" and year and year > 1800:
            poster_url = _query_tmdb(title_clean, year=0)

        if poster_url is not None:
            with _cache_lock:
                _poster_cache[cache_key] = poster_url
                _save_cache()
            return poster_url if poster_url else None
    except Exception:
        # Jika koneksi gagal, jangan simpan ke cache agar bisa dicoba lagi nanti
        return None

    return None
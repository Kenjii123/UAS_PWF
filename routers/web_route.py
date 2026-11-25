from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
from config import get_session
from services import rekomendasi_service
from services import poster_service, rekomendasi_service

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def get_current_user(request: Request, session: Session):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return rekomendasi_service.get_user_by_id(session, int(user_id))


# 1. HALAMAN HOME (BERSIH TANPA REKOMENDASI PERSONAL)
@router.get("/", response_class=HTMLResponse)
def halaman_home(request: Request, session: Session = Depends(get_session)):
    current_user = get_current_user(request, session)
    metrics = rekomendasi_service.get_ai_info()

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "active_page": "home",
            "metrics": metrics,
            "current_user": current_user,
        },
    )

# 1B. HALAMAN KHUSUS REKOMENDASI PERSONAL CBF (/untuk-anda)
@router.get("/untuk-anda", response_class=HTMLResponse)
def halaman_untuk_anda(request: Request, session: Session = Depends(get_session)):
    current_user = get_current_user(request, session)
    if not current_user:
        return RedirectResponse(url="/?login_required=1", status_code=303)

    split_recs = rekomendasi_service.get_split_personalized_recommendations(
        session,
        user_id=current_user.id,
        nama_user=current_user.nama_lengkap,
        top_n=15,
    )
    favorite_titles = rekomendasi_service.get_user_favorite_titles(
        session, current_user.id
    )

    return templates.TemplateResponse(
        request=request,
        name="untuk_anda.html",
        context={
            "active_page": "untuk_anda",
            "current_user": current_user,
            "by_favorites": split_recs["by_favorites"],
            "by_history": split_recs["by_history"],
            "favorite_titles": favorite_titles,
        },
    )

# 2. HALAMAN CARI & FILTER FILM (/cari)
@router.get("/cari", response_class=HTMLResponse)
def halaman_cari(
    request: Request,
    q: str = Query(""),
    genre: list[str] = Query(default=[]),
    year_range: str = Query("all"),
    min_score: float = Query(0.0),
    sort_by: str = Query("title_asc"),
    page: int = Query(1, ge=1),
    similar_to: str = Query(""),
    session: Session = Depends(get_session),
):
    current_user = get_current_user(request, session)
    selected_genres = [
        g.strip() for g in genre if g and g.strip().lower() != "all"
    ]

    catalog_data = rekomendasi_service.search_catalog_movies(
        q=q,
        genre=selected_genres,
        year_range=year_range,
        min_score=min_score,
        sort_by=sort_by,
        page=page,
        per_page=18,
    )

    all_genres = list(rekomendasi_service.mlb_classes)

    similar_target, similar_movies = (None, [])
    if similar_to.strip():
        similar_target, similar_movies = rekomendasi_service.get_similar_movies_by_title(
            similar_to.strip(), top_n=10
        )

    favorite_titles = (
        rekomendasi_service.get_user_favorite_titles(session, current_user.id)
        if current_user
        else set()
    )

    return templates.TemplateResponse(
        request=request,
        name="cari.html",
        context={
            "active_page": "cari",
            "current_user": current_user,
            "movies": catalog_data["movies"],
            "total_results": catalog_data["total_results"],
            "current_page": catalog_data["current_page"],
            "total_pages": catalog_data["total_pages"],
            "all_genres": all_genres,
            "filters": {
                "q": q,
                "genres": selected_genres,
                "year_range": year_range,
                "min_score": min_score,
                "sort_by": sort_by,
            },
            "similar_target": similar_target,
            "similar_movies": similar_movies,
            "favorite_titles": favorite_titles,
        },
    )

# 2B. ENDPOINT API JSON UNTUK POP-UP FILM SERUPA (ITEM-TO-ITEM CBF)
@router.get("/api/serupa")
def api_film_serupa(
    request: Request,
    title: str = Query(...),
    session: Session = Depends(get_session),
):
    target_movie, similar_movies = rekomendasi_service.get_similar_movies_by_title(
        title.strip(), top_n=10
    )
    if not target_movie:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "message": "Film tidak ditemukan di katalog."},
        )

    current_user = get_current_user(request, session)
    fav_titles = []
    if current_user:
        fav_titles = list(
            rekomendasi_service.get_user_favorite_titles(session, current_user.id)
        )

    return JSONResponse(
        content={
            "ok": True,
            "target": target_movie,
            "similar": similar_movies,
            "favorites": fav_titles,
        }
    )

# 2C. ENDPOINT API LAZY-LOAD POSTER FILM (TMDB + LOCAL JSON CACHE)
@router.get("/api/poster")
def api_poster_film(
    title: str = Query(...),
    year: int = Query(0),
):
    poster_url = poster_service.get_movie_poster_url(title=title, year=year)
    return JSONResponse(
        content={
            "ok": bool(poster_url),
            "poster_url": poster_url,
        }
    )

# 3. ENDPOINT FAVORIT (MEMBANGUN USER PROFILE VECTOR PER AKUN)
@router.post("/favorit/toggle")
def toggle_favorit(
    request: Request,
    movie_title: str = Form(...),
    next_url: str = Form("/cari"),
    session: Session = Depends(get_session),
):
    current_user = get_current_user(request, session)
    is_ajax = request.headers.get("X-Requested-With") == "fetch"

    if not current_user:
        if is_ajax:
            return JSONResponse(
                status_code=401,
                content={"ok": False, "login_required": True, "message": "Silakan login terlebih dahulu."},
            )
        return RedirectResponse(url="/?login_required=1", status_code=303)

    is_favorited, msg = rekomendasi_service.toggle_user_favorite(
        session, current_user.id, movie_title
    )

    if is_ajax:
        return JSONResponse(
            content={"ok": True, "favorited": is_favorited, "message": msg}
        )

    target = next_url if next_url.startswith("/") else "/cari"
    return RedirectResponse(url=target, status_code=303)


@router.post("/favorit/delete/{fav_id}")
def hapus_favorit(
    request: Request,
    fav_id: int,
    session: Session = Depends(get_session),
):
    current_user = get_current_user(request, session)
    if not current_user:
        return RedirectResponse(url="/?login_required=1", status_code=303)

    rekomendasi_service.delete_favorite_by_id(session, current_user.id, fav_id)
    return RedirectResponse(url="/profile", status_code=303)


# 4. FITUR AKUN: REGISTER, LOGIN, LUPA PASSWORD, LOGOUT, & PROFILE
@router.post("/auth/register", response_class=HTMLResponse)
def auth_register(
    request: Request,
    nama_lengkap: str = Form(...),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    user, err = rekomendasi_service.register_user(session, nama_lengkap, username, email, password)
    if err:
        metrics = rekomendasi_service.get_ai_info()
        return templates.TemplateResponse(
            request=request,
            name="home.html",
            context={
                "active_page": "home",
                "metrics": metrics,
                "current_user": None,
                "personalized_data": None,
                "favorite_titles": set(),
                "auth_error": err,
                "auth_tab": "register",
            },
        )
    request.session["user_id"] = user.id
    return RedirectResponse(url="/prediksi", status_code=303)


@router.post("/auth/login", response_class=HTMLResponse)
def auth_login(
    request: Request,
    identifier: str = Form(...),
    password: str = Form(...),
    next_url: str = Form("/prediksi"),
    session: Session = Depends(get_session),
):
    user = rekomendasi_service.authenticate_user(session, identifier, password)
    if not user:
        metrics = rekomendasi_service.get_ai_info()
        return templates.TemplateResponse(
            request=request,
            name="home.html",
            context={
                "active_page": "home",
                "metrics": metrics,
                "current_user": None,
                "personalized_data": None,
                "favorite_titles": set(),
                "auth_error": "Username/Email atau Password salah. Silakan coba lagi.",
                "auth_tab": "login",
            },
        )
    request.session["user_id"] = user.id
    target = next_url if next_url.startswith("/") else "/prediksi"
    return RedirectResponse(url=target, status_code=303)


@router.post("/auth/forgot-password", response_class=HTMLResponse)
def auth_forgot_password(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    new_password: str = Form(...),
    session: Session = Depends(get_session),
):
    ok, msg = rekomendasi_service.reset_password_user(session, username, email, new_password)
    metrics = rekomendasi_service.get_ai_info()
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "active_page": "home",
            "metrics": metrics,
            "current_user": None,
            "personalized_data": None,
            "favorite_titles": set(),
            "auth_error": None if ok else msg,
            "auth_success": msg if ok else None,
            "auth_tab": "login" if ok else "forgot",
        },
    )


@router.get("/auth/logout")
def auth_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@router.get("/profile", response_class=HTMLResponse)
def halaman_profile(request: Request, session: Session = Depends(get_session)):
    current_user = get_current_user(request, session)
    if not current_user:
        return RedirectResponse(url="/?login_required=1", status_code=303)

    favorites = rekomendasi_service.get_user_favorites(session, current_user.id)
    personalized_data = rekomendasi_service.get_personalized_recommendations(
        session,
        user_id=current_user.id,
        nama_user=current_user.nama_lengkap,
        top_n=6,
    )

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "active_page": "profile",
            "current_user": current_user,
            "favorites": favorites,
            "personalized_data": personalized_data,
        },
    )


@router.post("/profile/update", response_class=HTMLResponse)
def update_profile(
    request: Request,
    nama_lengkap: str = Form(...),
    email: str = Form(...),
    new_password: str = Form(""),
    session: Session = Depends(get_session),
):
    current_user = get_current_user(request, session)
    if not current_user:
        return RedirectResponse(url="/?login_required=1", status_code=303)

    updated_user, msg = rekomendasi_service.update_user_profile(
        session, current_user.id, nama_lengkap, email, new_password
    )
    favorites = rekomendasi_service.get_user_favorites(session, current_user.id)
    personalized_data = rekomendasi_service.get_personalized_recommendations(
        session,
        user_id=current_user.id,
        nama_user=(updated_user or current_user).nama_lengkap,
        top_n=6,
    )

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "active_page": "profile",
            "current_user": updated_user or current_user,
            "favorites": favorites,
            "personalized_data": personalized_data,
            "profile_msg": msg,
            "profile_ok": updated_user is not None,
        },
    )


# 5. HALAMAN PREDIKSI (TERPROTEKSI LOGIN & RIWAYAT KHUSUS PER AKUN)
@router.get("/prediksi", response_class=HTMLResponse)
def halaman_prediksi(request: Request, session: Session = Depends(get_session)):
    current_user = get_current_user(request, session)
    if not current_user:
        return RedirectResponse(url="/?login_required=1", status_code=303)

    riwayat = rekomendasi_service.get_all_rekomendasi(
        session, user_id=current_user.id, nama_user=current_user.nama_lengkap
    )
    hasil_terbaru = riwayat[0] if len(riwayat) > 0 else None
    favorite_titles = rekomendasi_service.get_user_favorite_titles(
        session, current_user.id
    )
    personalized_data = rekomendasi_service.get_personalized_recommendations(
        session,
        user_id=current_user.id,
        nama_user=current_user.nama_lengkap,
        top_n=6,
    )

    return templates.TemplateResponse(
        request=request,
        name="prediksi.html",
        context={
            "active_page": "prediksi",
            "riwayat": riwayat,
            "hasil_terbaru": hasil_terbaru,
            "current_user": current_user,
            "favorite_titles": favorite_titles,
            "personalized_data": personalized_data,
        },
    )


@router.post("/prediksi/create")
def buat_prediksi(
    request: Request,
    input_overview: str = Form(...),
    session: Session = Depends(get_session),
):
    current_user = get_current_user(request, session)
    if not current_user:
        return RedirectResponse(url="/?login_required=1", status_code=303)

    rekomendasi_service.create_rekomendasi(
        session=session,
        nama_user=current_user.nama_lengkap,
        input_overview=input_overview,
        user_id=current_user.id,
    )
    return RedirectResponse(url="/prediksi", status_code=303)


@router.post("/prediksi/delete/{item_id}")
def hapus_prediksi(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
):
    current_user = get_current_user(request, session)
    if not current_user:
        return RedirectResponse(url="/?login_required=1", status_code=303)

    rekomendasi_service.delete_rekomendasi(
        session, item_id, user_id=current_user.id, nama_user=current_user.nama_lengkap
    )
    return RedirectResponse(url="/prediksi", status_code=303)


@router.post("/prediksi/delete-all")
def hapus_semua_prediksi(
    request: Request,
    session: Session = Depends(get_session),
):
    current_user = get_current_user(request, session)
    if not current_user:
        return RedirectResponse(url="/?login_required=1", status_code=303)

    rekomendasi_service.delete_all_rekomendasi(
        session, user_id=current_user.id, nama_user=current_user.nama_lengkap
    )
    return RedirectResponse(url="/prediksi", status_code=303)


# 6. HALAMAN CONTACT US
@router.get("/contact", response_class=HTMLResponse)
def halaman_contact(request: Request, session: Session = Depends(get_session)):
    current_user = get_current_user(request, session)
    return templates.TemplateResponse(
        request=request,
        name="contact.html",
        context={
            "active_page": "contact",
            "current_user": current_user,
        },
    )
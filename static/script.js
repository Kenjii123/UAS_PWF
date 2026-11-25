// 1. Mengisi contoh overview otomatis ke dalam textarea
function isiContoh(teks) {
    const inputOverview = document.getElementById('input_overview');
    if (inputOverview) {
        inputOverview.value = teks;
        inputOverview.focus();
    }
}

// 2. Menampilkan atau menyembunyikan detail film/tahap AI
function toggleDetail(idElement) {
    const el = document.getElementById(idElement);
    if (el) {
        el.style.display = (el.style.display === 'none' || el.style.display === '') ? 'block' : 'none';
    }
}

// 3. Menampilkan notifikasi toast singkat
let toastTimer = null;
function tampilkanToast(pesan, isError = false) {
    const toast = document.getElementById('toastNotif');
    if (!toast) return;
    toast.textContent = pesan;
    toast.style.borderColor = isError ? '#ef4444' : '#46d369';
    toast.classList.add('show');

    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// 4. Toggle Favorit Tanpa Reload (Membangun User Profile Vector CBF)
async function toggleFavoritAjax(btn) {
    const isLoggedIn = document.body.getAttribute('data-logged-in') === 'true';
    if (!isLoggedIn) {
        bukaModalAuth('login', true);
        return;
    }

    const movieTitle = btn.getAttribute('data-title');
    if (!movieTitle) return;

    const formData = new FormData();
    formData.append('movie_title', movieTitle);

    try {
        const res = await fetch('/favorit/toggle', {
            method: 'POST',
            headers: { 'X-Requested-With': 'fetch' },
            body: formData
        });

        const data = await res.json();
        if (res.status === 401 || data.login_required) {
            bukaModalAuth('login', true);
            return;
        }

        if (data.ok) {
            // Sinkronkan semua tombol favorit dengan judul film yang sama di halaman
            document.querySelectorAll('.btn-fav').forEach(el => {
                if (el.getAttribute('data-title') === movieTitle) {
                    if (data.favorited) {
                        el.classList.add('is-favorited');
                        el.innerHTML = '&#9829; Difavoritkan';
                    } else {
                        el.classList.remove('is-favorited');
                        el.innerHTML = '&#9825; Favorit';
                    }
                }
            });
            tampilkanToast(data.message);
        }
    } catch (err) {
        tampilkanToast('Gagal memperbarui favorit. Coba muat ulang halaman.', true);
    }
}

// 5. Mengurutkan Hasil Rekomendasi Berdasarkan Kemiripan CBF / Rating IMDb
function urutkanRekomendasi() {
    const container = document.getElementById('daftarRekomendasiContainer');
    const sortSelect = document.getElementById('sortRekomendasi');
    if (!container || !sortSelect) return;

    const sortBy = sortSelect.value;
    const cards = Array.from(container.querySelectorAll('.item-rekomendasi'));

    cards.sort((a, b) => {
        const simA = parseFloat(a.getAttribute('data-similarity')) || 0;
        const simB = parseFloat(b.getAttribute('data-similarity')) || 0;
        const scoreA = parseFloat(a.getAttribute('data-score')) || 0;
        const scoreB = parseFloat(b.getAttribute('data-score')) || 0;

        if (sortBy === 'score_desc') {
            return (scoreB - scoreA) || (simB - simA);
        } else if (sortBy === 'score_asc') {
            return (scoreA - scoreB) || (simB - simA);
        } else {
            return (simB - simA) || (scoreB - scoreA);
        }
    });

    cards.forEach((card, index) => {
        const badgePeringkat = card.querySelector('.badge-peringkat');
        if (badgePeringkat) {
            badgePeringkat.textContent = '#' + (index + 1);
        }
        container.appendChild(card);
    });
}

// 6. Mengganti tab di dalam Pop-up Modal (Login / Daftar Akun / Lupa Password)
function gantiTabAuth(tabName) {
    const panels = {
        login: document.getElementById('panelLogin'),
        register: document.getElementById('panelRegister'),
        forgot: document.getElementById('panelForgot')
    };
    const buttons = {
        login: document.getElementById('tabBtnLogin'),
        register: document.getElementById('tabBtnRegister'),
        forgot: document.getElementById('tabBtnForgot')
    };

    Object.keys(panels).forEach(key => {
        if (panels[key]) panels[key].style.display = (key === tabName) ? 'block' : 'none';
        if (buttons[key]) {
            if (key === tabName) {
                buttons[key].classList.add('active');
            } else {
                buttons[key].classList.remove('active');
            }
        }
    });
}

// 7. Membuka Pop-up Modal Autentikasi
function bukaModalAuth(tabName = 'login', showNotice = false) {
    const overlay = document.getElementById('authModalOverlay');
    const notice = document.getElementById('modalNoticeBanner');
    if (overlay) {
        overlay.classList.add('show');
        gantiTabAuth(tabName);
        if (notice) {
            notice.style.display = showNotice ? 'block' : 'none';
        }
    }
}

// 8. Ketika user memilih tombol "Nanti Saja"
function pilihNantiSaja() {
    sessionStorage.setItem('skip_auth_popup', 'true');
    const overlay = document.getElementById('authModalOverlay');
    if (overlay) {
        overlay.classList.remove('show');
    }
}

// 9. Mencegat akses ke halaman Prediksi jika user belum login
function cekAksesPrediksi(event) {
    const isLoggedIn = document.body.getAttribute('data-logged-in') === 'true';
    if (!isLoggedIn) {
        if (event) {
            event.preventDefault();
            const targetHref = event.currentTarget ? event.currentTarget.getAttribute('href') : '/prediksi';
            const nextInput = document.getElementById('loginNextUrl');
            if (nextInput && targetHref) {
                nextInput.value = targetHref;
            }
        }
        bukaModalAuth('login', true);
        return false;
    }
    return true;
}

// 10. Animasi Slider Poster Film Populer di Hero Section
let currentPosterIndex = 0;
let posterInterval = null;

function pilihPosterSlide(index) {
    const slides = document.querySelectorAll('.poster-slide');
    const dots = document.querySelectorAll('.poster-dot');
    const backdrop = document.getElementById('heroDynamicBackdrop');

    if (slides.length === 0) return;

    currentPosterIndex = index % slides.length;

    slides.forEach((slide, i) => {
        if (i === currentPosterIndex) {
            slide.classList.add('active');
            const bgUrl = slide.getAttribute('data-bg');
            if (backdrop && bgUrl) {
                backdrop.style.backgroundImage = `url('${bgUrl}')`;
            }
        } else {
            slide.classList.remove('active');
        }
    });

    dots.forEach((dot, i) => {
        if (i === currentPosterIndex) {
            dot.classList.add('active');
        } else {
            dot.classList.remove('active');
        }
    });
}

function mulaiAnimasiPoster() {
    const slides = document.querySelectorAll('.poster-slide');
    if (slides.length > 1) {
        posterInterval = setInterval(() => {
            pilihPosterSlide(currentPosterIndex + 1);
        }, 3500);
    }
}

document.addEventListener('DOMContentLoaded', function () {
    mulaiAnimasiPoster();

    // Mengatur lebar bar persentase kemiripan (bebas warning CSS VS Code)
    document.querySelectorAll('.sim-progress-bar').forEach(bar => {
        const w = bar.getAttribute('data-width') || 0;
        bar.style.width = w + '%';
    });

    const isLoggedIn = document.body.getAttribute('data-logged-in') === 'true';
    const activeTab = document.body.getAttribute('data-auth-tab') || 'login';
    const hasAlert = document.body.getAttribute('data-has-alert') === 'true';
    const urlParams = new URLSearchParams(window.location.search);
    const loginRequired = urlParams.get('login_required') === '1';

    if (!isLoggedIn) {
        const skippedBefore = sessionStorage.getItem('skip_auth_popup') === 'true';
        if (loginRequired || hasAlert || !skippedBefore) {
            bukaModalAuth(activeTab, loginRequired && !hasAlert);
        }
    }

    const formPrediksi = document.getElementById('formPrediksi');
    if (formPrediksi) {
        formPrediksi.addEventListener('submit', function () {
            const btn = document.getElementById('btnSubmit');
            if (btn) {
                btn.innerText = 'Memproses CBF (Sentence-BERT + Multi-Label Genre)...';
                btn.style.opacity = '0.75';
            }
        });
    }
});

// ==========================================
// 11. INFINITE LOOPING HORIZONTAL CAROUSEL
// ==========================================
function toggleCarouselDetail(btn) {
    const card = btn.closest('.carousel-movie-card');
    if (!card) return;
    const detailEl = card.querySelector('.carousel-extra-detail');
    if (detailEl) {
        detailEl.style.display = (detailEl.style.display === 'none' || detailEl.style.display === '') ? 'block' : 'none';
    }
}

function geserCarousel(trackId, direction) {
    const track = document.getElementById(trackId);
    if (!track) return;
    const card = track.querySelector('.carousel-movie-card');
    const step = card ? (card.offsetWidth + 16) * 2 : 672;
    track.scrollBy({ left: direction * step, behavior: 'smooth' });
}

function initLoopingCarousels() {
    const tracks = document.querySelectorAll('.loop-carousel-track');

    tracks.forEach(track => {
        const originalCards = Array.from(track.children);
        if (originalCards.length < 2) return;

        // Kloning 1 set di depan & 1 set di belakang -> [Clone Kiri][Asli][Clone Kanan]
        const beforeFrag = document.createDocumentFragment();
        const afterFrag = document.createDocumentFragment();

        originalCards.forEach(card => {
            beforeFrag.appendChild(card.cloneNode(true));
            afterFrag.appendChild(card.cloneNode(true));
        });

        track.insertBefore(beforeFrag, track.firstChild);
        track.appendChild(afterFrag);

        const getSingleSetWidth = () => {
            const firstCard = track.querySelector('.carousel-movie-card');
            if (!firstCard) return 0;
            return originalCards.length * (firstCard.offsetWidth + 16);
        };

        // Posisikan scroll tepat di awal set tengah (Asli)
        let setWidth = getSingleSetWidth();
        track.scrollLeft = setWidth;

        // Teleportasi instan & tak terlihat saat mendekati ujung kiri/kanan (Looping)
        let isAdjusting = false;
        track.addEventListener('scroll', () => {
            if (isAdjusting) return;
            setWidth = getSingleSetWidth();
            if (setWidth <= 0) return;

            if (track.scrollLeft < setWidth * 0.25) {
                isAdjusting = true;
                track.scrollLeft += setWidth;
                requestAnimationFrame(() => { isAdjusting = false; });
            } else if (track.scrollLeft > setWidth * 1.75) {
                isAdjusting = true;
                track.scrollLeft -= setWidth;
                requestAnimationFrame(() => { isAdjusting = false; });
            }
        });

        // Dukungan geser pakai klik & tahan mouse (drag-to-scroll) di desktop
        let isDragging = false;
        let startX = 0;
        let startScrollLeft = 0;

        track.addEventListener('mousedown', (e) => {
            if (e.target.closest('button, a')) return;
            isDragging = true;
            startX = e.pageX - track.offsetLeft;
            startScrollLeft = track.scrollLeft;
        });

        window.addEventListener('mouseup', () => {
            isDragging = false;
        });

        track.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            e.preventDefault();
            const x = e.pageX - track.offsetLeft;
            track.scrollLeft = startScrollLeft - (x - startX) * 1.3;
        });

        // Dukungan scroll menyamping saat memakai scroll wheel mouse di atas baris kartu
        track.addEventListener('wheel', (e) => {
            if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
                e.preventDefault();
                track.scrollLeft += e.deltaY;
            }
        }, { passive: false });
    });
}

document.addEventListener('DOMContentLoaded', initLoopingCarousels);

// ==========================================
// 12. POP-UP MODAL FILM SERUPA (ITEM-TO-ITEM CBF)
// ==========================================
function escapeHtml(str) {
    return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function tutupModalSerupa() {
    const overlay = document.getElementById('similarModalOverlay');
    if (overlay) {
        overlay.classList.remove('show');
        document.body.style.overflow = '';
    }
}

async function bukaModalSerupa(trigger) {
    const title = typeof trigger === 'string' ? trigger : trigger.getAttribute('data-title');
    if (!title) return;

    const overlay = document.getElementById('similarModalOverlay');
    const titleEl = document.getElementById('similarModalTitle');
    const subEl = document.getElementById('similarModalSub');
    const bodyEl = document.getElementById('similarModalBody');

    if (!overlay || !bodyEl) return;

    titleEl.textContent = `Top 10 Film Serupa dengan "${title}"`;
    subEl.textContent = 'Menghitung kemiripan vektor CBF 461-Dim...';
    bodyEl.innerHTML = '<div class="similar-modal-loading">Memuat rekomendasi film serupa...</div>';

    overlay.classList.add('show');
    document.body.style.overflow = 'hidden';

    try {
        const res = await fetch(`/api/serupa?title=${encodeURIComponent(title)}`);
        const data = await res.json();

        if (!res.ok || !data.ok) {
            bodyEl.innerHTML = `<div class="similar-modal-loading">${escapeHtml(data.message || 'Gagal memuat data.')}</div>`;
            return;
        }

        const target = data.target;
        const favSet = new Set((data.favorites || []).map(f => f.toLowerCase()));

        titleEl.textContent = `Top 10 Film Serupa dengan "${target.names}"`;
        subEl.innerHTML = `<strong>Genre Acuan:</strong> ${escapeHtml(target.genre)} &bull; <strong>Rating IMDb:</strong> ${target.score}/100`;

        bodyEl.innerHTML = data.similar.map(film => {
            const isFav = favSet.has(film.names.toLowerCase());
            const safeTitle = escapeHtml(film.names);
            const imdbUrl = `https://www.imdb.com/find/?s=tt&q=${encodeURIComponent(film.names)}`;

            return `
            <div class="rec-item-card" style="background: #1c1c1c;">
                <div class="rec-rank-col">
                    <div class="rec-rank-badge">#${film.rank}</div>
                </div>
                <div class="movie-poster-box poster-rec is-loading"
                  data-poster-title="${safeTitle}"
                  data-poster-year="${film.release_year || 0}">
                 <span class="poster-fallback-text">${safeTitle.charAt(0).toUpperCase()}</span>
             </div>
                <div class="rec-body-col">
                    <div class="rec-title-row">
                        <div>
                            <h4 class="rec-movie-title">
                                ${safeTitle} <span class="rec-year">(${escapeHtml(film.date_x)})</span>
                            </h4>
                            <span class="rec-genre-tag">Genre: ${escapeHtml(film.genre)}</span>
                        </div>
                        <div class="rec-metrics-group">
                            <span class="rec-sim-badge">Kemiripan CBF: ${film.similarity}%</span>
                            <span class="rec-imdb-badge">&#9733; IMDb ${film.score}/100</span>
                        </div>
                    </div>

                    <div class="sim-progress-wrap">
                        <div class="sim-progress-bar" style="width: ${film.similarity}%;"></div>
                    </div>

                    <p class="rec-overview-desc" style="margin-bottom: 10px;">${escapeHtml(film.overview)}</p>

                    <div class="rec-actions-footer" style="justify-content: flex-start; gap: 8px; flex-wrap: wrap;">
                        <button type="button"
                                class="btn-fav ${isFav ? 'is-favorited' : ''}"
                                data-title="${safeTitle}"
                                onclick="toggleFavoritAjax(this)">
                            ${isFav ? '&#9829; Difavoritkan' : '&#9825; Favorit'}
                        </button>
                        <button type="button"
                                class="btn-similar-cbf"
                                data-title="${safeTitle}"
                                onclick="bukaModalSerupa(this)">
                            Serupa (CBF)
                        </button>
                        <a href="${imdbUrl}"
                           target="_blank"
                           rel="noopener noreferrer"
                           class="btn-imdb-card">
                            &#9733; Buka IMDb &nearr;
                        </a>
                    </div>
                </div>
            </div>`;
        }).join('');

        bodyEl.scrollTop = 0;
        observePosters(bodyEl);
    } catch (err) {
        bodyEl.innerHTML = '<div class="similar-modal-loading">Terjadi kesalahan koneksi saat memuat film serupa.</div>';
    }
}

// Tutup pop-up saat menekan tombol Escape di keyboard
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        tutupModalSerupa();
    }
});

// ==========================================
// 13. LAZY LOADING POSTER FILM (INTERSECTION OBSERVER + MEMORY CACHE)
// ==========================================
const posterMemoryCache = new Map();
const posterPendingMap = new Map();

function applyPosterToBox(box, url) {
    box.classList.remove('is-loading');
    if (!url) return;

    const existingImg = box.querySelector('img.movie-poster-img');
    if (existingImg) return;

    const img = document.createElement('img');
    img.className = 'movie-poster-img';
    img.alt = box.getAttribute('data-poster-title') || 'Poster Film';
    img.loading = 'lazy';
    img.onload = () => {
        const fb = box.querySelector('.poster-fallback-text');
        if (fb) fb.style.display = 'none';
        img.classList.add('loaded');
    };
    img.onerror = () => {
        img.remove();
    };
    img.src = url;
    box.appendChild(img);
}

async function fetchPosterUrl(title, year) {
    const key = `${title.toLowerCase()}|${year || 0}`;
    if (posterMemoryCache.has(key)) {
        return posterMemoryCache.get(key);
    }
    if (posterPendingMap.has(key)) {
        return posterPendingMap.get(key);
    }

    const promise = fetch(`/api/poster?title=${encodeURIComponent(title)}&year=${encodeURIComponent(year || 0)}`)
        .then(res => res.json())
        .then(data => {
            const url = (data && data.ok && data.poster_url) ? data.poster_url : null;
            posterMemoryCache.set(key, url);
            posterPendingMap.delete(key);
            return url;
        })
        .catch(() => {
            posterPendingMap.delete(key);
            return null;
        });

    posterPendingMap.set(key, promise);
    return promise;
}

const posterObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        const box = entry.target;
        observer.unobserve(box);

        const title = box.getAttribute('data-poster-title');
        const year = box.getAttribute('data-poster-year') || 0;
        if (!title) {
            box.classList.remove('is-loading');
            return;
        }

        fetchPosterUrl(title, year).then(url => {
            // Sinkronkan juga ke seluruh kartu kloningan carousel dengan film yang sama
            document.querySelectorAll('.movie-poster-box').forEach(el => {
                if (
                    el.getAttribute('data-poster-title') === title &&
                    (el.getAttribute('data-poster-year') || '0') === String(year)
                ) {
                    applyPosterToBox(el, url);
                }
            });
        });
    });
}, { rootMargin: '150px' });

function observePosters(root = document) {
    root.querySelectorAll('.movie-poster-box[data-poster-title]').forEach(box => {
        if (box.getAttribute('data-poster-observed') === '1') return;
        box.setAttribute('data-poster-observed', '1');
        posterObserver.observe(box);
    });
}

// Jalankan setelah DOM & kloning carousel looping selesai terbentuk
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => observePosters(document), 50);
});

// ==========================================
// 14. CUSTOM DROPDOWN FILTER KATALOG (/cari)
// ==========================================
function toggleCustomDropdown(event, dropdownId) {
    if (event) event.stopPropagation();
    const target = document.getElementById(dropdownId);
    if (!target) return;

    const isAlreadyOpen = target.classList.contains('open');

    // Tutup semua dropdown lain yang sedang terbuka
    document.querySelectorAll('.multi-select-dropdown.open').forEach(el => {
        el.classList.remove('open');
    });

    if (!isAlreadyOpen) {
        target.classList.add('open');
    }
}

function toggleGenreDropdown(event) {
    toggleCustomDropdown(event, 'genreMultiDropdown');
}

function selectSingleDropdownOption(dropdownId, inputId, textId, value, label, optionBtn) {
    const hiddenInput = document.getElementById(inputId);
    const triggerText = document.getElementById(textId);
    const dropdown = document.getElementById(dropdownId);

    if (hiddenInput) hiddenInput.value = value;
    if (triggerText) triggerText.textContent = label;

    if (dropdown) {
        dropdown.querySelectorAll('.single-select-option').forEach(btn => {
            btn.classList.remove('active');
        });
        if (optionBtn) optionBtn.classList.add('active');
        dropdown.classList.remove('open');
    }
}

function updateGenreTriggerLabel() {
    const checkboxes = document.querySelectorAll('#genreMultiDropdown input[name="genre"]');
    const checked = Array.from(checkboxes).filter(cb => cb.checked).map(cb => cb.value);
    const labelEl = document.getElementById('genreTriggerText');
    if (!labelEl) return;

    if (checked.length === 0) {
        labelEl.textContent = `Semua Genre (${checkboxes.length})`;
    } else if (checked.length <= 2) {
        labelEl.textContent = checked.join(', ');
    } else {
        labelEl.textContent = `${checked.slice(0, 2).join(', ')} (+${checked.length - 2})`;
    }
}

function clearGenreSelection() {
    document.querySelectorAll('#genreMultiDropdown input[name="genre"]').forEach(cb => {
        cb.checked = false;
    });
    updateGenreTriggerLabel();
}

// Tutup semua custom dropdown jika user klik di area luar
document.addEventListener('click', function (e) {
    document.querySelectorAll('.multi-select-dropdown.open').forEach(dropdown => {
        if (!dropdown.contains(e.target)) {
            dropdown.classList.remove('open');
        }
    });
});
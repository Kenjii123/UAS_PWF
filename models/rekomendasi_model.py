from typing import Optional
from sqlmodel import Field, SQLModel


class UserAccount(SQLModel, table=True):
    __tablename__ = "user_account"

    id: Optional[int] = Field(default=None, primary_key=True)
    nama_lengkap: str = Field(index=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    waktu_daftar: str


class RiwayatRekomendasi(SQLModel, table=True):
    __tablename__ = "riwayat_rekomendasi"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, index=True)
    nama_user: str = Field(index=True)
    input_overview: str
    prediksi_genre: str
    top_judul_film: str
    detail_rekomendasi: str
    waktu_pencarian: str


class UserFavorite(SQLModel, table=True):
    __tablename__ = "user_favorite"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    movie_title: str = Field(index=True)
    movie_date: str = Field(default="-")
    movie_genre: str = Field(default="-")
    movie_score: float = Field(default=0.0)
    waktu_favorit: str
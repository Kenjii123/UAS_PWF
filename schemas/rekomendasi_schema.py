from pydantic import BaseModel

class RekomendasiCreate(BaseModel):
    nama_user: str
    input_overview: str

class RekomendasiResponse(BaseModel):
    id: int
    nama_user: str
    input_overview: str
    prediksi_genre: str
    top_judul_film: str
    detail_rekomendasi: str
    waktu_pencarian: str

    class Config:
        from_attributes = True
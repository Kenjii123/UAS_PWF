from sqlmodel import Session, SQLModel, create_engine
from models.rekomendasi_model import RiwayatRekomendasi, UserAccount

APP_NAME = "Sistem Rekomendasi Film AI - UAS PWF"
APP_DESCRIPTION = "Project FastAPI dengan AI (Sentence-BERT + Logistic Regression + Cosine Similarity) dan PostgreSQL"
APP_VERSION = "1.0.0"

# Sesuaikan password dan nama database dengan pgAdmin 4 kamu
DATABASE_URL = "postgresql://postgres:aquamarine@localhost:5432/rekomendasi_film"

engine = create_engine(DATABASE_URL, echo=True, future=True)

def create_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
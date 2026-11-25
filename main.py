from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from routers.web_route import router as web_router
from config import (
    APP_DESCRIPTION,
    APP_NAME,
    APP_VERSION,
    create_tables,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield

app = FastAPI(
    title=APP_NAME,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key="12345",
)

# Menghubungkan folder static untuk melayani file CSS dan JS
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(web_router)
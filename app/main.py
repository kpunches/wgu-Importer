from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import extract, preview, commit, health

app = FastAPI(
    title="WGU Doc Importer API",
    description="Backend for CCW/SSD extraction and Coda import",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten to GH Pages URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(extract.router, prefix="/extract")
app.include_router(preview.router, prefix="/preview")
app.include_router(commit.router, prefix="/commit")

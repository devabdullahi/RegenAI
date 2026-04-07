from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import farms, fields, recommendations, health, credits, csp, activities

app = FastAPI(
    title="RegenAI API",
    description="AI platform for regenerative agriculture",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(farms.router)
app.include_router(fields.router)
app.include_router(recommendations.router)
app.include_router(credits.router)
app.include_router(csp.router)
app.include_router(activities.router)

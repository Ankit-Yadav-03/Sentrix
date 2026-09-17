"""
FastAPI Application Entry Point — Sentrix SIF Precursor Detection System
"""

import logging
import os 
from dotenv import load_dotenv
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.models.db import init_db, get_session
from backend.pipeline.validator import load_site_registry_from_db
from backend.api.reports import router as reports_router
from backend.api.sites import router as sites_router
from backend.api.clusters import router as clusters_router
from backend.api.dashboard import router as dashboard_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv() 

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_url = os.getenv("DATABASE_URL")
    engine = init_db(db_url)
    logger.info("DB initialized")
    # Load site registry from DB
    try:
        s = get_session()
        load_site_registry_from_db(s)
        s.close()
    except Exception as e:
        logger.warning(f"Site registry load from DB failed: {e} — using defaults")
    yield
    logger.info("Shutdown")


app = FastAPI(
    title="SIF Precursor Detection System — v0",
    description="Sentrix: AI-powered near-miss report analysis for oil & gas safety",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(reports_router)
app.include_router(sites_router)
app.include_router(clusters_router)
app.include_router(dashboard_router)
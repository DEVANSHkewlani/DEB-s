from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
import uvicorn
from api.endpoints import router as api_router

app = FastAPI(
    title="DEB's Health Navigator API",
    description="Backend for Hybrid RAG Health Information System",
    version="1.0.0"
)

# CORS configuration
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "*")
origins = [origin.strip() for origin in allowed_origins_str.split(',')] if allowed_origins_str != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from api.routers import reports, education, alerts, maps, knowledge_gaps
from api import lens
app.include_router(api_router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(education.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(maps.router, prefix="/api/v1/maps")
app.include_router(lens.router, prefix="/api/v1/lens")
app.include_router(knowledge_gaps.router, prefix="/api/v1/knowledge-gaps", tags=["knowledge-gaps"])

# Get absolute path to public directory
current_dir = os.path.dirname(os.path.abspath(__file__))
public_dir = os.path.join(os.path.dirname(current_dir), "public")

@app.get("/")
async def root():
    return RedirectResponse(url="/pages/index.html")

# Serve static files - catch-all mount must be last if it matches everything
app.mount("/", StaticFiles(directory=public_dir, html=True), name="public")

if __name__ == "__main__":
    is_prod = os.getenv("ENV", "development").lower() == "production"
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=not is_prod)

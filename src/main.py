from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.pdf_extraction import router as pdf_router

app = FastAPI(
    title="alysa API",
    description="Backend för PDF-analys och framtida AI-funktioner",
    version="0.1.0"
)

# CORS – justera origins senare
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(pdf_router, prefix="/api")

@app.get("/")
def health_check():
    return {"status": "alysa backend running"}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.routes import plan_routes, evaluation_routes

# Initialize SQLite database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Academic Research Prototype for BINUS University S2 Thesis: 'Design and Evaluation of an AI-Based Personalized Running Training Recommendation System'",
    version="1.0.0"
)

# CORS configuration: this is a local academic prototype, so only the Vite
# dev server origins are allowed. allow_origins=["*"] is avoided because it is
# an invalid/insecure combination with allow_credentials=True.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plan_routes.router, prefix="/api")
app.include_router(evaluation_routes.router, prefix="/api")

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "prototype": settings.PROJECT_NAME,
        "academic_affiliation": "BINUS University - S2 Information Technology",
        "safety_disclaimer": "This system provides running recommendations solely for academic research and educational purposes. It does not constitute medical advice."
    }

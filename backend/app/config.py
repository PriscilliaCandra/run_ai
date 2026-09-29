import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    PROJECT_NAME: str = "AI Running Training Recommendation System (Academic Prototype)"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./running_research.db")
    
    # LLM Settings
    # Supports 'gemini', 'openai', or 'auto' (checks available keys)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

settings = Settings()

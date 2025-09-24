"""
Configuration settings for Instagram AI Agent
"""
import os
from dotenv import load_dotenv
from pydantic import BaseSettings
from typing import List, Optional

load_dotenv()

class Settings(BaseSettings):
    # Instagram Credentials
    instagram_username: str = os.getenv("INSTAGRAM_USERNAME", "")
    instagram_password: str = os.getenv("INSTAGRAM_PASSWORD", "")
    
    # AI API Keys
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///instagram_agent.db")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Creative Studio Information
    studio_name: str = os.getenv("STUDIO_NAME", "Your Creative Studio")
    studio_description: str = os.getenv("STUDIO_DESCRIPTION", "Professional creative services")
    studio_website: str = os.getenv("STUDIO_WEBSITE", "https://yourstudio.com")
    studio_email: str = os.getenv("STUDIO_EMAIL", "hello@yourstudio.com")
    
    # Targeting Configuration
    target_locations: List[str] = os.getenv("TARGET_LOCATIONS", "Dubai,UAE").split(",")
    target_industries: List[str] = os.getenv("TARGET_INDUSTRIES", "real_estate,property,construction,architecture").split(",")
    target_keywords: List[str] = os.getenv("TARGET_KEYWORDS", "real estate,dubai properties,property development,real estate marketing").split(",")
    
    # Rate Limiting
    max_dm_per_hour: int = int(os.getenv("MAX_DM_PER_HOUR", "10"))
    max_outreach_per_day: int = int(os.getenv("MAX_OUTREACH_PER_DAY", "50"))
    min_delay_between_messages: int = int(os.getenv("MIN_DELAY_BETWEEN_MESSAGES", "300"))
    
    # Safety Settings
    enable_auto_response: bool = os.getenv("ENABLE_AUTO_RESPONSE", "true").lower() == "true"
    enable_auto_outreach: bool = os.getenv("ENABLE_AUTO_OUTREACH", "true").lower() == "true"
    human_oversight_required: bool = os.getenv("HUMAN_OVERSIGHT_REQUIRED", "false").lower() == "true"
    
    class Config:
        env_file = ".env"

settings = Settings()

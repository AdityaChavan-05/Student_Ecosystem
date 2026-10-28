import os
from dotenv import load_dotenv

# Load private configuration from the local .env file

load_dotenv()

class Config:
"""Central configuration for the Student Ecosystem application."""

```
# Flask settings
SECRET_KEY = os.getenv("SECRET_KEY", "development-key-change-me")
DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

# Google Gemini AI
GEMINI_API_KEY = os.getenv("AI_API_KEY", "")

# Supabase database
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# News settings
DEFAULT_NEWS_LIMIT = 8
MAX_NEWS_LIMIT = 10
NEWS_CACHE_MINUTES = 30

# College updates settings
COLLEGE_CACHE_MINUTES = 15
```

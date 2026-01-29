import sys
import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")

# Available Models for switching
AVAILABLE_MODELS = {
    "Gemini 2.0 Flash (Free)": "google/gemini-2.0-flash-exp:free",
    "Claude 3.5 Sonnet": "anthropic/claude-3.5-sonnet",
    "GPT-4o Mini": "openai/gpt-4o-mini",
    "Llama 3.1 70B": "meta-llama/llama-3.1-70b-instruct",
    "Gemini 1.5 Pro": "google/gemini-pro-1.5"
}

# Validation
if not TELEGRAM_BOT_TOKEN:
    print("❌ ERROR: TELEGRAM_BOT_TOKEN is not set in environment variables.")
    sys.exit(1)

if not OPENROUTER_API_KEY:
    print("❌ ERROR: OPENROUTER_API_KEY is not set in environment variables.")
    sys.exit(1)

# Admin Settings
ADMIN_ID = os.getenv("ADMIN_ID") # Telegram User ID

# File Paths
DATABASE_PATH = "database.xlsx"

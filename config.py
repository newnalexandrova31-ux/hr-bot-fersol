import sys
import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")

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

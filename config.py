import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-thinking-preview:free") # Note: Gemini 3 doesn't exist yet, using 2.0 for now

# Admin Settings
ADMIN_ID = os.getenv("ADMIN_ID") # Telegram User ID

# File Paths
DATABASE_PATH = "database.xlsx"
FAISS_INDEX_PATH = "faiss_index.bin"
KNOWLEDGE_BASE_PKL = "knowledge_base.pkl"

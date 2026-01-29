import pandas as pd
import os
from openai import OpenAI
import config

# Initialize OpenRouter Client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=config.OPENROUTER_API_KEY,
    timeout=30.0, # Production timeout
)

def load_all_knowledge():
    """
    Reads all sheets from Excel and returns a single combined string.
    Optimized for files < 1MB to avoid heavy vector databases.
    """
    if not os.path.exists(config.DATABASE_PATH):
        return "База знаний пуста."

    try:
        xl = pd.ExcelFile(config.DATABASE_PATH)
        full_text = ""
        for sheet_name in xl.sheet_names:
            df = pd.read_excel(config.DATABASE_PATH, sheet_name=sheet_name)
            sheet_content = f"\n--- РАЗДЕЛ: {sheet_name} ---\n"
            # Combine all non-empty rows into text
            for _, row in df.iterrows():
                row_text = " ".join([str(val) for val in row.values if pd.notna(val)]).strip()
                if len(row_text) > 5:
                    sheet_content += row_text + "\n"
            full_text += sheet_content
        return full_text
    except Exception as e:
        return f"Ошибка при чтении базы: {e}"

# Global cache for the knowledge base text
_KNOWLEDGE_CACHE = None

def reset_cache():
    global _KNOWLEDGE_CACHE
    _KNOWLEDGE_CACHE = None

def get_categories():
    """Returns a list of cleaned sheet names from the Excel database."""
    if not os.path.exists(config.DATABASE_PATH):
        return []
    try:
        xl = pd.ExcelFile(config.DATABASE_PATH)
        categories = []
        for name in xl.sheet_names:
            # Clean up tab characters and other artifacts
            clean_name = name.replace("_x0009_", " ").replace("\xa0", " ").strip()
            categories.append(clean_name)
        return categories
    except Exception:
        return []

import re

def get_subcategories(sheet_name_partial):
    """Returns a list of subcategories from a specific sheet based on numbering pattern (e.g. 1.1.)."""
    if not os.path.exists(config.DATABASE_PATH):
        return []
    try:
        xl = pd.ExcelFile(config.DATABASE_PATH)
        # Find exact sheet name
        target_sheet = None
        for name in xl.sheet_names:
            # Clean name for comparison
            clean_name = name.replace("_x0009_", " ").replace("\xa0", " ").strip()
            if sheet_name_partial in clean_name or sheet_name_partial in name:
                target_sheet = name
                break
        
        if not target_sheet:
            return []

        df = pd.read_excel(config.DATABASE_PATH, sheet_name=target_sheet, header=None)
        
        # Look for pattern "X.Y." in column 0
        subcategories = []
        for idx, row in df.iterrows():
            col0 = str(row[0])
            col1 = str(row[1])
            
            # Check if col0 looks like "1.1." or "1.2."
            # Also handle cases where it might be read as float (1.1)
            if re.match(r'^\d+\.\d+\.?$', col0):
                if col1 and col1.lower() != 'nan':
                     subcategories.append(col1.strip())
        
        return subcategories
    except Exception as e:
        print(f"Error getting subcategories: {e}")
        return []

def get_context():
    global _KNOWLEDGE_CACHE
    if _KNOWLEDGE_CACHE is None:
        _KNOWLEDGE_CACHE = load_all_knowledge()
    return _KNOWLEDGE_CACHE

def ask_gemini(question):
    """
    Sends question with the FULL context to Gemini.
    Gemini 1.5 Flash easily handles the entire 60KB Excel file in the prompt.
    """
    context = get_context()
    
    prompt = f"""
Ты — «HR-бот», строгий и профессиональный ассистент отдела кадров компании Fersol. Твоя единственная цель — предоставлять информацию из официальной базы знаний.

КРИТИЧЕСКИЕ ПРАВИЛА:
1. ОТВЕЧАЙ ТОЛЬКО НА ОСНОВЕ ПРЕДОСТАВЛЕННОГО КОНТЕКСТА.
2. ЕСЛИ В КОНТЕКСТЕ НЕТ ПРЯМОГО ОТВЕТА НА ВОПРОС, ТЫ ОБЯЗАН ОТВЕТИТЬ СЛЕДУЮЩЕЙ ФРАЗОЙ: «К сожалению, у меня нет информации по этому вопросу в базе знаний. Пожалуйста, обратитесь к HR-менеджеру для уточнения.»
3. ЗАПРЕЩЕНО выдумывать факты, использовать свои общие знания о мире или предполагать, как это может работать в других компаниях.
4. ЗАПРЕЩЕНО добавлять ссылки на внешние ресурсы или пути к файлам, если их нет в контексте.
5. Пиши связным текстом, разделяя мысли абзацами. НЕ используй списки, точки и нумерацию.
6. Твой тон должен быть официально-деловым, но вежливым.

Контекст базы знаний:
{context}

Вопрос пользователя: {question}
Ответ:"""

    try:
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://railway.app",
                "X-Title": "HR Assistant Bot",
            },
            model=config.OPENROUTER_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Ошибка при обращении к ИИ: {e}"

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
Ты — «HR-бот», профессиональный и дружелюбный ассистент отдела кадров. Твоя задача — помогать сотрудникам находить информацию в предоставленной базе знаний.

Твои правила:
1. Используй ТОЛЬКО тот фрагмент текста из базы знаний, который ПРЯМО относится к вопросу пользователя.
2. НЕ добавляй общую справочную информацию или ссылки на папки (например, пути на диске U:), если они не указаны в базе именно для этого конкретного вопроса.
3. Если в контексте нет прямого ответа, вежливо скажи, что не обладаешь этой информацией.
4. Ответ должен быть кратким и четким, без лишних «полезных» дополнений от себя.

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

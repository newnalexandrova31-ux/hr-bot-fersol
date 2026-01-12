import pandas as pd
import numpy as np
import faiss
import pickle
import os
from openai import OpenAI
from sentence_transformers import SentenceTransformer
import config

# Initialize OpenRouter Client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=config.OPENROUTER_API_KEY,
)

# Load Embedding Model (Local for fast vector search)
# We'll use a small, efficient model to build the index locally
embed_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

def load_knowledge_base():
    """
    Reads all sheets from Excel and extracts text.
    """
    if not os.path.exists(config.DATABASE_PATH):
        return []

    xl = pd.ExcelFile(config.DATABASE_PATH)
    knowledge_base = []

    for sheet_name in xl.sheet_names:
        df = pd.read_excel(config.DATABASE_PATH, sheet_name=sheet_name)
        
        # General extraction: combine all non-empty cell values into strings per row
        for _, row in df.iterrows():
            content = " ".join([str(val) for val in row.values if pd.notna(val)]).strip()
            if len(content) > 10:
                knowledge_base.append({
                    "content": content,
                    "source": sheet_name
                })
    
    return knowledge_base

def build_index(kb):
    """
    Builds FAISS index for the knowledge base.
    """
    texts = [item['content'] for item in kb]
    embeddings = embed_model.encode(texts)
    
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings).astype('float32'))
    
    # Save index and KB
    faiss.write_index(index, config.FAISS_INDEX_PATH)
    with open(config.KNOWLEDGE_BASE_PKL, 'wb') as f:
        pickle.dump(kb, f)

def get_context(query, top_k=3):
    """
    Retrieves most relevant chunks from FAISS index.
    """
    if not os.path.exists(config.FAISS_INDEX_PATH):
        kb = load_knowledge_base()
        build_index(kb)
    else:
        with open(config.KNOWLEDGE_BASE_PKL, 'rb') as f:
            kb = pickle.dump(kb, f) # Error here, should be load. Let me fix in next tool.
            
    # Load if not already
    index = faiss.read_index(config.FAISS_INDEX_PATH)
    with open(config.KNOWLEDGE_BASE_PKL, 'rb') as f:
        kb = pickle.load(f)

    query_embedding = embed_model.encode([query])
    distances, indices = index.search(np.array(query_embedding).astype('float32'), top_k)
    
    context = ""
    for idx in indices[0]:
        if idx != -1:
            context += f"- {kb[idx]['content']}\n"
    
    return context

def ask_gemini(question):
    """
    Sends question with context to OpenRouter (Gemini).
    """
    context = get_context(question)
    
    prompt = f"""
Ты — «HR-бот», профессиональный и дружелюбный ассистент отдела кадров. Твоя задача — помогать сотрудникам находить информацию в базе знаний компании.
Твои правила:
1. Используй ТОЛЬКО предоставленный ниже контекст для ответа.
2. Если в контексте нет ответа, вежливо скажи, что не обладаешь этой информацией и предложи обратиться в HR напрямую.
3. Всегда указывай ссылки на документы, если они есть в контексте.

Контекст:
{context}

Вопрос пользователя: {question}
Ответ:"""

    try:
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://railway.app", # Optional for OpenRouter
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

import logging
import asyncio
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command
import config
from rag_engine import ask_gemini

import rag_engine

# Logging setup (Console + File)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_log.log"),
        logging.StreamHandler()
    ]
)
bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

from aiogram.utils.keyboard import InlineKeyboardBuilder

# ThreadPool for non-blocking LLM calls
executor = ThreadPoolExecutor(max_workers=10)

# Topics for quick access
QUICK_TOPICS = {
    "📅 Отпуск": "Как оформить отпуск?",
    "💰 Зарплата": "Когда придет зарплата?",
    "📄 Документы": "Где найти шаблоны заявлений?",
    "🏥 Больничный": "Как закрыть больничный?",
}

# Simple Rate Limiting Middleware
class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, limit: int = 5, window: int = 60):
        self.limit = limit
        self.window = window
        self.users = defaultdict(list)
        super().__init__()

    async def __call__(self, handler, event, data):
        if not isinstance(event, types.Message):
            return await handler(event, data)
            
        user_id = event.from_user.id
        now = time.time()
        
        # Clean up old timestamps
        self.users[user_id] = [t for t in self.users[user_id] if now - t < self.window]
        
        if len(self.users[user_id]) >= self.limit:
            await event.answer("⚠️ Слишком много запросов. Пожалуйста, подождите минуту.")
            return
            
        self.users[user_id].append(now)
        return await handler(event, data)

# Register Middleware
dp.message.middleware(RateLimitMiddleware())

def get_start_keyboard():
    builder = InlineKeyboardBuilder()
    for text in QUICK_TOPICS.keys():
        builder.button(text=text, callback_data=f"topic_{text}")
    builder.button(text="👤 Связаться с HR", callback_data="contact_hr")
    builder.adjust(2)
    return builder.as_markup()

def get_feedback_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="👍 Помогло", callback_data="feedback_up")
    builder.button(text="👎 Не помогло", callback_data="feedback_down")
    builder.button(text="👤 Спросить HR", callback_data="contact_hr")
    builder.adjust(2)
    return builder.as_markup()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}! Я твой HR-ассистент.\n\n"
        "Я помогу найти информацию по регламентам, процедурам и документам компании.\n"
        "Выбери тему ниже или просто задай мне вопрос.",
        reply_markup=get_start_keyboard()
    )

@dp.message(Command("reload"))
async def reload_handler(message: types.Message):
    if str(message.from_user.id) == config.ADMIN_ID:
        rag_engine.reset_cache()
        await message.answer("✅ База знаний успешно перезагружена!")
    else:
        await message.answer("⚠️ У вас нет прав для выполнения этой команды.")

@dp.message(Command("help"))
async def help_handler(message: types.Message):
    await message.answer(
        "❓ **Как пользоваться ботом:**\n\n"
        "1. Просто напиши свой вопрос текстом.\n"
        "2. Используй кнопки под сообщением /start для быстрого доступа.\n"
        "3. Если бот не нашел ответ, нажми 'Связаться с HR'.\n\n"
        "Я ищу информацию только в официальной базе знаний компании."
    )

@dp.callback_query(F.data.startswith("topic_"))
async def topic_callback_handler(callback: types.CallbackQuery):
    topic_text = callback.data.replace("topic_", "")
    query = QUICK_TOPICS.get(topic_text)
    if query:
        await callback.message.answer(f"🔍 Ищу ответ на вопрос: *{query}*", parse_mode="Markdown")
        # Simulating a message for chat_handler logic
        dummy_message = callback.message
        dummy_message.text = query
        dummy_message.from_user = callback.from_user
        await chat_handler(dummy_message)
    await callback.answer()

@dp.callback_query(F.data == "contact_hr")
async def contact_hr_handler(callback: types.CallbackQuery):
    await callback.message.answer(
        "📧 Для связи с HR-отделом напишите на почту: `hr@fersol.org`\n"
        "Или обратитесь к Наталье Александровой через личные сообщения."
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("feedback_"))
async def feedback_handler(callback: types.CallbackQuery):
    feedback = "положительный" if "up" in callback.data else "отрицательный"
    await callback.message.edit_reply_markup(reply_markup=None) # Remove buttons
    await callback.message.answer(f"🙏 Спасибо за ваш {feedback} отзыв! Это помогает мне становиться лучше.")
    
    # Log feedback to admin
    if config.ADMIN_ID:
        try:
            await bot.send_message(
                config.ADMIN_ID,
                f"📝 **Feedback:** {feedback} от {callback.from_user.full_name}"
            )
        except Exception:
            pass
    await callback.answer()

@dp.message(F.text)
async def chat_handler(message: types.Message):
    # Show typing status
    await bot.send_chat_action(message.chat.id, "typing")
    
    user_query = message.text
    
    # Run synchronous LLM call in a thread pool to avoid blocking the bot
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(executor, ask_gemini, user_query)
    
    # Send answer to user
    try:
        await message.reply(response, parse_mode="Markdown", reply_markup=get_feedback_keyboard())
    except Exception as e:
        logging.error(f"Markdown parsing failed: {e}. Sending plain text.")
        await message.reply(response, reply_markup=get_feedback_keyboard()) # Fallback to plain text
    
    # Log to Admin
    if config.ADMIN_ID:
        try:
            log_text = (
                f"👤 **User:** {message.from_user.full_name} (@{message.from_user.username})\n"
                f"❓ **Query:** {user_query}\n"
                f"🤖 **Bot:** {response[:500]}..."
            )
            await bot.send_message(config.ADMIN_ID, log_text, parse_mode="Markdown")
        except Exception:
            pass # Ignore admin logging errors to keep user experience smooth

async def main():
    print("Bot is starting (Production Mode)...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

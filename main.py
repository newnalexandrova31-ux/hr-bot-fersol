import logging
import asyncio
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
import config
from rag_engine import ask_gemini, get_categories, get_subcategories

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

# ThreadPool for non-blocking LLM calls
executor = ThreadPoolExecutor(max_workers=10)

# Emojis for categories
CATEGORY_EMOJIS = {
    "1. О Ферсол": "🏢",
    "2. О зарплате": "💰",
    "3. Испытательный срок": "⏳",
    "4. ДМС и НС": "🏥",
    "5. Отпуск и больничный": "📅",
    "6. Печать документов": "🖨️",
    "7. Удаленный доступ": "💻",
    "8. Как закрыть офис": "🔑",
    "9. Политики и заявления": "📄"
}

def get_main_menu_keyboard():
    builder = ReplyKeyboardBuilder()
    categories = get_categories()
    for cat in categories:
        emoji = ""
        for key, val in CATEGORY_EMOJIS.items():
            if key in cat or cat in key:
                emoji = val + " "
                break
        builder.button(text=f"{emoji}{cat}")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

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

def get_feedback_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="👍 Помогло", callback_data="feedback_up")
    builder.button(text="👎 Не помогло", callback_data="feedback_down")
    builder.button(text="👤 Спросить HR", callback_data="contact_hr")
    builder.adjust(2)
    return builder.as_markup()

@dp.message(F.text.lower().in_(["привет", "здравствуй", "здравствуйте", "hi", "hello", "меню", "start", "/start"]))
async def greeting_handler(message: types.Message):
    await start_handler(message)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}! Я твой HR-ассистент в компании **Fersol**.\n\n"
        "Я помогу тебе найти информацию о регламентах, процедурах и корпоративных политиках.\n\n"
        "**Как я могу помочь:**\n"
        "1. Выбери интересующий раздел в меню ниже.\n"
        "2. Или просто напиши свой вопрос текстом (например: 'Как оформить отпуск?').\n\n"
        "Что тебя интересует сейчас?",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(Command("reload"))
async def reload_handler(message: types.Message):
    if str(message.from_user.id) == config.ADMIN_ID:
        rag_engine.reset_cache()
        await message.answer("✅ База знаний успешно перезагружена!", reply_markup=get_main_menu_keyboard())
    else:
        await message.answer("⚠️ У вас нет прав для выполнения этой команды.")

@dp.message(Command("help"))
async def help_handler(message: types.Message):
    await message.answer(
        "❓ **Как пользоваться ботом:**\n\n"
        "1. Используйте кнопки меню для навигации по разделам.\n"
        "2. Задавайте вопросы в свободной форме.\n"
        "3. Если бот не нашел ответ, используйте кнопку 'Спросить HR' под сообщением.\n\n"
        "Я черпаю информацию только из официальной базы знаний Fersol.",
        parse_mode="Markdown"
    )

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

@dp.message(F.text == "🔙 Назад")
async def back_handler(message: types.Message):
    await start_handler(message)

@dp.message(lambda msg: "1. О Ферсол" in msg.text)
async def fersol_menu_handler(message: types.Message):
    subcats = get_subcategories("1. О Ферсол")
    if not subcats:
        await chat_handler(message)
        return

    builder = ReplyKeyboardBuilder()
    for sub in subcats:
        builder.button(text=sub)
    builder.button(text="🔙 Назад")
    builder.adjust(1)
    
    await message.answer("📂 Выберите интересующий подраздел:", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(F.text)
async def chat_handler(message: types.Message):
    # Show typing status
    await bot.send_chat_action(message.chat.id, "typing")
    
    user_query = message.text
    
    # Check if the query is a category button click (removing emoji if present)
    clean_query = user_query
    for emoji in CATEGORY_EMOJIS.values():
        clean_query = clean_query.replace(emoji, "").strip()
    
    # If it's a category, we might want a slightly different prompt to LLM
    prompt_query = user_query
    if clean_query in get_categories():
        prompt_query = f"Расскажи кратко, что содержится в разделе '{clean_query}' и какие основные вопросы он охватывает?"

    # Run synchronous LLM call in a thread pool to avoid blocking the bot
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(executor, ask_gemini, prompt_query)
    
    # Determine if we should show feedback buttons
    # User requested no buttons for "О Ферсол" subsections
    show_feedback = True
    subcats_fersol = get_subcategories("1. О Ферсол")
    # Fuzzy match or exact match? The button text matches exactly the subcat title.
    if clean_query in subcats_fersol:
        show_feedback = False

    # Send answer to user
    reply_markup = get_feedback_keyboard() if show_feedback else None
    
    try:
        await message.reply(response, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception as e:
        logging.error(f"Markdown parsing failed: {e}. Sending plain text.")
        await message.reply(response, reply_markup=reply_markup) # Fallback to plain text
    
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

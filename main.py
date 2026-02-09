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
    builder = InlineKeyboardBuilder()
    categories = get_categories()
    for cat in categories:
        emoji = ""
        for key, val in CATEGORY_EMOJIS.items():
            if key in cat or cat in key:
                emoji = val + " "
                break
        # Используем callback_data вместо текста
        builder.button(text=f"{emoji}{cat}", callback_data=f"cat_{cat}")
    builder.adjust(1) # Инлайн кнопки лучше смотрятся в один столбец, если названия длинные
    return builder.as_markup()

def get_fersol_submenu():
    subcats = get_subcategories("1. О Ферсол")
    builder = InlineKeyboardBuilder()
    for sub in subcats:
        builder.button(text=sub, callback_data=f"sub_{sub}")
    builder.button(text="🔙 Назад в меню", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

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

@dp.message(F.text.regexp(r"(?i)^(привет|здравствуй|hello|hi|меню|start)"))
async def greeting_handler(message: types.Message):
    await start_handler(message)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Я — виртуальный ассистент компании Fersol и готов предоставить информацию по меню ниже.",
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

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Что тебя интересует сейчас?",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("cat_"))
async def category_callback_handler(callback: types.CallbackQuery):
    category = callback.data.replace("cat_", "")
    
    if "1. О Ферсол" in category:
        await callback.message.edit_text(
            "📂 Выберите интересующий подраздел:",
            reply_markup=get_fersol_submenu()
        )
    else:
        # Для остальных категорий запрашиваем краткое описание у ИИ
        prompt = f"Расскажи мне подробно про '{category}' как сотруднику. Какие здесь действуют правила и процедуры?"
        await callback.message.edit_text("⏳ Загружаю информацию...")
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(executor, ask_gemini, prompt)
        
        try:
            await callback.message.edit_text(response, parse_mode="Markdown", reply_markup=get_feedback_keyboard())
        except Exception:
            await callback.message.edit_text(response, reply_markup=get_feedback_keyboard())
            
    await callback.answer()

@dp.callback_query(F.data.startswith("sub_"))
async def subcategory_callback_handler(callback: types.CallbackQuery):
    subcategory = callback.data.replace("sub_", "")
    await callback.message.edit_text(f"⏳ Ищу информацию по теме: {subcategory}...")
    
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(executor, ask_gemini, subcategory)
    
    # Для подразделов "О Ферсол" не показываем кнопки фидбека по просьбе пользователя
    try:
        await callback.message.edit_text(response, parse_mode="Markdown")
    except Exception:
        await callback.message.edit_text(response)
    
    # Добавляем кнопку возврата в меню после ответа
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в меню", callback_data="back_to_main")
    await callback.message.answer("Вы можете вернуться в главное меню или задать другой вопрос:", reply_markup=builder.as_markup())
    
    await callback.answer()

@dp.message(F.text == "🔙 Назад")
async def back_handler(message: types.Message):
    await start_handler(message)

@dp.message(lambda msg: "1. О Ферсол" in msg.text)
async def fersol_menu_handler(message: types.Message):
    await message.answer("📂 Выберите интересующий подраздел:", reply_markup=get_fersol_submenu())

@dp.message(F.text)
async def chat_handler(message: types.Message):
    # Show typing status
    await bot.send_chat_action(message.chat.id, "typing")
    
    user_query = message.text
    
    # Run synchronous LLM call in a thread pool to avoid blocking the bot
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(executor, ask_gemini, user_query)
    
    # Проверяем, содержит ли ответ фразу о нехватке информации
    no_info_msg = "К сожалению, у меня нет информации по этому вопросу"
    reply_markup = get_feedback_keyboard()
    
    if no_info_msg in response:
        # Если информации нет, добавляем инлайн-кнопку для прямой связи с HR
        builder = InlineKeyboardBuilder()
        builder.button(text="👤 Связаться с HR", callback_data="contact_hr")
        builder.button(text="🔙 В главное меню", callback_data="back_to_main")
        builder.adjust(1)
        reply_markup = builder.as_markup()

    # Send answer to user
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

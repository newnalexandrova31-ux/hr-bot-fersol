import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
import config
from rag_engine import ask_gemini

# Logging
logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "👋 Привет! Я твой HR-ассистент.\n\n"
        "Я помогу найти информацию по регламентам, процедурам и документам компании.\n"
        "Просто задай мне вопрос, например: 'Как оформить отпуск?' или 'Где найти шаблон заявления?'"
    )

@dp.message(F.text)
async def chat_handler(message: types.Message):
    # Show typing status
    await bot.send_chat_action(message.chat.id, "typing")
    
    user_query = message.text
    response = ask_gemini(user_query)
    
    # Send answer to user
    await message.reply(response, parse_mode="Markdown")
    
    # Log to Admin
    if config.ADMIN_ID:
        try:
            log_text = (
                f"👤 **User:** {message.from_user.full_name} (@{message.from_user.username})\n"
                f"❓ **Query:** {user_query}\n"
                f"🤖 **Bot:** {response[:500]}..." # Truncate long logs
            )
            await bot.send_message(config.ADMIN_ID, log_text, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Failed to send log to admin: {e}")

async def main():
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os
import re
import logging
from logging.handlers import TimedRotatingFileHandler
import yt_dlp
from config import TOKEN
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramEntityTooLarge

os.makedirs('logs', exist_ok=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_filename = 'logs/bot-latest.log'

file_handler = TimedRotatingFileHandler(
    filename=log_filename,
    when='midnight',
    interval=1,
    backupCount=30,
    encoding='utf-8'
)
file_handler.suffix = "%Y-%m-%d-%H-%M-%S"

def log_namer(default_name):
    base_dir, filename = os.path.split(default_name)
    clean_date = filename.replace("bot-latest.log.", "")
    new_filename = f"bot-{clean_date}.log"
    return os.path.join(base_dir, new_filename)

file_handler.namer = log_namer
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

if logger.hasHandlers():
    logger.handlers.clear()

logger.addHandler(file_handler)
logger.addHandler(console_handler)

bot = Bot(token=TOKEN)
dp = Dispatcher()

def get_user_display_name(user: types.User):
    if user.username:
        return f"@{user.username}"
    return user.first_name

def download_media(url: str, mode: str) -> str:
    """Синхронная функция скачивания через yt-dlp (видео или аудио)"""
    
    ydl_opts = {
        'outtmpl': '%(id)s.%(ext)s', 
        'quiet': True,
        'no_warnings': True,
    }

    if mode == 'video':
        ydl_opts['format'] = 'bestvideo[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4][vcodec^=avc]/best[ext=mp4]/best'
    else:
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if mode == 'audio':
            base_name, _ = os.path.splitext(filename)
            filename = f"{base_name}.mp3" 
        return filename

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user = message.from_user
    name = get_user_display_name(user)
    logger.info(f"[{user.id}] {name} начал использовать бота.")
    
    await message.answer(
        "Привет! Я бот для скачивания из TikTok.\n"
        "Отправь мне ссылку, и я предложу скачать видео (файлом) или отдельно аудио!"
    )

@dp.message(F.text.regexp(r'(?i)https?://(?:[a-zA-Z0-9-]+\.)*(tiktok\.com|youtube\.com|youtu\.be|instagram\.com)/.*'))
async def handle_media_link(message: types.Message, state: FSMContext):
    url = message.text
    user = message.from_user
    name = get_user_display_name(user)
    logger.info(f"[{user.id}] {name} прислал ссылку: {url}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📹 Скачать видео", callback_data='video')],
        [InlineKeyboardButton(text="🎵 Скачать аудио", callback_data='audio')]
    ])
    await state.update_data(media_url=url)
    await message.answer("Что именно нужно скачать?", reply_markup=keyboard)

@dp.callback_query(F.data.in_({"video", "audio"}))
async def button_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    user = callback.from_user
    name = get_user_display_name(user)
    mode = callback.data
    logger.info(f"[{user.id}] {name} нажал кнопку: {mode}")

    data = await state.get_data()
    media_url = data.get('media_url')
    
    if not media_url:
        await callback.message.edit_text("❌ Ссылка устарела. Отправьте её заново.")
        return
    await state.clear()

    status_text = "⏳ Скачиваю видео..." if mode == 'video' else "⏳ Скачиваю аудио..."
    await callback.message.edit_text(status_text)

    try:
        file_path = await asyncio.to_thread(download_media, media_url, mode)
        
        try:
            if mode == 'video':
                document = FSInputFile(file_path)
                await callback.message.answer_document(
                    document=document,
                    disable_content_type_detection=True
                )
            elif mode == 'audio':
                audio = FSInputFile(file_path)
                await callback.message.answer_audio(
                    audio=audio
                )
            logger.info(f"[{user.id}] {name} -> Успешно отправлен файл {mode}.")

        except TelegramEntityTooLarge:
            await callback.message.answer("❌ Файл слишком большой! Telegram позволяет отправлять ботам файлы размером не более 50 МБ.")
            logger.warning(f"[{user.id}] {name} -> Файл превысил лимит в 50 МБ.")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    except Exception as e:
        logger.error(f"Error process_media [{mode}]: {e}")
        await callback.message.answer("❌ Произошла ошибка. Возможно, видео скрыто приватностью, удалено или временно недоступно.")

@dp.message()
async def handle_other_messages(message: types.Message):
    await message.answer("Пожалуйста, отправьте корректную ссылку на TikTok, YouTube или Instagram.")

async def main():
    print(f"Активный лог: {log_filename}")
    print("Бот запущен")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен пользователем.")

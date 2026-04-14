import os
import re
import json
import random
import yt_dlp
import asyncio
import logging
from config import TOKEN
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram import Bot, Dispatcher, F, types
from aiogram.exceptions import TelegramEntityTooLarge
from logging.handlers import TimedRotatingFileHandler
from instagram_photo_downloader import get_insta_photos
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.types import FSInputFile, URLInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from tiktok_photo_downloader import get_tiktok_photos_and_download, get_tiktok_audio, check_tiktok_media_type

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

def sync_playwright_cookies():
    """Конвертирует сессию браузера в формат для yt-dlp"""
    state_file = 'ig_browser_state.json'
    cookie_file = 'ig_cookies.txt'
    if not os.path.exists(state_file):
        return None   
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)  
        cookies = data.get('cookies', [])
        if not cookies:
            return None 
        with open(cookie_file, 'w', encoding='utf-8') as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# This file is generated automatically.\n\n")
            for c in cookies:
                domain = c.get('domain', '')
                include_sub = 'TRUE' if domain.startswith('.') else 'FALSE'
                path = c.get('path', '/')
                secure = 'TRUE' if c.get('secure') else 'FALSE'
                expires = c.get('expires', 0)
                if expires < 0: 
                    expires = 0 
                name = c.get('name', '')
                value = c.get('value', '')
                f.write(f"{domain}\t{include_sub}\t{path}\t{secure}\t{int(expires)}\t{name}\t{value}\n")     
        return cookie_file
    except Exception as e:
        logger.error(f"Ошибка конвертации куки: {e}")
        return None

def get_cover_info(url: str):
    """Извлекает прямую ссылку на обложку и название медиа"""
    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get('thumbnail')

def download_media(url: str, mode: str) -> str:
    """Синхронная функция скачивания через yt-dlp (видео или аудио)"""
    dynamic_name = str(random.randint(1000000, 99999999))
    ydl_opts = {
        'outtmpl': f'{dynamic_name}.%(ext)s', 
        'quiet': True,
        'no_warnings': True,
    }
    if 'instagram.com' in url.lower():
        cookie_path = sync_playwright_cookies()
        if cookie_path:
            ydl_opts['cookiefile'] = cookie_path

    if mode == 'video':
        ydl_opts['format'] = 'bestvideo[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[ext=mp4][vcodec^=avc]/best[ext=mp4]/best'
        ydl_opts['merge_output_format'] = 'mp4'
    else:
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['writethumbnail'] = True
        ydl_opts['postprocessors'] = [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            },
            {
                'key': 'EmbedThumbnail',
            }
        ]
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get('title', 'Unknown Media')
        filename = ydl.prepare_filename(info)
        if mode == 'audio':
            base_name, _ = os.path.splitext(filename)
            filename = f"{base_name}.mp3" 
        return filename, title

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user = message.from_user
    name = get_user_display_name(user)
    logger.info(f"[{user.id}] {name} начал использовать бота.")
    await message.answer(
        "Привет! Я бот для скачивания медиа.\n"
        "Отправь мне ссылку на YouTube, TikTok, Instagram или SoundCloud, и я предложу форматы для загрузки!"
    )

@dp.message(F.text.regexp(r'(?i)https?://(?:[a-zA-Z0-9-]+\.)*(tiktok\.com|youtube\.com|youtu\.be|instagram\.com|soundcloud\.com)/.*'))
async def handle_media_link(message: types.Message, state: FSMContext):
    url = message.text
    user = message.from_user
    name = get_user_display_name(user)
    logger.info(f"[{user.id}] {name} прислал ссылку: {url}")
    await state.update_data(media_url=url)

    if 'soundcloud.com' in url.lower():
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🖼 Скачать обложку трека", callback_data='cover')],
            [InlineKeyboardButton(text="🎵 Скачать трек", callback_data='audio')]
        ])
        await message.answer("Что именно нужно скачать?", reply_markup=keyboard) 
    
    elif 'tiktok.com' in url.lower():
        status_msg = await message.answer("⏳ Анализирую ссылку...")
        media_type = await check_tiktok_media_type(url)
        if media_type == 'photo':
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🖼 Альбомом (Быстро, со сжатием)", callback_data="tt_photos_album")],
                [InlineKeyboardButton(text="📁 Файлами (Оригинал, без сжатия)", callback_data="tt_photos_doc")],
                [InlineKeyboardButton(text="🎵 Скачать звук", callback_data="audio")]
            ])
        elif media_type == 'video':
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📹 Скачать видео", callback_data="video")],
                [InlineKeyboardButton(text="📁 Скачать видео без сжатия", callback_data="video_doc")],
                [InlineKeyboardButton(text="🎵 Скачать звук", callback_data="audio")]
            ])
        else:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📹 Скачать видео", callback_data="video")],
                [InlineKeyboardButton(text="🖼 Скачать фото (если это карусель)", callback_data="tiktok_photos")],
                [InlineKeyboardButton(text="🎵 Скачать звук", callback_data="audio")]
            ])
        await status_msg.edit_text("Что именно нужно скачать?", reply_markup=keyboard)
        
    elif 'instagram.com' in url.lower():
        if '/reel/' in url.lower() or '/tv/' in url.lower():
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📹 Скачать видео", callback_data='video')],
                [InlineKeyboardButton(text="📁 Скачать видео без сжатия", callback_data='video_doc')],
                [InlineKeyboardButton(text="🎵 Скачать звук", callback_data='audio')]
            ])
            await message.answer("Что именно нужно скачать?", reply_markup=keyboard)
        elif '/p/' in url.lower():
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🖼 Альбомом (Быстро, со сжатием)", callback_data='ig_photos_album')],
                [InlineKeyboardButton(text="📁 Файлами (Оригинал, без сжатия)", callback_data='ig_photos_doc')],
                [InlineKeyboardButton(text="🎵 Скачать звук", callback_data='audio')]
            ])
            await message.answer("Как именно скачать?", reply_markup=keyboard)
        else:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📹 Скачать видео", callback_data='video')],
                [InlineKeyboardButton(text="🖼 Скачать фото (Альбомом)", callback_data='ig_photos_album')],
                [InlineKeyboardButton(text="🎵 Скачать звук", callback_data='audio')]
            ])
            await message.answer("Что именно нужно скачать?", reply_markup=keyboard)

@dp.callback_query(F.data.in_({"video", "video_doc", "audio", "cover", "tiktok_photos", "tt_photos_album", "tt_photos_doc", "ig_photos_album", "ig_photos_doc"}))
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
    if mode == 'tiktok_photos':
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🖼 Альбомом (Быстро, со сжатием)", callback_data="tt_photos_album")],
            [InlineKeyboardButton(text="📁 Файлами (Оригинал, без сжатия)", callback_data="tt_photos_doc")],
            [InlineKeyboardButton(text="🎵 Скачать только звук", callback_data="audio")]
        ])
        await callback.message.edit_text(
            text="Как именно скачать?",
            reply_markup=keyboard
        )
        return

    await state.clear()
    status_text = {
        'video': "⏳ Скачиваю видео...",
        'video_doc': "⏳ Скачиваю видео (файлом)...",
        'audio': "⏳ Скачиваю аудио...",
        'cover': "⏳ Получаю обложку...",
        'tt_photos_album': "⏳ Ищу и скачиваю альбом...",
        'tt_photos_doc': "⏳ Ищу и скачиваю оригиналы фото...",
        'ig_photos_album': "⏳ Ищу и скачиваю фото...",
        'ig_photos_doc': "⏳ Скачиваю оригиналы фото..."
    }.get(mode, "⏳ Обработка...")
    status_msg = await callback.message.edit_text(status_text)

    try:
        if mode in ['tt_photos_album', 'tt_photos_doc']:
            is_doc = (mode == 'tt_photos_doc')
            downloaded_files = await get_tiktok_photos_and_download(media_url, user.id, as_doc=is_doc)
            if downloaded_files:
                media_group = MediaGroupBuilder(caption="Твои фото 📸" if not is_doc else None)
                for file in downloaded_files:
                    if is_doc:
                        media_group.add_document(media=FSInputFile(file)) 
                    else:
                        media_group.add_photo(media=FSInputFile(file))    
                try:
                    await callback.message.answer_media_group(media=media_group.build())
                except TelegramEntityTooLarge:
                    await callback.message.answer("❌ Альбом слишком большой для отправки.")
                except Exception as e:
                    logger.error(f"Ошибка отправки медиа: {e}")
                    await callback.message.answer("❌ Произошла ошибка при отправке фотографий.")
                finally:
                    for file in downloaded_files:
                        if os.path.exists(file):
                            os.remove(file)
            else:
                await callback.message.answer("❌ Не удалось скачать фотографии. Убедитесь, что это карусель с фото.")
            await status_msg.delete()
            return

        if mode in ['ig_photos_album', 'ig_photos_doc']:
            is_doc = (mode == 'ig_photos_doc')
            downloaded_files = await get_insta_photos(media_url, user.id, as_doc=is_doc)
            if downloaded_files:
                media_group = MediaGroupBuilder(caption="Твои фото 📸" if not is_doc else None)
                for file in downloaded_files:
                    if is_doc:
                        media_group.add_document(media=FSInputFile(file)) 
                    else:
                        media_group.add_photo(media=FSInputFile(file))    
                try:
                    await callback.message.answer_media_group(media=media_group.build())
                except TelegramEntityTooLarge:
                    await callback.message.answer("❌ Альбом слишком большой для отправки.")
                except Exception as e:
                    logger.error(f"Ошибка отправки Instagram медиа: {e}")
                    await callback.message.answer("❌ Произошла ошибка при отправке фотографий.")
                finally:
                    for file in downloaded_files:
                        if os.path.exists(file):
                            os.remove(file)
            else:
                await callback.message.answer("❌ Не удалось скачать фото. Убедитесь, что аккаунт открыт и это пост с картинками.")
            await status_msg.delete()
            return

        if mode == 'cover':
            cover_url = await asyncio.to_thread(get_cover_info, media_url)
            if cover_url:
                dynamic_name = str(random.randint(1000000, 99999999))
                cover_doc = URLInputFile(url=cover_url, filename=f"{dynamic_name}.jpg")
                await callback.message.answer_document(
                    document=cover_doc,
                    disable_content_type_detection=True
                )
            else:
                await callback.message.answer("❌ Не удалось найти обложку для этой ссылки.")
            await status_msg.delete()
            return

        if mode == 'audio' and 'tiktok' in media_url.lower():
            file_path = await get_tiktok_audio(media_url, user.id)
            title = f"TikTok_Audio_{random.randint(1000, 9999)}"
            if not file_path:
                await status_msg.edit_text("❌ Не удалось скачать аудио с TikTok. Возможно, звук удален.")
                return
        else:
            dl_mode = 'video' if mode in ('video', 'video_doc') else mode
            file_path, title = await asyncio.to_thread(download_media, media_url, dl_mode)   
            
        try:
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
            
            if mode == 'video':
                video_file = FSInputFile(file_path, filename=f"{safe_title}.mp4")
                await callback.message.answer_video(video=video_file, supports_streaming=True)
                
            elif mode == 'video_doc':
                document_file = FSInputFile(file_path, filename=f"{safe_title}.mp4")
                await callback.message.answer_document(document=document_file, disable_content_type_detection=True)
                
            elif mode == 'audio':
                audio_file = FSInputFile(file_path, filename=f"{safe_title}.mp3")
                await callback.message.answer_audio(audio=audio_file, title=safe_title) 
            logger.info(f"[{user.id}] {name} -> Успешно отправлен файл {mode} ({safe_title}).")
            await status_msg.delete()
        except TelegramEntityTooLarge:
            await status_msg.edit_text("❌ Файл слишком большой! Telegram позволяет отправлять файлы до 50 МБ.")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)      
    except Exception as e:
        logger.error(f"Error process_media [{mode}]: {e}")
        await status_msg.edit_text("❌ Произошла ошибка. Возможно, медиа удалено или недоступно.")

@dp.message()
async def handle_other_messages(message: types.Message):
    await message.answer("Пожалуйста, отправьте корректную ссылку на YouTube, TikTok, Instagram или SoundCloud.")

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

import os
import aiohttp
from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

async def get_tiktok_photos_and_download(url: str, user_id: int, as_doc: bool = False):
    """Скачивает фото. Если as_doc=True, сохраняет без сжатия Pillow."""
    print(f"\n--- ЗАПУСК API (TIKWM) ДЛЯ: {url} ---")
    try:
        downloaded_files = []
        api_url = "https://www.tikwm.com/api/"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params={"url": url, "hd": 1}, timeout=15) as resp:
                if resp.status != 200: return []
                data = await resp.json()
                if data.get("code") != 0: return []    
                images = data.get("data", {}).get("images", [])
                if not images: return []    
                print(f"✅ Найдено фотографий: {len(images)}")
                for idx, img_url in enumerate(images[:10]):
                    raw_filename = f"raw_photo_{user_id}_{idx}.webp"
                    final_filename = f"photo_{user_id}_{idx}.jpeg" if as_doc else f"photo_{user_id}_{idx}.jpg"
                    try:
                        async with session.get(img_url, timeout=15) as img_resp:
                            if img_resp.status == 200:
                                img_data = await img_resp.read()
                                if len(img_data) > 5000:
                                    with open(raw_filename, 'wb') as f:
                                        f.write(img_data) 
                                    if as_doc:
                                        os.rename(raw_filename, final_filename)
                                        downloaded_files.append(final_filename)
                                    else:
                                        img = Image.open(raw_filename)
                                        img.load()
                                        if img.mode != 'RGB':
                                            img = img.convert('RGB')
                                        img.save(final_filename, format="JPEG", quality=95)
                                        downloaded_files.append(final_filename)
                                        os.remove(raw_filename)
                    except Exception as e:
                        print(f"⚠️ Сбой при скачивании фото {idx}: {e}")
                    if os.path.exists(raw_filename):
                        os.remove(raw_filename)                    
        print("-----------------------------------")
        return downloaded_files
    except Exception as e:
        print(f"❌ Ошибка в загрузчике: {e}")
        return []

async def get_tiktok_audio(url: str, user_id: int):
    """Специальная функция для быстрого скачивания ТОЛЬКО аудио через TikWM"""
    print(f"\n--- ЗАПУСК API АУДИО (TIKWM) ДЛЯ: {url} ---")
    try:
        api_url = "https://www.tikwm.com/api/"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params={"url": url, "hd": 1}, timeout=15) as resp:
                if resp.status != 200: return None
                data = await resp.json()
                if data.get("code") != 0: return None  
                music_url = data.get("data", {}).get("music")
                if not music_url: return None  
                print("🎵 Ссылка на аудио найдена, скачиваю...")
                audio_filename = f"temp_audio_only_{user_id}.mp3"
                async with session.get(music_url, timeout=15) as audio_resp:
                    if audio_resp.status == 200:
                        with open(audio_filename, 'wb') as f:
                            f.write(await audio_resp.read())
                        print("✅ Аудио успешно сохранено!")
                        return audio_filename
        return None
    except Exception as e:
        print(f"❌ Ошибка при скачивании аудио: {e}")
        return None

async def check_tiktok_media_type(url: str) -> str:
    """Быстро определяет тип контента TikTok (фото или видео) до скачивания."""
    try:
        api_url = "https://www.tikwm.com/api/"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params={"url": url}, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("code") == 0:
                        if data.get("data", {}).get("images"):
                            return "photo"
                        else:
                            return "video"
    except Exception:
        pass
    return "unknown"

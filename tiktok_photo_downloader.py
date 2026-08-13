import os
import io
import aiohttp
import logging
import random
import asyncio
from PIL import Image, ImageFile
from cloakbrowser import launch_async
import yt_dlp

ImageFile.LOAD_TRUNCATED_IMAGES = True
logger = logging.getLogger('__main__')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

async def fetch_urls_via_cloakbrowser(url: str):
    """Скачивает фото TikTok через CloakBrowser обходя капчи"""
    logger.info(f"--- ЗАПУСК CLOAKBROWSER ДЛЯ: {url} ---")
    media_urls = []
    try:
        browser = await launch_async(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=HEADERS["User-Agent"]
        )
        page = await context.new_page()
        await page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["media", "font"] else route.continue_())
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        
        async def collect_images():
            urls = await page.evaluate('''() => {
                let images = Array.from(document.querySelectorAll('img'));
                let results = [];
                for (let img of images) {
                    let rect = img.getBoundingClientRect();
                    if (rect.width > 200 && rect.height > 200) {
                        let src = img.src || "";
                        // Ищем только реальные ссылки (начинаются на http), исключая base64 заглушки
                        if (src.startsWith("http") && (src.includes("tiktokcdn") || src.includes("tos-") || src.includes("image"))) {
                            results.push(src);
                        }
                    }
                }
                return results;
            }''')
            for src in urls:
                if src not in media_urls:
                    media_urls.append(src)
        await collect_images()
        for _ in range(15): 
            next_btn = await page.query_selector('button[class*="ArrowRight"], button[class*="arrow-right"]')
            if next_btn:
                await next_btn.click(force=True)
                await page.wait_for_timeout(300)
                await collect_images()
            else:
                await page.keyboard.press("ArrowRight")
                await page.wait_for_timeout(300)
                await collect_images()
        await browser.close()
    except Exception as e:
        logger.error(f"Ошибка CloakBrowser: {e}")
    return list(set(media_urls))

async def get_tiktok_photos_and_download(url: str, user_id: int, as_doc: bool = False):
    """Основная функция скачивания фото"""
    media_urls = await fetch_urls_via_cloakbrowser(url)
    if not media_urls:
        logger.warning("Фотографии TikTok не найдены.")
        return []
    logger.info(f"Найдено фото: {len(media_urls)}. Начинаю скачивание...")
    batch_id = random.randint(1000000, 99999999)
    connector = aiohttp.TCPConnector(limit=50, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=connector, headers=HEADERS) as session:

        async def fetch_and_process_photo(img_url, idx):
            final_filename = f"photo_{batch_id}_{idx}.jpeg" if as_doc else f"photo_{batch_id}_{idx}.jpg"
            try:
                async with session.get(img_url, timeout=10) as img_resp:
                    if img_resp.status == 200:
                        img_bytes = await img_resp.read()
                        if len(img_bytes) < 5000:
                            return None
                        if as_doc:
                            with open(final_filename, 'wb') as f:
                                f.write(img_bytes)
                            return final_filename
                        else:
                            def convert_in_memory(raw_bytes):
                                with Image.open(io.BytesIO(raw_bytes)) as img:
                                    if img.mode != 'RGB':
                                        img = img.convert('RGB')
                                    img.save(final_filename, format="JPEG", quality=95)
                            await asyncio.to_thread(convert_in_memory, img_bytes)
                            return final_filename
            except Exception as e:
                logger.warning(f"Ошибка при скачивании фото {idx}: {e}")
            return None
        tasks = [fetch_and_process_photo(img_url, idx) for idx, img_url in enumerate(media_urls)]
        results = await asyncio.gather(*tasks)
        downloaded_files = [res for res in results if res is not None]
    logger.info(f"--- ЗАВЕРШЕНО: {len(downloaded_files)} фото скачано ---")
    return downloaded_files

async def get_tiktok_audio(url: str, user_id: int):
    """Скачивает аудио с TikTok через yt-dlp"""
    logger.info(f"--- ЗАПУСК YT-DLP ДЛЯ АУДИО TIKTOK: {url} ---")
    try:
        final_url = url
        if '/@' not in url:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, allow_redirects=True, timeout=10) as resp:
                    final_url = str(resp.url)
        if '/photo/' in final_url:
            final_url = final_url.replace('/photo/', '/video/')

        def download_audio_sync(target_url):
            dynamic_name = f"tiktok_audio_{random.randint(1000000, 99999999)}"
            ydl_opts = {
                'outtmpl': f'{dynamic_name}.%(ext)s',
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target_url, download=True)
                filename = ydl.prepare_filename(info)
                base_name, _ = os.path.splitext(filename)
                return f"{base_name}.mp3"
        file_path = await asyncio.to_thread(download_audio_sync, final_url)
        if file_path and os.path.exists(file_path):
            return file_path
    except Exception as e:
        logger.error(f"Ошибка при скачивании аудио TikTok: {e}")
    return None

async def check_tiktok_media_type(url: str) -> str:
    """Быстро определяет тип контента TikTok"""
    if '/photo/' in url.lower():
        return "photo"
    if '/video/' in url.lower() or '/v/' in url.lower():
        return "video"
    try:
        process = await asyncio.create_subprocess_exec(
            'curl', '-s', url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            html_content = stdout.decode('utf-8', errors='ignore')
            if '/photo/' in html_content.lower():
                return "photo"
            elif '/video/' in html_content.lower() or '/v/' in html_content.lower():
                return "video"
        else:
            logger.warning(f"curl завершился с ошибкой: {stderr.decode('utf-8', errors='ignore')}") 
    except Exception as e:
        logger.error(f"Ошибка при проверке типа через curl: {e}")
    return "unknown"

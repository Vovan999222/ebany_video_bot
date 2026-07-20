import os
import aiohttp
import logging
import random
import asyncio
from PIL import Image, ImageFile
from cloakbrowser import launch_async
import yt_dlp

ImageFile.LOAD_TRUNCATED_IMAGES = True
logger = logging.getLogger('__main__')

async def get_tiktok_photos_and_download(url: str, user_id: int, as_doc: bool = False):
    """Скачивает фото TikTok через CloakBrowser обходя капчи"""
    logger.info(f"--- ЗАПУСК БРАУЗЕРА (CLOAKBROWSER) ДЛЯ TIKTOK: {url} ---")
    downloaded_files = []
    media_urls = []
    try:
        browser = await launch_async(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["media", "font"] else route.continue_())
        logger.info("Открываю страницу TikTok...")
        await page.goto(url, wait_until="domcontentloaded")
        try:
            await page.wait_for_selector("#__UNIVERSAL_DATA_FOR_REHYDRATION__, #SIGI_STATE", timeout=2000)
        except:
            await page.wait_for_timeout(1000)
        json_urls = await page.evaluate('''() => {
            try {
                let script = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');
                if (script) {
                    let data = JSON.parse(script.textContent);
                    let itemStruct = data["__DEFAULT_SCOPE__"]["webapp.video-detail"]["itemInfo"]["itemStruct"];
                    if (itemStruct && itemStruct.imagePost && itemStruct.imagePost.images) {
                        return itemStruct.imagePost.images.map(img => img.imageURL.urlList[0]);
                    }
                }
                let sigiScript = document.getElementById('SIGI_STATE');
                if (sigiScript) {
                    let data = JSON.parse(sigiScript.textContent);
                    let itemModule = data.ItemModule;
                    if (itemModule) {
                        let keys = Object.keys(itemModule);
                        for (let key of keys) {
                            let item = itemModule[key];
                            if (item.imagePost && item.imagePost.images) {
                                return item.imagePost.images.map(img => img.imageURL.urlList[0]);
                            }
                        }
                    }
                }
            } catch (e) {
                console.error(e);
            }
            return null;
        }''')
        if json_urls and len(json_urls) > 0:
            logger.info("Фотографии успешно найдены через внутренний JSON TikTok.")
            media_urls.extend(json_urls)
        else:
            logger.info("JSON не найден. Пробую собрать фото через перелистывание DOM...")
            
            async def collect_images():
                urls = await page.evaluate('''() => {
                    let images = Array.from(document.querySelectorAll('img'));
                    let results = [];
                    for (let img of images) {
                        let rect = img.getBoundingClientRect();
                        if (rect.width > 200 && rect.height > 200) {
                            let src = img.src || "";
                            if (src.includes("tiktokcdn") || src.includes("tos-") || src.includes("image")) {
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
        logger.error(f"Ошибка в CloakBrowser загрузчике TikTok: {e}")
        return []
    if not media_urls:
        logger.warning("Фотографии TikTok не найдены.")
        return []
    logger.info(f"Найдено фотографий (TikTok): {len(media_urls)}")
    batch_id = random.randint(1000000, 99999999)

    async def fetch_tiktok_photo(session, img_url, idx):
        raw_filename = f"raw_photo_{batch_id}_{idx}.webp"
        final_filename = f"photo_{batch_id}_{idx}.jpeg" if as_doc else f"photo_{batch_id}_{idx}.jpg"
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            async with session.get(img_url, headers=headers, timeout=15) as img_resp:
                if img_resp.status == 200:
                    img_data = await img_resp.read()
                    if len(img_data) > 5000:
                        with open(raw_filename, 'wb') as f:
                            f.write(img_data) 
                        if as_doc:
                            os.rename(raw_filename, final_filename)
                            return final_filename
                        else:
                            def process_image():
                                img = Image.open(raw_filename)
                                img.load()
                                if img.mode != 'RGB':
                                    img = img.convert('RGB')
                                img.save(final_filename, format="JPEG", quality=95)

                            await asyncio.to_thread(process_image)
                            logger.info(f"Скачано фото {idx + 1}")
                            return final_filename
        except Exception as e:
            logger.warning(f"Сбой при скачивании фото {idx}: {e}")
        finally:
            if os.path.exists(raw_filename):
                os.remove(raw_filename)
        return None

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_tiktok_photo(session, url, idx) for idx, url in enumerate(media_urls)]
        results = await asyncio.gather(*tasks)
        downloaded_files = [res for res in results if res is not None]
    logger.info("--- ЗАВЕРШЕНИЕ ОБРАБОТКИ ФОТО (CLOAKBROWSER) ---")
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
                    logger.info(f"Полная ссылка: {final_url}")
        if '/photo/' in final_url:
            final_url = final_url.replace('/photo/', '/video/')
            logger.info(f"URL изменен для совместимости с yt-dlp: {final_url}")

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
            logger.info("Аудио TikTok успешно сохранено через yt-dlp!")
            return file_path
    except Exception as e:
        logger.error(f"Ошибка при скачивании аудио TikTok (yt-dlp): {e}")
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

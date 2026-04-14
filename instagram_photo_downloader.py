import os
import asyncio
import aiohttp
import logging
import random
from PIL import Image, ImageFile
from playwright.async_api import async_playwright

ImageFile.LOAD_TRUNCATED_IMAGES = True

IG_USERNAME = ""
IG_PASSWORD = ""

STATE_FILE = "ig_browser_state.json"
logger = logging.getLogger('__main__')

async def get_insta_photos(url: str, user_id: int, as_doc: bool = False):
    logger.info(f"--- ЗАПУСК БРАУЗЕРА (STEALTH MODE) ДЛЯ: {url} ---")
    downloaded_files = []
    media_urls = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            'locale': "en-US",
            'timezone_id': "Europe/Kiev"
        }
        if os.path.exists(STATE_FILE):
            logger.info("Загружаю сохраненную сессию...")
            context_options['storage_state'] = STATE_FILE
        context = await browser.new_context(**context_options)
        page = await context.new_page()

        try:
            if not os.path.exists(STATE_FILE):
                logger.info("Сессия не найдена. Перехожу на страницу входа...")
                await page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded")
                await page.wait_for_timeout(5000)
                cookie_btn = await page.query_selector("button:has-text('Allow all cookies'), button:has-text('Принять все')")
                if cookie_btn:
                    await cookie_btn.click()
                    await page.wait_for_timeout(2000)
                logger.info("Ввожу логин и пароль...")
                await page.wait_for_selector("input", timeout=10000)
                inputs = await page.locator("input").all()
                if len(inputs) >= 2:
                    await inputs[0].fill(IG_USERNAME)
                    await page.wait_for_timeout(1000)
                    await inputs[1].fill(IG_PASSWORD)
                    await page.wait_for_timeout(500)
                    await inputs[1].press("Enter")
                    logger.info("Жду ответа от Инстаграма...")
                    await page.wait_for_timeout(6000)
                    two_factor_input = page.locator("input[name='verificationCode'], input[aria-label*='Security Code'], input[aria-label*='Код безопасности']")
                    if await two_factor_input.count() > 0:
                        logger.warning("ИНСТАГРАМ ЗАПРОСИЛ КОД ПОДТВЕРЖДЕНИЯ (2FA)!")
                        print("ИНСТАГРАМ ЗАПРОСИЛ КОД ПОДТВЕРЖДЕНИЯ (2FA)!")
                        choice_prompt = (
                            "Как подтвердить вход?\n"
                            "1 - Код из SMS/WhatsApp (6 цифр)\n"
                            "2 - Резервный код (8 цифр)\n"
                            "Введи 1 или 2 и нажми Enter: "
                        )
                        choice = await asyncio.to_thread(input, choice_prompt)
                        if choice.strip() == '2':
                            logger.info("Ищу ссылку для ввода резервного кода...")
                            backup_link = page.locator("text=/резервных кодов|backup codes|recovery codes/i")
                            if await backup_link.count() > 0:
                                await backup_link.first.click()
                                await page.wait_for_timeout(2000)
                                recovery_input = page.locator("input[name='recoveryCode'], input[name='verificationCode']")
                                if await recovery_input.count() > 0:
                                    code = await asyncio.to_thread(input, "Введи 8-значный резервный код: ")
                                    await recovery_input.first.fill(code.strip())
                                else:
                                    logger.warning("Не нашел специальное поле, ввожу код вслепую...")
                                    code = await asyncio.to_thread(input, "Введи 8-значный резервный код: ")
                                    await page.keyboard.type(code.strip())
                            else:
                                logger.warning("Не нашел ссылку на резервные коды на странице. Пробую ввести как обычный код.")
                                code = await asyncio.to_thread(input, "Введи код: ")
                                await two_factor_input.first.fill(code.strip())
                        else:
                            code = await asyncio.to_thread(input, "Введи код из SMS/WhatsApp: ")
                            await two_factor_input.first.fill(code.strip())
                        await page.wait_for_timeout(1000)
                        confirm_btn = page.locator("button:has-text('Confirm'), button:has-text('Подтвердить'), button[type='button']")
                        if await confirm_btn.count() > 0:
                            await confirm_btn.first.click()
                        else:
                            await page.keyboard.press("Enter")
                        logger.info("Отправляю код...")
                        await page.wait_for_timeout(6000)

                    logger.info("Жду загрузки главной страницы...")
                    await page.wait_for_url("**/", timeout=20000)
                    await page.wait_for_timeout(5000)
                    await context.storage_state(path=STATE_FILE)
                    logger.info("Вход выполнен! Сессия сохранена.")
                else:
                    raise Exception("Поля ввода не найдены.")

            logger.info("Загружаю пост...")
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
            await page.keyboard.press("Escape")

            async def collect():
                urls = await page.evaluate('''() => {
                    let images = Array.from(document.querySelectorAll('img'));
                    if (images.length === 0) return [];
                    let anchorImg = null;
                    let maxArea = 0;
                    for (let img of images) {
                        let rect = img.getBoundingClientRect();
                        let area = rect.width * rect.height;
                        if (area > maxArea && rect.width > 200) {
                            maxArea = area;
                            anchorImg = img;
                        }
                    }
                    if (!anchorImg) return [];
                    let anchorRect = anchorImg.getBoundingClientRect();
                    let results = [];
                    for (let img of images) {
                        let rect = img.getBoundingClientRect();
                        let isSameRow = Math.abs(rect.top - anchorRect.top) < 15;
                        let isSameHeight = Math.abs(rect.height - anchorRect.height) < 15;
                        if (isSameRow && isSameHeight) {
                            let src = img.src || "";
                            if (!src.match(/(scontent|fbcdn|instagram|cdn)/i)) continue;

                            let best_url = src;
                            if (img.srcset) {
                                let parts = img.srcset.split(',');
                                let last_part = parts[parts.length - 1].trim().split(' ')[0];
                                if (last_part && last_part.match(/(scontent|fbcdn|instagram|cdn)/i)) {
                                    best_url = last_part;
                                }
                            }
                            results.push(best_url);
                        }
                    }
                    return results;
                }''')
                for src in urls:
                    if src not in media_urls:
                        media_urls.append(src)
            logger.info("Ищу главную фотографию и собираю карусель...")
            await collect()
            for _ in range(10):
                next_btn = await page.query_selector("button[aria-label='Next'], button[aria-label='Далее'], ._afxw")
                if next_btn:
                    await next_btn.click(force=True)
                    await page.wait_for_timeout(1500)
                    await collect()
                else:
                    break
        except Exception as e:
            logger.error(f"Ошибка при работе с Playwright: {e}")
            await page.screenshot(path="debug_error.png")
        finally:
            await browser.close()
        if not media_urls:
            logger.warning("Фотографии не найдены. Если это видео (Reel), используй кнопку 'Скачать видео'.")
            return []
        logger.info(f"Успех! Радар захватил целевых фотографий: {len(media_urls)}. Начинаю загрузку...")
        batch_id = random.randint(1000000, 99999999)

        async with aiohttp.ClientSession() as session:
            for idx, img_url in enumerate(media_urls[:10]):
                final_filename = f"ig_{batch_id}_{idx}.jpeg" if as_doc else f"ig_{batch_id}_{idx}.jpg"
                try:
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                    async with session.get(img_url, headers=headers, timeout=15) as resp:
                        if resp.status == 200:
                            img_data = await resp.read()
                            if len(img_data) > 5000:
                                with open(final_filename, 'wb') as f:
                                    f.write(img_data)
                                downloaded_files.append(final_filename)
                                logger.info(f"Скачано фото {idx + 1}")
                            else:
                                logger.warning(f"Файл {idx} отбракован (слишком мал).")
                except Exception as e:
                    logger.error(f"Ошибка скачивания файла {idx}: {e}")      
        return downloaded_files

# ebany video bot

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python)
![Telegram](https://img.shields.io/badge/Telegram-Bot-2CA5E0?style=for-the-badge&logo=telegram)
![yt-dlp](https://img.shields.io/badge/yt--dlp-Enabled-red?style=for-the-badge&logo=youtube)
![FFmpeg](https://img.shields.io/badge/FFmpeg-Enabled-green?style=for-the-badge&logo=ffmpeg)
![Playwright](https://img.shields.io/badge/Playwright-Enabled-45ba4b?style=for-the-badge&logo=Playwright)

This Telegram bot is designed to easily download media files via links from popular social networks.

The bot automatically downloads videos in the best available quality, adapts them for Telegram's native player, extracts audio tracks, and seamlessly handles TikTok and Instagram photos.

## Features

**Multi-platform**:
* Supports links from **YouTube** (including Shorts), **TikTok**, **Instagram** (Reels/Posts), and **SoundCloud**.
* Offers a choice: download as **Video** or **Audio**. (For SoundCloud, you can also download the **Cover Art**).

**Smart TikTok & Instagram Integration**:
* **Auto-detection**: Automatically detects if a link is a standard video or a Photo Carousel and provides context-aware menus.
* **Photo**: Download photos as a native Telegram Album (compressed for quick viewing) or as uncompressed Document files (original quality).
* Bypasses captchas and extracts watermark-free media and original MP3 audio via the TikWM API and headless browser scraping.

**Video Processing**:
* Forced conversion and codec selection to **H.264 (MP4)** for seamless playback directly in the Telegram chat.
* Supports video streaming (users can start watching before the file is fully downloaded to the cache).
* Original quality preserved: videos are sent as uncompressed documents to avoid Telegram's built-in compression.

**Audio & Metadata Extraction**:
* Converts audio tracks to **MP3** format (320kbps).
* Automatically embeds high-quality cover art and metadata directly into downloaded MP3 files using `yt-dlp` postprocessors.

**Logging**:
* Maintains detailed logs with daily rotation in the `logs/` directory.

**Asynchronous**:
* Downloading files does not block the bot's operation for other users, thanks to `asyncio.to_thread` and `aiohttp`.

## Requirements

To run the bot, you need:

1.  **Python 3.8+**
2.  **FFmpeg** (system-level) — critical for `yt-dlp` to work properly (merging video and audio, codec conversion).

### Installing FFmpeg:

**Ubuntu/Debian**:
```bash
sudo apt update && sudo apt upgrade && sudo apt install ffmpeg
```

**Windows**:
* **Method 1 (Recommended):** Open a terminal (PowerShell or CMD) and run:
```cmd
winget install Gyan.FFmpeg
```
> **⚠️ "winget" command not found?** > If you are using an older version of Windows 10, download and install the **App Installer** from the [official GitHub releases](https://github.com/microsoft/winget-cli/releases) (look for the `.msixbundle` file).

* **Method 2 (Manual):** Download the archive from the [official repository](https://github.com/GyanD/codexffmpeg/releases), unzip it, and add the path to the `bin` folder to your system environment variables (PATH).
```cmd
C:\ffmpeg\bin
```

**MacOS**:
```bash
brew install ffmpeg
```

## Installation & Usage

### 1. Clone the repository

```bash
git clone https://github.com/Vovan999222/ebany_video_bot.git

cd ebany_video_bot
```

### 2. Create a virtual environment (Recommended)

```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate
```

### 3. Install dependencies

You can install the libraries manually:

```bash
pip install aiogram yt-dlp Pillow aiohttp playwright
```

**⚠️ Important step for Playwright (Instagram module):**
After installing the Python package, you must install the Chromium browser binaries and system dependencies:
```bash
playwright install chromium
# If you are installing on a clean Linux server (e.g., Ubuntu), also run:
playwright install-deps
```

Or create a `requirements.txt` file and install via:
```bash
pip install -r requirements.txt
```

### 4. Configuration

1. Open the `config.py` file and insert your bot token from @BotFather:
   ```python
   TOKEN = ""
   ```
2. Open `instagram_photo_downloader.py` and insert your Instagram credentials for the scraper to work:
   ```python
   IG_USERNAME = ""
   IG_PASSWORD = ""
   ```

### 5. First run & Instagram Login (2FA)

When downloading from Instagram for the first time, the bot will launch a hidden browser and attempt to log in. 
**Watch the terminal!** If Instagram asks for a 2FA (Two-Factor Authentication) code, the bot will pause and prompt you in the console:
```text
ИНСТАГРАМ ЗАПРОСИЛ КОД ПОДТВЕРЖДЕНИЯ (2FA)!
Введи код из SMS/WhatsApp и нажми Enter:
```
Once you enter the code, the session will be saved to `ig_browser_state.json`. All future downloads will work automatically without requiring passwords or codes.

### 6. Run the bot

```bash
python bot.py
```

## Technical Details

* **Limits**: The bot processes and sends files up to **50 MB** (Telegram Bot API restriction).
* **Video**: `yt-dlp` settings are forced to request `bestvideo[ext=mp4][vcodec^=avc]` format to exclude AV1/VP9 codecs, which are not supported by Telegram's in-app player.
* **Audio**: Processed via `FFmpegExtractAudio` with the MP3 codec.
* **TikTok Parsing**: Uses `aiohttp` to communicate with the TikWM API for fast, captcha-free data extraction. `Pillow` is used to process raw WebP image chunks and safely convert them to standard JPEGs.
* **Instagram Scraping**: Uses `playwright` in stealth mode to bypass Meta's scraping restrictions. Employs a custom "Visual Radar" algorithm to detect and extract high-quality carousel images based on DOM rendering size, ignoring recommendations and avatars.
* **Concurrency & Race Conditions**: Implements random dynamic batch ID generation (`uuid`/`random`) for downloaded files to prevent race conditions when users send multiple links simultaneously.

## License

This project is distributed under the [MIT License](https://raw.githubusercontent.com/Vovan999222/ebany_video_bot/refs/heads/main/LICENSE).

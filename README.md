# ebany video bot

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python)
![Telegram](https://img.shields.io/badge/Telegram-Bot-2CA5E0?style=for-the-badge&logo=telegram)
![yt-dlp](https://img.shields.io/badge/yt--dlp-Enabled-red?style=for-the-badge&logo=youtube)
![FFmpeg](https://img.shields.io/badge/FFmpeg-Enabled-green?style=for-the-badge&logo=ffmpeg)

This Telegram bot is designed to easily download media files via links from popular social networks.

The bot automatically downloads videos in the best available quality, adapts them for Telegram's native player, and can also extract audio tracks.

## Features

* **Multi-platform**:
    * Supports links from **YouTube** (including Shorts), **TikTok**, and **Instagram** (Reels/Posts).
    * Offers a choice: download as **Video** or **Audio**.
* **Video Processing**:
    * Forced conversion and codec selection to **H.264 (MP4)** for seamless playback directly in the Telegram chat.
    * Supports video streaming (users can start watching before the file is fully downloaded to the cache).
* **Audio Extraction**:
    * Converts audio tracks to **MP3** format (320kbps).
* **Logging**:
    * Maintains detailed logs with daily rotation in the `logs/` directory.
* **Asynchronous**:
    * Downloading files does not block the bot's operation for other users, thanks to `asyncio.to_thread`.

## Requirements

To run the bot, you need:

1.  **Python 3.8+**
2.  **FFmpeg** (system-level) — critical for `yt-dlp` to work properly (merging video and audio, codec conversion).

### Installing FFmpeg:

* **Ubuntu/Debian**: `sudo apt update && sudo apt upgrade && sudo apt install ffmpeg`
* **Windows**:
    * **Method 1 (Recommended):** Open a terminal (PowerShell or CMD) and run:
      ```cmd
      winget install Gyan.FFmpeg
      ```
      > **⚠️ "winget" command not found?** > If you are using an older version of Windows 10, download and install the **App Installer** from the [official GitHub releases](https://github.com/microsoft/winget-cli/releases) (look for the `.msixbundle` file).
    
    * **Method 2 (Manual):** Download the archive from the [official repository](https://github.com/GyanD/codexffmpeg/releases), unzip it, and add the path to the `bin` folder to your system environment variables (PATH).
      ```cmd
      C:\ffmpeg\bin
      ```
* **MacOS**: `brew install ffmpeg`

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
pip install aiogram yt-dlp
```

Or create a `requirements.txt` file and install via:

```bash
pip install -r requirements.txt
```

### 4. Configuration

Open the `config.py` file and find the following line:

```python
TOKEN = ""  # Paste your token from @BotFather here
```

Insert your bot token inside the quotes.

### 5. Run the bot

```bash
python bot.py
```

## Technical Details

* **Limits**: The bot processes and sends files up to **50 MB** (Telegram Bot API restriction).
* **Video**: `yt-dlp` settings are forced to request `bestvideo[ext=mp4][vcodec^=avc]` format to exclude AV1/VP9 codecs, which are not supported by Telegram's in-app player.
* **Audio**: Processed via `FFmpegExtractAudio` with the MP3 codec.

## License

This project is distributed under the [MIT License](https://raw.githubusercontent.com/Vovan999222/ebany_video_bot/refs/heads/main/LICENSE).
```

# Telegram Music Bot with Spotify Playlist Support 🎵

A **fully functional** Telegram music bot that plays music in voice chats with support for importing entire Spotify playlists!

## ⚡ Quick Start

```bash
# 1. Clone/download the repository
# 2. Install FFmpeg (see Prerequisites)
# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure .env
# On Windows:
copy .env.example .env
# On Linux/Mac:
cp .env.example .env
# Edit .env with your credentials

# 5. Test setup (optional but recommended)
python test_setup.py

# 6. Run the bot
python telegram_music_bot.py
```

**For Windows users:**
```powershell
# 1. Clone/download the repository
# 2. Install FFmpeg (see Prerequisites)
# 3. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 4. Copy and configure .env
copy .env.example .env
# Edit .env with your credentials

# 5. Test setup (optional but recommended)
python test_setup.py

# 6. Run the bot
python telegram_music_bot.py
```

## Features

- 🎵 Play songs by name in voice chats
- 📋 Import and play entire Spotify playlists
- ⏸️ Pause/Resume playback
- ⏭️ Skip songs
- 📝 View queue (up to 20 songs display)
- 🎶 Now playing info
- 🗑️ Clear queue
- ⏹️ Stop playback and leave voice chat
- 🔄 Auto-play next song when current finishes
- 👥 Works in groups and channels

## Prerequisites

### System Requirements

1. **Python 3.8+** installed
2. **FFmpeg** installed on your system (REQUIRED for audio processing):
   - **Windows**: 
     - Download from [ffmpeg.org](https://ffmpeg.org/download.html)
     - Extract and add to PATH
     - Or use: `choco install ffmpeg` (if you have Chocolatey)
     - Alternative: `winget install Gyan.FFmpeg`
   - **Linux**: 
     ```bash
     sudo apt update
     sudo apt install ffmpeg
     ```
   - **Mac**: 
     ```bash
     brew install ffmpeg
     ```

3. **Visual C++ Build Tools** (for Windows users):
   - Some packages require compilation
   - Download from [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
   - Or install Visual Studio with C++ support

4. **Verify installations**:
   ```bash
   ffmpeg -version
   python --version
   ```

## Setup Guide

### 1. Get Telegram Bot Token

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow instructions to create your bot
4. Copy the bot token (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Send `/setjoingroups` to @BotFather and enable it
6. Send `/setprivacy` to @BotFather and disable it

### 2. Get Telegram API Credentials

1. Go to [https://my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Click on "API Development Tools"
4. Fill in the form (app title and short name can be anything)
5. Copy your **API_ID** (number) and **API_HASH** (string)

### 3. Get Spotify API Credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account
3. Click "Create an App"
4. Fill in app name and description
5. Copy your **Client ID** and **Client Secret**

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

**Important**: If you encounter errors with `py-tgcalls`, install build dependencies:
- **Linux**: `sudo apt install python3-dev`
- **Mac**: `xcode-select --install`

### 5. Configure Environment Variables

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials:
   ```env
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   API_ID=12345678
   API_HASH=abcdef1234567890abcdef1234567890
   SPOTIFY_CLIENT_ID=your_spotify_client_id
   SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
   ```

### 6. Test Your Setup (Optional but Recommended)

Run the test script to verify everything is configured correctly:

```bash
python test_setup.py
```

This will check:
- All required packages are installed
- FFmpeg is available
- .env file has all credentials
- Spotify API is working
- YouTube search is working

### 7. Run the Bot

```bash
python telegram_music_bot.py
```

You should see:
```
🚀 Starting bot...
✅ Pyrogram client started
✅ PyTgCalls started
🤖 Bot is running!
📝 Make sure to:
   1. Add bot to your group
   2. Make bot admin with 'Manage Voice Chats' permission
   3. Start a voice chat in the group
   4. Use /play command to start playing music
```

## Usage

### Setting Up Your Group

1. Add the bot to your Telegram group
2. Make the bot an **admin** with these permissions:
   - ✅ Manage Voice Chats
   - ✅ Delete Messages (optional)
   - ✅ Ban Users (optional)
3. Start a voice chat in the group
4. Use bot commands!

### Commands

- `/start` - Show welcome message and all commands
- `/play <song name>` - Play a song in voice chat
- `/play <spotify playlist link>` - Play entire Spotify playlist
- `/pause` - Pause current playback
- `/resume` - Resume paused playback
- `/skip` - Skip current song and play next
- `/np` - Show now playing information
- `/queue` - Show current queue (max 20 songs displayed)
- `/clear` - Clear entire queue and stop
- `/stop` - Stop playing and leave voice chat

### Examples

**Play a single song:**
```
/play Bohemian Rhapsody Queen
```

**Play a Spotify playlist:**
```
/play https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M
```

**Pause and resume:**
```
/pause
/resume
```

**Check what's playing:**
```
/np
```

## How It Works

### Single Song Flow
1. User sends `/play Bohemian Rhapsody`
2. Bot searches YouTube for the song
3. Bot joins voice chat (if not already in)
4. Bot streams audio directly to voice chat using MediaStream
5. When song ends, `on_stream_end` event fires automatically
6. Bot plays next song in queue

### Playlist Flow
1. User sends `/play <spotify playlist link>`
2. Bot fetches all tracks from Spotify using your credentials
3. Bot extracts song names and artist names
4. All songs are added to the queue
5. Bot searches YouTube for each song when it's time to play
6. Songs play in order automatically via the event handler

### Technical Details
- Uses **PyTgCalls** for voice chat integration with proper event handlers
- Uses **yt-dlp** to search and get stream URLs from YouTube
- Uses **Spotipy** to fetch playlist data from Spotify API
- Audio is streamed directly via `MediaStream` (not downloaded)
- FFmpeg handles audio processing in the background
- Each chat has its own independent queue
- **Event-driven architecture**: `@calls.on_stream_end()` decorator handles automatic progression
- Proper async/await flow prevents race conditions

## Troubleshooting

### Bot not responding
- ✓ Check if bot token is correct in `.env`
- ✓ Ensure bot is running without errors in terminal
- ✓ Make sure you're using commands in a group, not private chat

### Bot can't join voice chat
- ✓ Make sure voice chat is active in the group
- ✓ Bot must be admin with "Manage Voice Chats" permission
- ✓ Check API_ID and API_HASH are correct
- ✓ Delete `music_bot.session` file and restart if it exists

### Playlist not loading
- ✓ Verify Spotify credentials are correct
- ✓ Check if playlist is **public** (private playlists won't work)
- ✓ Ensure playlist link is valid
- ✓ Test with: `https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M`

### Songs not playing / No audio
- ✓ **FFmpeg must be installed** - run `ffmpeg -version` to verify
- ✓ Check internet connection
- ✓ Verify yt-dlp is working: `yt-dlp --version`
- ✓ Some videos may be region-blocked
- ✓ Try a different song if one doesn't work

### "GroupCallNotFound" error
- ✓ Start a voice chat in the group first
- ✓ Make sure bot is admin
- ✓ Bot must have "Manage Voice Chats" permission

### Installation errors
- ✓ Update pip: `pip install --upgrade pip`
- ✓ Install build tools:
  - Linux: `sudo apt install python3-dev build-essential`
  - Mac: `xcode-select --install`
  - Windows: Install [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
- ✓ For TgCrypto installation issues on Windows:
  - Try: `pip install --upgrade py-tgcalls` and `pip install pyrogram`
  - TgCrypto is optional - Pyrogram will work with pure Python crypto (slower but functional)
  - If TgCrypto fails to install, the bot will still work but with reduced performance
- ✓ If you get compiler errors, try installing pre-compiled wheels:
  - `pip install --only-binary=all -r requirements.txt`

## Advanced Configuration

### Queue Size Limit
Currently unlimited. To add a limit, modify the `play()` function:
```python
MAX_QUEUE_SIZE = 50
if len(music_queue[chat_id]) >= MAX_QUEUE_SIZE:
    await update.message.reply_text("Queue is full!")
    return
```

### Auto-leave after inactivity
Add this to the `stop()` function:
```python
# Leave after 5 minutes of no activity
await asyncio.sleep(300)
await pytgcalls.leave_group_call(chat_id)
```

### Multiple Bot Instances
To run multiple bots:
1. Copy the folder
2. Create new bot with @BotFather
3. Use different `.env` file
4. Change session name in code: `Client("music_bot_2", ...)`

## File Structure

```
telegram-music-bot/
├── telegram_music_bot.py    # Main bot code
├── spotify.py                # Original Spotify parser (standalone)
├── requirements.txt          # Python dependencies
├── .env                      # Your credentials (don't share!)
├── .env.example              # Template for credentials
├── .gitignore               # Git ignore file
├── README.md                # This file
└── music_bot.session        # Auto-generated session file (ignored by git)
```

## Notes & Limitations

- Bot can only be in one voice chat per group at a time
- Streaming quality depends on YouTube video quality
- Some songs may not be available due to regional restrictions
- Playlist import works only with **public** Spotify playlists
- Bot requires stable internet connection
- Queue display limited to 15 songs (can be changed in code)

## What Makes This Version Fully Working?

This implementation includes critical fixes that make it production-ready:

1. **Event-Driven Architecture**: Uses `@calls.on_stream_end()` decorator to automatically play next song when current finishes
2. **Proper Async Handling**: Correct use of async/await prevents blocking and race conditions
3. **MediaStream API**: Uses the correct `MediaStream` class instead of deprecated `AudioPiped`
4. **Error Recovery**: Handles GroupCallNotFound, NoActiveGroupCall, and other exceptions gracefully
5. **State Management**: Properly tracks playing state, queue, and currently playing info per chat
6. **Session Handling**: Correctly initializes Pyrogram and PyTgCalls in the right order
7. **API ID Conversion**: Converts API_ID to int (required by Pyrogram)
8. **Test Suite**: Includes `test_setup.py` to catch configuration issues before running
9. **Better UX**: Uses Markdown formatting, proper emoji, and informative messages
10. **Clean Shutdown**: Handles Ctrl+C gracefully

## Security

- Never share your `.env` file
- Keep your bot token private
- Don't commit credentials to git
- Use `.gitignore` to exclude sensitive files

## Contributing

Found a bug? Have a feature request? Feel free to:
1. Open an issue
2. Submit a pull request
3. Fork and modify for your needs

## Credits

Built with:
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [py-tgcalls](https://github.com/pytgcalls/pytgcalls)
- [Pyrogram](https://github.com/pyrogram/pyrogram)
- [spotipy](https://github.com/spotipy-dev/spotipy)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

## License

MIT License - feel free to modify and use as needed!

---

**Enjoy your music bot! 🎵**

For support, make sure FFmpeg is installed and bot is admin in your group!
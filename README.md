\# Telegram Music Bot with Spotify Playlist Support



A Telegram bot that plays music from YouTube and supports importing entire Spotify playlists.



\## Features



\- 🎵 Play songs by name

\- 📋 Import and play entire Spotify playlists

\- ⏭️ Skip songs

\- 📝 View queue

\- 🗑️ Clear queue

\- ⏹️ Stop playback



\## Prerequisites



1\. \*\*Python 3.8+\*\* installed

2\. \*\*FFmpeg\*\* installed on your system:

&nbsp;  - Windows: Download from \[ffmpeg.org](https://ffmpeg.org/download.html)

&nbsp;  - Linux: `sudo apt install ffmpeg`

&nbsp;  - Mac: `brew install ffmpeg`



\## Setup



\### 1. Get Telegram Bot Token



1\. Open Telegram and search for \[@BotFather](https://t.me/botfather)

2\. Send `/newbot` command

3\. Follow instructions to create your bot

4\. Copy the bot token you receive



\### 2. Get Spotify API Credentials



1\. Go to \[Spotify Developer Dashboard](https://developer.spotify.com/dashboard)

2\. Log in with your Spotify account

3\. Click "Create an App"

4\. Fill in app name and description

5\. Copy your \*\*Client ID\*\* and \*\*Client Secret\*\*



\### 3. Install Dependencies



```bash

pip install -r requirements.txt

```



\### 4. Configure Environment Variables



1\. Copy `.env.example` to `.env`:

&nbsp;  ```bash

&nbsp;  cp .env.example .env

&nbsp;  ```



2\. Edit `.env` and add your credentials:

&nbsp;  ```

&nbsp;  TELEGRAM\_BOT\_TOKEN=your\_actual\_bot\_token

&nbsp;  SPOTIFY\_CLIENT\_ID=your\_spotify\_client\_id

&nbsp;  SPOTIFY\_CLIENT\_SECRET=your\_spotify\_client\_secret

&nbsp;  ```



\### 5. Run the Bot



```bash

python telegram\_music\_bot.py

```



\## Usage



\### Commands



\- `/start` - Show welcome message and commands

\- `/play <song name>` - Play a single song

\- `/play <spotify playlist link>` - Play entire Spotify playlist

\- `/skip` - Skip current song

\- `/queue` - Show current queue

\- `/clear` - Clear the queue

\- `/stop` - Stop playing and clear queue



\### Examples



\*\*Play a single song:\*\*

```

/play Bohemian Rhapsody Queen

```



\*\*Play a Spotify playlist:\*\*

```

/play https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M

```



\## How It Works



1\. When you send a song name, the bot searches YouTube and adds it to the queue

2\. When you send a Spotify playlist link, the bot:

&nbsp;  - Fetches all tracks from the playlist using Spotify API

&nbsp;  - Extracts song names and artist names

&nbsp;  - Adds all songs to the queue

&nbsp;  - Searches YouTube for each song when it's time to play



\## Notes



\- This is a basic implementation focusing on queue management

\- For actual voice playback in Telegram voice chats, you'll need additional setup with `pytgcalls` or similar libraries

\- The current version demonstrates the core functionality of playlist parsing and queue management

\- Consider rate limiting and error handling for production use



\## Extending the Bot



To add actual voice chat playback:



1\. Install `py-tgcalls`:

&nbsp;  ```bash

&nbsp;  pip install py-tgcalls

&nbsp;  ```



2\. Add voice chat join/leave functionality

3\. Implement audio streaming from YouTube URLs



\## Troubleshooting



\*\*Bot not responding:\*\*

\- Check if bot token is correct

\- Ensure bot is running without errors



\*\*Playlist not loading:\*\*

\- Verify Spotify credentials are correct

\- Check if playlist is public

\- Ensure playlist link is valid



\*\*Songs not playing:\*\*

\- Make sure FFmpeg is installed

\- Check internet connection

\- Verify yt-dlp is working: `yt-dlp --version`



\## License



MIT License - feel free to modify and use as needed!


import os
import sys
import subprocess
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from yt_dlp import YoutubeDL
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from pytgcalls.exceptions import GroupCallNotFound, NoActiveGroupCall
from pyrogram import Client, filters
from pyrogram.types import Message

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Validate environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# Validate required environment variables
missing_vars = []
if not TELEGRAM_BOT_TOKEN:
    missing_vars.append("TELEGRAM_BOT_TOKEN")
if not API_ID:
    missing_vars.append("API_ID")
else:
    try:
        API_ID = int(API_ID)
    except ValueError:
        logger.error("API_ID must be an integer")
        sys.exit(1)
if not API_HASH:
    missing_vars.append("API_HASH")
if not SPOTIFY_CLIENT_ID:
    missing_vars.append("SPOTIFY_CLIENT_ID")
if not SPOTIFY_CLIENT_SECRET:
    missing_vars.append("SPOTIFY_CLIENT_SECRET")

if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    logger.error("Please check your .env file and ensure all required variables are set.")
    sys.exit(1)

# Pyrogram client for voice calls
pyrogram_app = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=TELEGRAM_BOT_TOKEN
)

# PyTgCalls instance
calls = PyTgCalls(pyrogram_app)

# Spotify setup
sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    )
)

# Check if FFmpeg is available
try:
    subprocess.check_output(['ffmpeg', '-version'])
    logger.info("FFmpeg is available")
except (subprocess.CalledProcessError, FileNotFoundError):
    logger.error("FFmpeg is not installed or not in system PATH")
    logger.error("Please install FFmpeg from https://ffmpeg.org/download.html")
    sys.exit(1)

# YT-DLP options
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'extract_flat': False,
    'socket_timeout': 15,
    'connect_timeout': 15,
    'read_timeout': 60,
    'extractor_retries': 3,
    'retry_sleep_functions': {'http': 1},
}

# Queue and playback state management
music_queue = {}
currently_playing = {}
is_playing = {}

# Track active voice chats to ensure proper cleanup
active_voice_chats = set()

# Global app instance with better error handling
telegram_app_instance = None

async def send_message_to_chat(chat_id, message):
    """Send a message to a specific chat"""
    global telegram_app_instance
    if telegram_app_instance:
        try:
            await telegram_app_instance.bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            logger.error(f"Failed to send message to chat {chat_id}: {e}")
    else:
        logger.error(f"Telegram app instance not set, can't send message to {chat_id}")
        # Fallback: log the message that should have been sent
        logger.info(f"Would send to chat {chat_id}: {message}")

def set_telegram_app(app):
    global telegram_app_instance
    telegram_app_instance = app
    logger.info("Telegram app instance set successfully")


def sanitize_input(input_str, max_length=200):
    """Sanitize user input to prevent potential issues"""
    if not input_str:
        return ""
    
    # Limit length
    input_str = input_str[:max_length]
    
    # Remove potentially harmful characters (keep alphanumeric, spaces, common symbols)
    sanitized = "".join(c for c in input_str if c.isprintable() and ord(c) < 128)
    
    # Basic URL validation for Spotify links
    if "spotify.com" in sanitized:
        # Only allow valid Spotify URL patterns
        import re
        spotify_pattern = r"https?://open\.spotify\.com/(playlist|track|album)/[a-zA-Z0-9]+"
        if not re.match(spotify_pattern, sanitized):
            logger.warning(f"Invalid Spotify URL pattern detected: {sanitized}")
            return ""
    
    return sanitized.strip()

def _make_spotify_request(func, *args, **kwargs):
    """Wrapper for Spotify API calls with rate limit handling"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "rate limit" in str(e).lower() or "429" in str(e):
                logger.warning(f"Spotify rate limit hit on attempt {attempt + 1}, waiting before retry...")
                time.sleep(2 ** attempt)  # Exponential backoff
            elif "authentication" in str(e).lower() or "401" in str(e) or "403" in str(e):
                logger.error(f"Spotify authentication error: {e}")
                raise
            else:
                if attempt == max_retries - 1:  # Last attempt
                    logger.error(f"Spotify API error after {max_retries} attempts: {e}")
                    raise
                logger.warning(f"Spotify API error on attempt {attempt + 1}: {e}, retrying...")
                time.sleep(2 ** attempt)


def get_spotify_tracks(playlist_link):
    """Extract all tracks from Spotify playlist"""
    tracks = []
    try:
        results = _make_spotify_request(sp.playlist_items, playlist_link)
        
        while results:
            for item in results["items"]:
                track = item["track"]
                if track:
                    name = track["name"]
                    artists = ", ".join(artist["name"] for artist in track["artists"])
                    tracks.append(f"{name} {artists}")
            
            results = sp.next(results) if results["next"] else None
    except Exception as e:
        logger.error(f"Spotify error: {e}")
    
    return tracks

import concurrent.futures
import threading
import time

# Thread locks for queue operations to prevent race conditions
queue_locks = {}

async def search_youtube_async(query, max_retries=3):
    """Asynchronously search YouTube for a song and return audio URL with retry logic"""
    for attempt in range(max_retries):
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, search_youtube_sync, query)
            if result:
                return result
            if attempt < max_retries - 1:  # Don't wait after the last attempt
                logger.info(f"YouTube search attempt {attempt + 1} failed for '{query}', retrying in {2 ** attempt} seconds...")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    return None

def search_youtube_sync(query):
    """Synchronous version of YouTube search"""
    try:
        with YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if 'entries' in info and len(info['entries']) > 0:
                video = info['entries'][0]
                return {
                    'url': video['url'],
                    'title': video['title'],
                    'duration': video.get('duration', 0),
                    'webpage_url': video.get('webpage_url', '')
                }
    except Exception as e:
        logger.error(f"YouTube search error for query '{query}': {e}")
        if "timeout" in str(e).lower() or "network" in str(e).lower():
            logger.warning(f"Network error during search for '{query}'")
        elif "unavailable" in str(e).lower():
            logger.warning(f"Video unavailable for '{query}'")
    return None



# Event handler for when stream ends
@calls.on_stream_end()
async def on_stream_end(client, update):
    """Called when a song finishes playing"""
    chat_id = update.chat_id
    
    logger.info(f"Stream ended in chat {chat_id}")
    
    # Get or create lock for this chat
    if chat_id not in queue_locks:
        queue_locks[chat_id] = threading.Lock()
    
    with queue_locks[chat_id]:
        if chat_id in music_queue and music_queue[chat_id]:
            # Check if the queue still has items and remove the finished song
            if music_queue[chat_id]:
                music_queue[chat_id].pop(0)  # Remove finished song
                
                if music_queue[chat_id]:
                    # Play next song
                    await play_next_song(chat_id)
                else:
                    # Queue empty, leave call
                    is_playing[chat_id] = False
                    active_voice_chats.discard(chat_id)  # Remove from active voice chats
                    try:
                        await calls.leave_group_call(chat_id)
                    except:
                        pass

async def play_next_song(chat_id):
    """Play the next song in queue for a specific chat"""
    if not music_queue.get(chat_id):
        is_playing[chat_id] = False
        return
    
    current_song = music_queue[chat_id][0]
    logger.info(f"Playing next: {current_song}")
    
    # Search YouTube
    result = await search_youtube_async(current_song)
    
    if not result:
        logger.warning(f"Couldn't find: {current_song}")
        music_queue[chat_id].pop(0)
        if music_queue[chat_id]:
            await play_next_song(chat_id)
        else:
            is_playing[chat_id] = False
        return
    
    currently_playing[chat_id] = {
        'title': result['title'],
        'duration': result['duration'],
        'url': result.get('webpage_url', ''),
        'query': current_song
    }
    
    # Try to play the stream with retry logic
    max_play_retries = 3
    for attempt in range(max_play_retries):
        try:
            # Play the audio stream
            await calls.play(
                chat_id,
                MediaStream(result['url'])
            )
            is_playing[chat_id] = True
            active_voice_chats.add(chat_id)
            logger.info(f"Now playing in {chat_id}: {result['title']}")
            return  # Success, exit the function
        except NoActiveGroupCall:
            logger.error(f"No active voice chat in chat {chat_id}")
            await send_message_to_chat(chat_id, "❌ No active voice chat! Please start a voice chat first.")
            is_playing[chat_id] = False
            return
        except GroupCallNotFound:
            logger.error(f"Group call not found in chat {chat_id}")
            await send_message_to_chat(chat_id, "❌ Bot doesn't have permission to join voice chat. Make sure it's added as admin with 'Manage Voice Chats' permission.")
            is_playing[chat_id] = False
            return
        except Exception as e:
            logger.error(f"Error playing in chat {chat_id} (attempt {attempt + 1}): {e}")
            if attempt < max_play_retries - 1:  # If not the last attempt
                logger.info(f"Retrying in {2 ** attempt} seconds...")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                # All retries failed, move to next song
                logger.error(f"All attempts failed for {result['title']}, moving to next song")
                music_queue[chat_id].pop(0)
                if music_queue[chat_id]:
                    await play_next_song(chat_id)
                else:
                    is_playing[chat_id] = False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    await update.message.reply_text(
        "🎵 *Welcome to Music Bot!*\n\n"
        "*Commands:*\n"
        "▶️ `/play <song name>` - Play a song\n"
        "▶️ `/play <playlist link>` - Play Spotify playlist\n"
        "⏸ `/pause` - Pause playback\n"
        "▶️ `/resume` - Resume playback\n"
        "⏭ `/skip` - Skip current song\n"
        "📋 `/queue` - Show queue\n"
        "🎵 `/np` - Now playing\n"
        "🗑 `/clear` - Clear queue\n"
        "⏹ `/stop` - Stop and leave voice chat\n\n"
        "⚠️ *Important:* Add bot to your group, make it admin with 'Manage Voice Chats' permission, and start a voice chat first!",
        parse_mode='Markdown'
    )

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Play command - supports both song names and Spotify playlists"""
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.message.reply_text("❌ Usage: `/play <song name or playlist link>`", parse_mode='Markdown')
        return
    
    query = " ".join(context.args)
    
    # Sanitize the user input
    query = sanitize_input(query)
    
    if not query:
        await update.message.reply_text("❌ Invalid input provided.")
        return
    
    # Initialize queue for this chat
    if chat_id not in music_queue:
        music_queue[chat_id] = []
        is_playing[chat_id] = False
    
    # Check if it's a Spotify playlist link
    if "spotify.com/playlist" in query:
        msg = await update.message.reply_text("🔍 Fetching playlist tracks...")
        
        try:
            tracks = await get_spotify_tracks_async(query)
            if not tracks:
                await msg.edit_text("❌ Couldn't fetch playlist. Make sure it's public!")
                return
            
            await msg.edit_text(f"✅ Found {len(tracks)} tracks! Adding to queue...")
            
            for track in tracks:
                music_queue[chat_id].append(track)
            
            await msg.edit_text(
                f"✅ Added *{len(tracks)}* songs to queue!\n"
                f"Use /queue to see the list.",
                parse_mode='Markdown'
            )
            
            # Start playing if not already playing
            if not is_playing.get(chat_id, False):
                await play_next_song(chat_id)
                await asyncio.sleep(1)  # Wait a moment
                if chat_id in currently_playing:
                    info = currently_playing[chat_id]
                    await msg.reply_text(
                        f"▶️ *Now Playing:*\n{info['title']}\n\n"
                        f"📋 Queue: {len(music_queue[chat_id])-1} songs remaining",
                        parse_mode='Markdown'
                    )
        
        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)}")
    
    else:
        # Single song
        music_queue[chat_id].append(query)
        await update.message.reply_text(f"✅ Added to queue: *{query}*", parse_mode='Markdown')
        
        # Start playing if not already playing
        if not is_playing.get(chat_id, False):
            msg = await update.message.reply_text("🔍 Searching...")
            await play_next_song(chat_id)
            await asyncio.sleep(1)
            
            if chat_id in currently_playing:
                info = currently_playing[chat_id]
                duration_min = info['duration'] // 60
                duration_sec = info['duration'] % 60
                await msg.edit_text(
                    f"▶️ *Now Playing:*\n{info['title']}\n\n"
                    f"⏱ Duration: {duration_min}:{duration_sec:02d}",
                    parse_mode='Markdown'
                )
            else:
                await msg.edit_text("❌ Couldn't find the song. Make sure voice chat is active!")

async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pause playback"""
    chat_id = update.effective_chat.id
    
    try:
        await calls.pause_stream(chat_id)
        await update.message.reply_text("⏸ Paused")
    except Exception as e:
        await update.message.reply_text(f"❌ Not playing anything or error: {str(e)}")

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resume playback"""
    chat_id = update.effective_chat.id
    
    try:
        await calls.resume_stream(chat_id)
        await update.message.reply_text("▶️ Resumed")
    except Exception as e:
        await update.message.reply_text(f"❌ Nothing to resume or error: {str(e)}")

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip current song"""
    chat_id = update.effective_chat.id
    
    # Get or create lock for this chat
    if chat_id not in queue_locks:
        queue_locks[chat_id] = threading.Lock()
    
    with queue_locks[chat_id]:
        if chat_id in music_queue and music_queue[chat_id]:
            skipped = music_queue[chat_id].pop(0)
            await update.message.reply_text(f"⏭ Skipped: *{skipped}*", parse_mode='Markdown')
            
            if music_queue[chat_id]:
                await play_next_song(chat_id)
                await asyncio.sleep(1)
                if chat_id in currently_playing:
                    info = currently_playing[chat_id]
                    await update.message.reply_text(
                        f"▶️ *Now Playing:*\n{info['title']}",
                        parse_mode='Markdown'
                    )
            else:
                is_playing[chat_id] = False
                active_voice_chats.discard(chat_id)  # Remove from active voice chats
                try:
                    await calls.leave_group_call(chat_id)
                except:
                    pass
                await update.message.reply_text("✅ Queue is now empty!")
        else:
            await update.message.reply_text("❌ Nothing to skip!")

async def now_playing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show currently playing song"""
    chat_id = update.effective_chat.id
    
    if chat_id in currently_playing:
        info = currently_playing[chat_id]
        duration_min = info['duration'] // 60
        duration_sec = info['duration'] % 60
        
        await update.message.reply_text(
            f"🎵 *Now Playing:*\n{info['title']}\n\n"
            f"🔍 Query: {info.get('query', 'N/A')}\n"
            f"⏱ Duration: {duration_min}:{duration_sec:02d}\n"
            f"🔗 [Watch on YouTube]({info['url']})",
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    else:
        await update.message.reply_text("❌ Nothing is playing right now!")

async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current queue"""
    chat_id = update.effective_chat.id
    
    if chat_id not in music_queue or not music_queue[chat_id]:
        await update.message.reply_text("📋 Queue is empty!")
        return
    
    # Split queue into chunks if too long
    queue_list = music_queue[chat_id]
    max_display = 15
    
    queue_text = "📋 *Current Queue:*\n\n"
    for i, song in enumerate(queue_list[:max_display], 1):
        status = "▶️ " if i == 1 else f"{i}. "
        queue_text += f"{status}{song}\n"
    
    if len(queue_list) > max_display:
        queue_text += f"\n_...and {len(queue_list) - max_display} more songs_"
    
    queue_text += f"\n\n*Total:* {len(queue_list)} songs"
    
    await update.message.reply_text(queue_text, parse_mode='Markdown')

async def clear_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear the queue"""
    chat_id = update.effective_chat.id
    
    # Get or create lock for this chat
    if chat_id not in queue_locks:
        queue_locks[chat_id] = threading.Lock()
    
    with queue_locks[chat_id]:
        if chat_id in music_queue and music_queue[chat_id]:
            count = len(music_queue[chat_id])
            music_queue[chat_id] = []
            is_playing[chat_id] = False
            active_voice_chats.discard(chat_id)  # Remove from active voice chats
            try:
                await calls.leave_group_call(chat_id)
            except:
                pass
            await update.message.reply_text(f"✅ Cleared {count} songs from queue!")
        else:
            await update.message.reply_text("📋 Queue is already empty!")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop playing and leave voice chat"""
    chat_id = update.effective_chat.id
    
    if chat_id in music_queue:
        music_queue[chat_id] = []
    
    if chat_id in currently_playing:
        del currently_playing[chat_id]
    
    is_playing[chat_id] = False
    active_voice_chats.discard(chat_id)  # Remove from active voice chats
    
    try:
        await calls.leave_group_call(chat_id)
        await update.message.reply_text("⏹ Stopped playing and left voice chat!")
    except:
        await update.message.reply_text("⏹ Stopped playing!")

def main():
    """Start the bot"""
    logger.info("🚀 Starting bot...")
    
    # Start Pyrogram client
    pyrogram_app.start()
    logger.info("✅ Pyrogram client started")
    
    # Start PyTgCalls
    loop = asyncio.get_event_loop()
    loop.run_until_complete(calls.start())
    logger.info("✅ PyTgCalls started")
    
    # Build telegram bot
    telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Set the global telegram app instance for use in other functions
    set_telegram_app(telegram_app)
    
    # Command handlers
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("play", play))
    telegram_app.add_handler(CommandHandler("pause", pause))
    telegram_app.add_handler(CommandHandler("resume", resume))
    telegram_app.add_handler(CommandHandler("skip", skip))
    telegram_app.add_handler(CommandHandler("np", now_playing))
    telegram_app.add_handler(CommandHandler("queue", queue_command))
    telegram_app.add_handler(CommandHandler("clear", clear_queue))
    telegram_app.add_handler(CommandHandler("stop", stop))
    
    logger.info("🤖 Bot is running!")
    logger.info("📝 Make sure to:")
    logger.info("   1. Add bot to your group")
    logger.info("   2. Make bot admin with 'Manage Voice Chats' permission")
    logger.info("   3. Start a voice chat in the group")
    logger.info("   4. Use /play command to start playing music")
    logger.info("\n⏹ Press Ctrl+C to stop")
    
    try:
        telegram_app.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down gracefully...")
    except Exception as e:
        logger.error(f"Unexpected error during bot operation: {e}")
    finally:
        cleanup_resources()

def cleanup_resources():
    """Clean up resources when the bot stops"""
    logger.info("🧹 Cleaning up resources...")
    
    # Stop PyTgCalls
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(calls.stop())
        logger.info("✅ PyTgCalls stopped")
    except Exception as e:
        logger.error(f"Error stopping PyTgCalls: {e}")
    
    # Stop Pyrogram client
    try:
        pyrogram_app.stop()
        logger.info("✅ Pyrogram client stopped")
    except Exception as e:
        logger.error(f"Error stopping Pyrogram client: {e}")
    
    # Leave all active voice chats
    for chat_id in active_voice_chats:
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(calls.leave_group_call(chat_id))
            logger.info(f"✅ Left voice chat in {chat_id}")
        except Exception as e:
            logger.error(f"Error leaving voice chat in {chat_id}: {e}")
    
    # Clear the active voice chats set
    active_voice_chats.clear()
    
    logger.info("👋 Bot stopped!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n👋 Bot stopped!")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise
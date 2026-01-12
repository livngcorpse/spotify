import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from yt_dlp import YoutubeDL
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types import AudioPiped, AudioVideoPiped
from pytgcalls.exceptions import GroupCallNotFound
from pyrogram import Client

load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# Pyrogram client for voice calls
app = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=TELEGRAM_BOT_TOKEN
)

# PyTgCalls instance
pytgcalls = PyTgCalls(app)

# Spotify setup
sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    )
)

# YT-DLP options
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'skip_download': True
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# Queue and playback state management
music_queue = {}
currently_playing = {}
is_playing = {}

def get_spotify_tracks(playlist_link):
    """Extract all tracks from Spotify playlist"""
    tracks = []
    try:
        results = sp.playlist_items(playlist_link)
        
        while results:
            for item in results["items"]:
                track = item["track"]
                if track:
                    name = track["name"]
                    artists = ", ".join(artist["name"] for artist in track["artists"])
                    tracks.append(f"{name} {artists}")
            
            results = sp.next(results) if results["next"] else None
    except Exception as e:
        print(f"Spotify error: {e}")
    
    return tracks

def search_youtube(query):
    """Search YouTube for a song and return audio URL"""
    with YoutubeDL(YDL_OPTIONS) as ydl:
        try:
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
            print(f"YouTube search error: {e}")
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    await update.message.reply_text(
        "🎵 Welcome to Music Bot!\n\n"
        "Commands:\n"
        "/play <song name> - Play a song\n"
        "/play <playlist link> - Play Spotify playlist\n"
        "/pause - Pause playback\n"
        "/resume - Resume playback\n"
        "/skip - Skip current song\n"
        "/queue - Show queue\n"
        "/np - Now playing\n"
        "/clear - Clear queue\n"
        "/stop - Stop and leave voice chat\n\n"
        "Note: Add bot to your group and start a voice chat first!"
    )

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Play command - supports both song names and Spotify playlists"""
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.message.reply_text("Usage: /play <song name or playlist link>")
        return
    
    query = " ".join(context.args)
    
    # Initialize queue for this chat
    if chat_id not in music_queue:
        music_queue[chat_id] = []
        is_playing[chat_id] = False
    
    # Check if it's a Spotify playlist link
    if "spotify.com/playlist" in query:
        msg = await update.message.reply_text("🔍 Fetching playlist tracks...")
        
        try:
            tracks = get_spotify_tracks(query)
            if not tracks:
                await msg.edit_text("❌ Couldn't fetch playlist. Make sure it's public!")
                return
            
            await msg.edit_text(f"✅ Found {len(tracks)} tracks! Adding to queue...")
            
            for track in tracks:
                music_queue[chat_id].append(track)
            
            await msg.edit_text(
                f"📝 Added {len(tracks)} songs to queue!\n"
                f"Use /queue to see the list."
            )
            
            # Start playing if not already playing
            if not is_playing[chat_id]:
                await play_next(update, context)
        
        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)}")
    
    else:
        # Single song
        music_queue[chat_id].append(query)
        await update.message.reply_text(f"✅ Added to queue: {query}")
        
        # Start playing if not already playing
        if not is_playing[chat_id]:
            await play_next(update, context)

async def play_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Play the next song in queue"""
    chat_id = update.effective_chat.id
    
    if chat_id not in music_queue or not music_queue[chat_id]:
        is_playing[chat_id] = False
        try:
            await pytgcalls.leave_group_call(chat_id)
        except:
            pass
        return
    
    is_playing[chat_id] = True
    current_song = music_queue[chat_id][0]
    
    msg = await update.message.reply_text(f"🔍 Searching: {current_song}")
    
    # Search YouTube
    result = search_youtube(current_song)
    
    if not result:
        await msg.edit_text(f"❌ Couldn't find: {current_song}")
        music_queue[chat_id].pop(0)
        if music_queue[chat_id]:
            await play_next(update, context)
        else:
            is_playing[chat_id] = False
        return
    
    currently_playing[chat_id] = {
        'title': result['title'],
        'duration': result['duration'],
        'url': result.get('webpage_url', '')
    }
    
    try:
        # Join voice chat and play
        await pytgcalls.play(
            chat_id,
            AudioPiped(result['url'])
        )
        
        duration_min = result['duration'] // 60
        duration_sec = result['duration'] % 60
        
        await msg.edit_text(
            f"▶️ Now Playing:\n{result['title']}\n\n"
            f"⏱ Duration: {duration_min}:{duration_sec:02d}\n"
            f"📋 Queue: {len(music_queue[chat_id])-1} songs remaining"
        )
        
        # Schedule next song
        if result['duration'] > 0:
            await asyncio.sleep(result['duration'] + 2)
            music_queue[chat_id].pop(0)
            if music_queue[chat_id]:
                await play_next(update, context)
            else:
                is_playing[chat_id] = False
                await pytgcalls.leave_group_call(chat_id)
    
    except GroupCallNotFound:
        await msg.edit_text(
            "❌ No active voice chat found!\n"
            "Please start a voice chat in the group first."
        )
        is_playing[chat_id] = False
    
    except Exception as e:
        await msg.edit_text(f"❌ Error playing: {str(e)}")
        music_queue[chat_id].pop(0)
        if music_queue[chat_id]:
            await play_next(update, context)
        else:
            is_playing[chat_id] = False

async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pause playback"""
    chat_id = update.effective_chat.id
    
    try:
        await pytgcalls.pause_stream(chat_id)
        await update.message.reply_text("⏸ Paused")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resume playback"""
    chat_id = update.effective_chat.id
    
    try:
        await pytgcalls.resume_stream(chat_id)
        await update.message.reply_text("▶️ Resumed")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip current song"""
    chat_id = update.effective_chat.id
    
    if chat_id in music_queue and music_queue[chat_id]:
        skipped = music_queue[chat_id].pop(0)
        await update.message.reply_text(f"⏭ Skipped: {skipped}")
        
        if music_queue[chat_id]:
            await play_next(update, context)
        else:
            is_playing[chat_id] = False
            try:
                await pytgcalls.leave_group_call(chat_id)
            except:
                pass
            await update.message.reply_text("Queue is now empty!")
    else:
        await update.message.reply_text("Nothing to skip!")

async def now_playing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show currently playing song"""
    chat_id = update.effective_chat.id
    
    if chat_id in currently_playing:
        info = currently_playing[chat_id]
        duration_min = info['duration'] // 60
        duration_sec = info['duration'] % 60
        
        await update.message.reply_text(
            f"🎵 Now Playing:\n{info['title']}\n\n"
            f"⏱ Duration: {duration_min}:{duration_sec:02d}\n"
            f"🔗 {info['url']}"
        )
    else:
        await update.message.reply_text("Nothing is playing right now!")

async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current queue"""
    chat_id = update.effective_chat.id
    
    if chat_id not in music_queue or not music_queue[chat_id]:
        await update.message.reply_text("Queue is empty!")
        return
    
    # Split queue into chunks if too long
    queue_list = music_queue[chat_id]
    max_display = 20
    
    queue_text = "📋 Current Queue:\n\n"
    for i, song in enumerate(queue_list[:max_display], 1):
        status = "▶️ " if i == 1 else f"{i}. "
        queue_text += f"{status}{song}\n"
    
    if len(queue_list) > max_display:
        queue_text += f"\n...and {len(queue_list) - max_display} more songs"
    
    await update.message.reply_text(queue_text)

async def clear_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear the queue"""
    chat_id = update.effective_chat.id
    
    if chat_id in music_queue:
        music_queue[chat_id] = []
        is_playing[chat_id] = False
        try:
            await pytgcalls.leave_group_call(chat_id)
        except:
            pass
        await update.message.reply_text("✅ Queue cleared!")
    else:
        await update.message.reply_text("Queue is already empty!")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop playing and leave voice chat"""
    chat_id = update.effective_chat.id
    
    if chat_id in music_queue:
        music_queue[chat_id] = []
    
    is_playing[chat_id] = False
    
    try:
        await pytgcalls.leave_group_call(chat_id)
        await update.message.reply_text("⏹ Stopped playing and left voice chat!")
    except:
        await update.message.reply_text("⏹ Stopped playing!")

async def start_pytgcalls():
    """Start PyTgCalls"""
    await pytgcalls.start()

def main():
    """Start the bot"""
    # Start Pyrogram client
    app.start()
    
    # Start PyTgCalls in background
    loop = asyncio.get_event_loop()
    loop.create_task(start_pytgcalls())
    
    # Build telegram bot
    telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
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
    
    print("🤖 Bot is running...")
    print("Make sure to start a voice chat in your group!")
    
    telegram_app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
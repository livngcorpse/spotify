import os
import asyncio
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

load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

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

# Event handler for when stream ends
@calls.on_stream_end()
async def on_stream_end(client, update):
    """Called when a song finishes playing"""
    chat_id = update.chat_id
    
    print(f"Stream ended in chat {chat_id}")
    
    if chat_id in music_queue and music_queue[chat_id]:
        music_queue[chat_id].pop(0)  # Remove finished song
        
        if music_queue[chat_id]:
            # Play next song
            await play_next_song(chat_id)
        else:
            # Queue empty, leave call
            is_playing[chat_id] = False
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
    print(f"Playing next: {current_song}")
    
    # Search YouTube
    result = search_youtube(current_song)
    
    if not result:
        print(f"Couldn't find: {current_song}")
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
    
    try:
        # Play the audio stream
        await calls.play(
            chat_id,
            MediaStream(result['url'])
        )
        is_playing[chat_id] = True
        print(f"Now playing in {chat_id}: {result['title']}")
        
    except Exception as e:
        print(f"Error playing: {e}")
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
    
    if chat_id in music_queue and music_queue[chat_id]:
        count = len(music_queue[chat_id])
        music_queue[chat_id] = []
        is_playing[chat_id] = False
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
    
    try:
        await calls.leave_group_call(chat_id)
        await update.message.reply_text("⏹ Stopped playing and left voice chat!")
    except:
        await update.message.reply_text("⏹ Stopped playing!")

def main():
    """Start the bot"""
    print("🚀 Starting bot...")
    
    # Start Pyrogram client
    pyrogram_app.start()
    print("✅ Pyrogram client started")
    
    # Start PyTgCalls
    loop = asyncio.get_event_loop()
    loop.run_until_complete(calls.start())
    print("✅ PyTgCalls started")
    
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
    
    print("🤖 Bot is running!")
    print("📝 Make sure to:")
    print("   1. Add bot to your group")
    print("   2. Make bot admin with 'Manage Voice Chats' permission")
    print("   3. Start a voice chat in the group")
    print("   4. Use /play command to start playing music")
    print("\n⏹ Press Ctrl+C to stop")
    
    telegram_app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped!")
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
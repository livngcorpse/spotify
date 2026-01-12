import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from yt_dlp import YoutubeDL
import discord
from discord.ext import commands

load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

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
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

# Queue management
music_queue = {}

def get_spotify_tracks(playlist_link):
    """Extract all tracks from Spotify playlist"""
    tracks = []
    results = sp.playlist_items(playlist_link)
    
    while results:
        for item in results["items"]:
            track = item["track"]
            if track:
                name = track["name"]
                artists = ", ".join(artist["name"] for artist in track["artists"])
                tracks.append(f"{name} {artists}")
        
        results = sp.next(results) if results["next"] else None
    
    return tracks

def search_youtube(query):
    """Search YouTube for a song"""
    with YoutubeDL(YDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if 'entries' in info:
                video = info['entries'][0]
                return {
                    'url': video['url'],
                    'title': video['title'],
                    'duration': video.get('duration', 0)
                }
        except Exception as e:
            print(f"Error searching: {e}")
            return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    await update.message.reply_text(
        "🎵 Welcome to Music Bot!\n\n"
        "Commands:\n"
        "/play <song name> - Play a song\n"
        "/play <playlist link> - Play Spotify playlist\n"
        "/skip - Skip current song\n"
        "/queue - Show queue\n"
        "/clear - Clear queue\n"
        "/stop - Stop playing"
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
    
    # Check if it's a Spotify playlist link
    if "spotify.com/playlist" in query:
        await update.message.reply_text("🔍 Fetching playlist tracks...")
        
        try:
            tracks = get_spotify_tracks(query)
            await update.message.reply_text(f"✅ Found {len(tracks)} tracks! Adding to queue...")
            
            for track in tracks:
                music_queue[chat_id].append(track)
            
            await update.message.reply_text(
                f"📝 Added {len(tracks)} songs to queue!\n"
                f"Use /queue to see the list."
            )
            
            # Start playing if not already playing
            if len(music_queue[chat_id]) == len(tracks):
                await play_next(update, context)
        
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    else:
        # Single song
        music_queue[chat_id].append(query)
        await update.message.reply_text(f"✅ Added to queue: {query}")
        
        # Start playing if this is the first song
        if len(music_queue[chat_id]) == 1:
            await play_next(update, context)

async def play_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Play the next song in queue"""
    chat_id = update.effective_chat.id
    
    if chat_id not in music_queue or not music_queue[chat_id]:
        await update.message.reply_text("Queue is empty!")
        return
    
    current_song = music_queue[chat_id][0]
    await update.message.reply_text(f"🎵 Searching: {current_song}")
    
    # Search YouTube
    result = search_youtube(current_song)
    
    if result:
        await update.message.reply_text(
            f"▶️ Now Playing:\n{result['title']}\n\n"
            f"⏱ Duration: {result['duration']}s\n"
            f"📋 Queue: {len(music_queue[chat_id])} songs"
        )
    else:
        await update.message.reply_text(f"❌ Couldn't find: {current_song}")
        music_queue[chat_id].pop(0)
        if music_queue[chat_id]:
            await play_next(update, context)

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip current song"""
    chat_id = update.effective_chat.id
    
    if chat_id in music_queue and music_queue[chat_id]:
        skipped = music_queue[chat_id].pop(0)
        await update.message.reply_text(f"⏭ Skipped: {skipped}")
        
        if music_queue[chat_id]:
            await play_next(update, context)
        else:
            await update.message.reply_text("Queue is now empty!")
    else:
        await update.message.reply_text("Nothing to skip!")

async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current queue"""
    chat_id = update.effective_chat.id
    
    if chat_id not in music_queue or not music_queue[chat_id]:
        await update.message.reply_text("Queue is empty!")
        return
    
    queue_text = "📋 Current Queue:\n\n"
    for i, song in enumerate(music_queue[chat_id], 1):
        status = "▶️ " if i == 1 else f"{i}. "
        queue_text += f"{status}{song}\n"
    
    await update.message.reply_text(queue_text)

async def clear_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear the queue"""
    chat_id = update.effective_chat.id
    
    if chat_id in music_queue:
        music_queue[chat_id] = []
        await update.message.reply_text("✅ Queue cleared!")
    else:
        await update.message.reply_text("Queue is already empty!")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop playing and clear queue"""
    chat_id = update.effective_chat.id
    
    if chat_id in music_queue:
        music_queue[chat_id] = []
    
    await update.message.reply_text("⏹ Stopped playing and cleared queue!")

def main():
    """Start the bot"""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("skip", skip))
    app.add_handler(CommandHandler("queue", queue_command))
    app.add_handler(CommandHandler("clear", clear_queue))
    app.add_handler(CommandHandler("stop", stop))
    
    print("🤖 Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

import os
from dotenv import load_dotenv

load_dotenv()  # reads .env file

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

def ms_to_min_sec(ms):
    minutes = ms // 60000
    seconds = (ms % 60000) // 1000
    return f"{minutes}:{seconds:02d}"

# Spotify API setup
sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )
)

playlist_link = input("Enter Spotify playlist link: ").strip()

results = sp.playlist_items(playlist_link)

print("\nTracks:\n" + "-" * 40)

while results:
    for item in results["items"]:
        track = item["track"]
        if track is None:
            continue

        name = track["name"]
        artists = ", ".join(artist["name"] for artist in track["artists"])
        duration = ms_to_min_sec(track["duration_ms"])

        print(f"Song   : {name}")
        print(f"Artist : {artists}")
        print(f"Time   : {duration}")
        print("-" * 40)

    results = sp.next(results) if results["next"] else None

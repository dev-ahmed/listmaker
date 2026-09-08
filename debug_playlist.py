#!/usr/bin/env python3
"""Debug why adding tracks fails"""
import os
import sys
from listmaker.spotify import SpotifyClient


def main():
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')

    if not client_id or not client_secret:
        print("ERROR: Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET")
        sys.exit(1)

    client = SpotifyClient(client_id, client_secret)

    if not client.access_token:
        print("ERROR: Not authenticated. Run: listmaker auth")
        sys.exit(1)

    # Get user info
    print("="*60)
    print("USER INFO")
    print("="*60)
    user_response = client._make_request('GET', '/me')
    user = user_response.json()
    print(f"Email: {user.get('email')}")
    print(f"User ID: {user.get('id')}")
    print(f"Product: {user.get('product')}")
    print(f"Country: {user.get('country')}")

    # Check playlist
    playlist_id = input("\nEnter playlist ID: ").strip()

    print(f"\n{'='*60}")
    print("PLAYLIST INFO")
    print("="*60)

    try:
        playlist_info = client.get_playlist_info(playlist_id)
        print(f"Name: {playlist_info['name']}")
        print(f"Owner: {playlist_info['owner']['id']}")
        print(f"Public: {playlist_info['public']}")
        print(f"Total tracks: {playlist_info['tracks']['total']}")
        print(f"Collaborative: {playlist_info.get('collaborative', False)}")

        # Check if user owns the playlist
        if playlist_info['owner']['id'] != user.get('id'):
            print(f"\n⚠️  WARNING: You don't own this playlist!")
            print(f"   Owner: {playlist_info['owner']['id']}")
            print(f"   You: {user.get('id')}")
            print(f"   You can only add tracks to playlists you own!")

    except Exception as e:
        print(f"Error getting playlist: {e}")
        sys.exit(1)

    # Try to add a single track
    print(f"\n{'='*60}")
    print("TESTING TRACK ADDITION")
    print("="*60)

    print("Searching for 'Bleeding Love'...")
    results = client.search_track("Bleeding Love", limit=1)

    if not results:
        print("No results found")
        sys.exit(1)

    track_uri = results[0]['uri']
    track_name = results[0]['name']
    print(f"Found: {track_name} ({track_uri})")

    print("\nAttempting to add 1 track to playlist...")
    try:
        response = client._make_request('POST', f'/playlists/{playlist_id}/tracks', json={'uris': [track_uri]})
        print(f"Response status: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code in [200, 201]:
            print("✓ SUCCESS!")
        else:
            print("✗ FAILED!")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()

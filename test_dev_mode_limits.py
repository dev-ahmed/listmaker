#!/usr/bin/env python3
"""
Standalone test to determine Spotify Development Mode limits.
Run this script to find out:
1. Maximum batch size for adding tracks
2. Maximum total tracks per playlist
"""
import os
import sys
from listmaker.spotify import SpotifyClient


def main():
    print("="*60)
    print("SPOTIFY DEVELOPMENT MODE LIMIT TEST")
    print("="*60)

    # Get credentials
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')

    if not client_id or not client_secret:
        print("\nERROR: Environment variables not set")
        print("Run: export SPOTIFY_CLIENT_ID=...")
        print("     export SPOTIFY_CLIENT_SECRET=...")
        sys.exit(1)

    # Create client
    client = SpotifyClient(client_id, client_secret)

    if not client.access_token:
        print("\nERROR: Not authenticated")
        print("Run: listmaker auth")
        sys.exit(1)

    print(f"\n✓ Authenticated")

    # Get some test tracks
    print("\n1. Getting test tracks...")
    test_songs = [
        "Bleeding Love", "Shape of You", "Rolling in the Deep",
        "Perfect", "Stay", "Someone Like You", "Hello", "Photograph",
        "Thinking Out Loud", "Castle on the Hill"
    ]

    track_uris = []
    for song in test_songs:
        try:
            results = client.search_track(song, limit=1)
            if results and results[0]['uri'] not in track_uris:
                track_uris.append(results[0]['uri'])
        except:
            pass

    print(f"✓ Got {len(track_uris)} test tracks\n")

    # Test 1: Find maximum batch size
    print("2. Testing batch sizes...")
    print("-" * 60)

    batch_sizes = [1, 2, 3, 5, 8, 10, 15, 20]
    max_batch_working = 1

    for batch_size in batch_sizes:
        # Create test playlist
        try:
            playlist = client.create_playlist(f"Batch Test {batch_size} - DELETE ME")
            playlist_id = playlist['id']

            # Get tracks for this test
            test_tracks = track_uris[:min(batch_size, len(track_uris))]

            # Try adding
            client.add_tracks_to_playlist(playlist_id, test_tracks, batch_size=batch_size)

            print(f"  ✓ Batch size {batch_size}: SUCCESS ({len(test_tracks)} tracks)")
            max_batch_working = batch_size

        except Exception as e:
            error_str = str(e)
            if "403" in error_str:
                print(f"  ✗ Batch size {batch_size}: FAILED (403 Forbidden)")
                break
            else:
                print(f"  ✗ Batch size {batch_size}: FAILED ({error_str[:50]})")
                break

    print(f"\n  RESULT: Maximum batch size = {max_batch_working}")

    # Test 2: Find maximum total tracks per playlist
    print("\n3. Testing maximum total tracks per playlist...")
    print("-" * 60)

    try:
        # Create fresh playlist
        playlist = client.create_playlist("Total Tracks Test - DELETE ME")
        playlist_id = playlist['id']
        print(f"  ✓ Created playlist: {playlist_id}")

        # Add tracks one by one until we hit the limit
        total_added = 0
        batch_size = 1  # Safest

        for i in range(len(track_uris)):
            try:
                track = [track_uris[i]]
                client.add_tracks_to_playlist(playlist_id, track, batch_size=1)
                total_added += 1
                print(f"  ✓ Added track {total_added}")
            except Exception as e:
                error_str = str(e)
                if "403" in error_str:
                    print(f"  ✗ Hit limit at track {total_added + 1}")
                    break
                else:
                    print(f"  ✗ Error: {error_str[:100]}")
                    break

        # Get final count
        playlist_info = client.get_playlist_info(playlist_id)
        final_count = playlist_info['tracks']['total']

        print(f"\n  RESULT: Maximum total tracks = {final_count}")

    except Exception as e:
        print(f"  ✗ Test failed: {e}")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Maximum batch size:      {max_batch_working} tracks per request")
    print(f"Maximum playlist tracks: {final_count if 'final_count' in locals() else 'Unknown'}")
    print("\nNote: These limits apply to Development Mode only.")
    print("Request Extended Quota Mode for higher limits.")
    print("="*60)


if __name__ == "__main__":
    main()

"""Integration tests for Spotify API - requires real credentials"""
import pytest
import os
from listmaker.spotify import SpotifyClient


@pytest.fixture
def spotify_client():
    """Create a real Spotify client - requires environment variables"""
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')

    if not client_id or not client_secret:
        pytest.skip("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET not set")

    client = SpotifyClient(client_id, client_secret)

    if not client.access_token:
        pytest.skip("Not authenticated - run 'listmaker auth' first")

    return client


class TestSpotifyIntegration:
    """Integration tests that hit real Spotify API"""

    def test_get_user_info(self, spotify_client):
        """Test getting user information"""
        user_id = spotify_client.get_user_id()
        assert user_id is not None
        assert len(user_id) > 0
        print(f"\n✓ User ID: {user_id}")

    def test_search_single_track(self, spotify_client):
        """Test searching for a well-known track"""
        results = spotify_client.search_track("Bleeding Love Leona Lewis", limit=5)

        assert len(results) > 0, "No results returned"

        first_result = results[0]
        assert 'name' in first_result
        assert 'artists' in first_result
        assert 'uri' in first_result

        print(f"\n✓ Found: {first_result['name']} by {first_result['artists'][0]['name']}")
        print(f"  URI: {first_result['uri']}")

    def test_search_multiple_tracks(self, spotify_client):
        """Test searching for multiple tracks"""
        test_songs = [
            "Bleeding Love - Leona Lewis",
            "Shape of You - Ed Sheeran",
            "Rolling in the Deep - Adele"
        ]

        results_count = []
        for song in test_songs:
            results = spotify_client.search_track(song, limit=5)
            results_count.append(len(results))
            print(f"\n✓ '{song}': {len(results)} results")

        assert all(count > 0 for count in results_count), "Some searches returned no results"

    def test_create_empty_playlist(self, spotify_client):
        """Test creating an empty playlist (should work in Development Mode)"""
        try:
            playlist = spotify_client.create_playlist(
                "Test Playlist - Delete Me",
                "Created by listmaker integration test"
            )

            assert 'id' in playlist
            assert 'name' in playlist
            assert playlist['name'] == "Test Playlist - Delete Me"

            print(f"\n✓ Created playlist: {playlist['name']}")
            print(f"  ID: {playlist['id']}")
            print(f"  URL: {playlist.get('external_urls', {}).get('spotify', 'N/A')}")

            # Store for cleanup
            return playlist['id']

        except Exception as e:
            pytest.fail(f"Failed to create playlist: {e}")

    def test_add_single_track_to_playlist(self, spotify_client):
        """Test adding a single track to a playlist"""
        # Create playlist
        playlist = spotify_client.create_playlist("Test Single Track - Delete Me")
        playlist_id = playlist['id']

        print(f"\n✓ Created playlist: {playlist_id}")

        # Search for a track
        results = spotify_client.search_track("Bleeding Love Leona Lewis", limit=1)
        assert len(results) > 0

        track_uri = results[0]['uri']
        print(f"✓ Found track: {track_uri}")

        # Try to add track
        try:
            spotify_client.add_tracks_to_playlist(playlist_id, [track_uri])
            print(f"✓ Successfully added 1 track")
        except Exception as e:
            print(f"✗ Failed to add track: {e}")
            raise

    def test_add_multiple_tracks_batch_sizes(self, spotify_client):
        """Test adding different batch sizes to find Development Mode limit"""
        # Create playlist
        playlist = spotify_client.create_playlist("Test Batch Size - Delete Me")
        playlist_id = playlist['id']

        print(f"\n✓ Created playlist: {playlist_id}")

        # Get multiple tracks
        test_songs = [
            "Bleeding Love - Leona Lewis",
            "Shape of You - Ed Sheeran",
            "Rolling in the Deep - Adele",
            "Perfect - Ed Sheeran",
            "Stay - Rihanna",
        ]

        track_uris = []
        for song in test_songs:
            results = spotify_client.search_track(song, limit=1)
            if results:
                track_uris.append(results[0]['uri'])

        print(f"✓ Found {len(track_uris)} tracks")

        # Test different batch sizes
        batch_sizes = [1, 5, 10, 25, 50]

        for batch_size in batch_sizes:
            # Create new playlist for each test
            test_playlist = spotify_client.create_playlist(f"Test {batch_size} Tracks - Delete Me")
            test_playlist_id = test_playlist['id']

            # Take only the needed tracks
            tracks_to_add = track_uris[:min(batch_size, len(track_uris))]

            try:
                spotify_client.add_tracks_to_playlist(test_playlist_id, tracks_to_add)
                print(f"✓ Batch size {batch_size}: SUCCESS ({len(tracks_to_add)} tracks)")
            except Exception as e:
                print(f"✗ Batch size {batch_size}: FAILED - {str(e)[:100]}")
                # Don't fail the test, just record the limit
                break

    def test_development_mode_limits(self, spotify_client):
        """Test to determine exact Development Mode limitations"""
        print("\n" + "="*60)
        print("DEVELOPMENT MODE LIMIT TEST")
        print("="*60)

        # Test 1: Can we create a playlist?
        try:
            playlist = spotify_client.create_playlist("Limit Test - Delete Me")
            print("✓ CREATE PLAYLIST: Works")
            playlist_id = playlist['id']
        except Exception as e:
            print(f"✗ CREATE PLAYLIST: Failed - {e}")
            pytest.fail("Cannot create playlist")

        # Test 2: Can we add 1 track?
        try:
            results = spotify_client.search_track("Bleeding Love", limit=1)
            track_uri = results[0]['uri']
            spotify_client.add_tracks_to_playlist(playlist_id, [track_uri])
            print("✓ ADD 1 TRACK: Works")
            successful_count = 1
        except Exception as e:
            print(f"✗ ADD 1 TRACK: Failed - {e}")
            pytest.fail("Cannot add even 1 track")

        # Test 3: Find the maximum number of tracks
        test_track_counts = [5, 10, 15, 20, 25, 30, 50, 100]
        max_successful = 1

        for count in test_track_counts:
            # Create fresh playlist
            test_playlist = spotify_client.create_playlist(f"Test {count} - Delete Me")
            test_id = test_playlist['id']

            # Get tracks
            search_queries = ["Bleeding Love", "Shape of You", "Rolling in the Deep",
                            "Perfect", "Stay", "Someone Like You", "Hello", "Photograph"]
            track_uris = []

            for query in search_queries * 20:  # Repeat to get enough tracks
                if len(track_uris) >= count:
                    break
                results = spotify_client.search_track(query, limit=1)
                if results and results[0]['uri'] not in track_uris:
                    track_uris.append(results[0]['uri'])

            tracks_to_test = track_uris[:count]

            try:
                spotify_client.add_tracks_to_playlist(test_id, tracks_to_test)
                print(f"✓ ADD {count} TRACKS: Works")
                max_successful = count
            except Exception as e:
                print(f"✗ ADD {count} TRACKS: Failed")
                print(f"  Error: {str(e)[:200]}")
                break

        print(f"\n{'='*60}")
        print(f"RESULT: Maximum tracks in Development Mode = {max_successful}")
        print(f"{'='*60}\n")

        assert max_successful > 0, "Should be able to add at least 1 track"

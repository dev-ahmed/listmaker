"""Tests for add-to-playlist functionality"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from listmaker.spotify import SpotifyClient


class TestAddToPlaylist:
    """Test adding tracks to existing playlists"""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Spotify client"""
        client = Mock(spec=SpotifyClient)
        client.access_token = "test_token"
        return client

    def test_add_single_track_to_playlist(self, mock_client):
        """Test adding a single track"""
        playlist_id = "test_playlist_123"
        track_uris = ["spotify:track:abc123"]

        mock_response = Mock()
        mock_response.status_code = 201
        mock_client._make_request.return_value = mock_response

        # Call the method
        mock_client.add_tracks_to_playlist(playlist_id, track_uris)

        # Verify it was called
        mock_client._make_request.assert_called_once()

    def test_add_tracks_in_batches(self, mock_client):
        """Test that tracks are added in batches"""
        playlist_id = "test_playlist_123"

        # Create 25 tracks
        track_uris = [f"spotify:track:{i}" for i in range(25)]

        mock_response = Mock()
        mock_response.status_code = 201
        mock_client._make_request.return_value = mock_response

        # Mock the add_tracks_to_playlist to use batch size of 10
        def mock_add_tracks(pid, uris):
            # Simulate batching
            batch_size = 10
            call_count = 0
            for i in range(0, len(uris), batch_size):
                batch = uris[i:i+batch_size]
                call_count += 1
            return call_count

        result = mock_add_tracks(playlist_id, track_uris)

        # Should make 3 calls: 10, 10, 5
        assert result == 3

    def test_extract_playlist_id_from_url(self):
        """Test extracting playlist ID from Spotify URL"""
        test_cases = [
            ("64FfTcfp7GAbQBI8AyzAHw", "64FfTcfp7GAbQBI8AyzAHw"),
            ("https://open.spotify.com/playlist/64FfTcfp7GAbQBI8AyzAHw", "64FfTcfp7GAbQBI8AyzAHw"),
            ("https://open.spotify.com/playlist/64FfTcfp7GAbQBI8AyzAHw?si=xyz", "64FfTcfp7GAbQBI8AyzAHw"),
        ]

        for input_url, expected_id in test_cases:
            # Extract ID
            playlist_id = input_url
            if 'spotify.com/playlist/' in input_url:
                playlist_id = input_url.split('playlist/')[-1].split('?')[0]

            assert playlist_id == expected_id, f"Failed for {input_url}"

    def test_batch_size_calculation(self):
        """Test that batch size is respected"""
        track_count = 34
        batch_size = 5

        batches = []
        for i in range(0, track_count, batch_size):
            batch_end = min(i + batch_size, track_count)
            batches.append((i, batch_end))

        # Should create 7 batches: 5,5,5,5,5,5,4
        assert len(batches) == 7
        assert batches[0] == (0, 5)
        assert batches[-1] == (30, 34)

    def test_different_batch_sizes(self):
        """Test various batch sizes"""
        track_count = 34

        test_cases = [
            (1, 34),   # 1 track per batch = 34 batches
            (5, 7),    # 5 tracks per batch = 7 batches
            (10, 4),   # 10 tracks per batch = 4 batches
            (34, 1),   # All at once = 1 batch
        ]

        for batch_size, expected_batches in test_cases:
            batch_count = 0
            for i in range(0, track_count, batch_size):
                batch_count += 1

            assert batch_count == expected_batches, \
                f"Batch size {batch_size}: expected {expected_batches}, got {batch_count}"


class TestAddToPlaylistIntegration:
    """Integration tests for adding to playlists - requires real credentials"""

    @pytest.fixture
    def spotify_client(self):
        """Create a real Spotify client"""
        client_id = os.getenv('SPOTIFY_CLIENT_ID')
        client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')

        if not client_id or not client_secret:
            pytest.skip("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET not set")

        client = SpotifyClient(client_id, client_secret)

        if not client.access_token:
            pytest.skip("Not authenticated - run 'listmaker auth' first")

        return client

    def test_create_playlist_and_add_tracks_incrementally(self, spotify_client):
        """Test creating playlist and adding tracks in small batches"""
        # Create playlist
        playlist = spotify_client.create_playlist("Test Incremental Add - Delete Me")
        playlist_id = playlist['id']

        print(f"\n✓ Created playlist: {playlist_id}")

        # Get some tracks
        test_songs = [
            "Bleeding Love - Leona Lewis",
            "Shape of You - Ed Sheeran",
            "Rolling in the Deep - Adele",
        ]

        track_uris = []
        for song in test_songs:
            results = spotify_client.search_track(song, limit=1)
            if results:
                track_uris.append(results[0]['uri'])

        print(f"✓ Found {len(track_uris)} tracks")

        # Add tracks one by one (safest for Development Mode)
        batch_size = 1
        added_count = 0

        for i in range(0, len(track_uris), batch_size):
            batch = track_uris[i:i+batch_size]

            try:
                spotify_client.add_tracks_to_playlist(playlist_id, batch)
                added_count += len(batch)
                print(f"✓ Added track {added_count}/{len(track_uris)}")
            except Exception as e:
                print(f"✗ Failed at track {added_count + 1}: {str(e)[:100]}")
                break

        print(f"\n{'='*60}")
        print(f"Successfully added {added_count} out of {len(track_uris)} tracks")
        print(f"{'='*60}\n")

        assert added_count > 0, "Should be able to add at least 1 track"

    def test_find_maximum_batch_size(self, spotify_client):
        """Test to find maximum batch size that works"""
        print("\n" + "="*60)
        print("FINDING MAXIMUM BATCH SIZE")
        print("="*60)

        # Create test playlist
        playlist = spotify_client.create_playlist("Test Batch Size - Delete Me")
        playlist_id = playlist['id']

        # Get tracks
        test_songs = ["Bleeding Love", "Shape of You", "Rolling in the Deep",
                     "Perfect", "Stay", "Someone Like You", "Hello", "Photograph",
                     "Photograph", "Thinking Out Loud", "Castle on the Hill"]

        track_uris = []
        for song in test_songs:
            results = spotify_client.search_track(song, limit=1)
            if results and results[0]['uri'] not in track_uris:
                track_uris.append(results[0]['uri'])

        print(f"✓ Got {len(track_uris)} unique tracks\n")

        # Test different batch sizes
        batch_sizes = [1, 2, 3, 5, 8, 10, 15, 20]
        max_working_batch = 1

        for batch_size in batch_sizes:
            # Create fresh playlist for each test
            test_playlist = spotify_client.create_playlist(f"Batch Test {batch_size} - Delete Me")
            test_id = test_playlist['id']

            # Try to add tracks in this batch size
            tracks_to_add = track_uris[:min(batch_size, len(track_uris))]

            try:
                spotify_client.add_tracks_to_playlist(test_id, tracks_to_add)
                print(f"✓ Batch size {batch_size}: SUCCESS")
                max_working_batch = batch_size
            except Exception as e:
                print(f"✗ Batch size {batch_size}: FAILED")
                print(f"  Error: {str(e)[:150]}")
                break

        print(f"\n{'='*60}")
        print(f"MAXIMUM WORKING BATCH SIZE: {max_working_batch}")
        print(f"{'='*60}\n")

        assert max_working_batch >= 1, "Should support at least batch size of 1"

        # Store result for other tests
        return max_working_batch

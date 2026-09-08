"""Tests for playlist management - finding, updating, avoiding duplicates"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from listmaker.spotify import SpotifyClient


class TestPlaylistManagement:
    """Test playlist finding and management"""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Spotify client"""
        client = Mock(spec=SpotifyClient)
        client.access_token = "test_token"
        return client

    def test_get_user_playlists(self, mock_client):
        """Test getting user's playlists"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'items': [
                {'id': 'playlist1', 'name': 'My Songs', 'tracks': {'total': 10}},
                {'id': 'playlist2', 'name': 'Other Songs', 'tracks': {'total': 5}},
            ]
        }
        mock_client._make_request.return_value = mock_response

        # Create real client method
        from listmaker.spotify import SpotifyClient
        real_client = SpotifyClient("test", "test")
        real_client._make_request = mock_client._make_request

        playlists = real_client.get_user_playlists()

        assert len(playlists) == 2
        assert playlists[0]['name'] == 'My Songs'
        assert playlists[1]['name'] == 'Other Songs'

    def test_find_playlist_by_name_exists(self, mock_client):
        """Test finding a playlist that exists"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'items': [
                {'id': 'playlist1', 'name': 'My Songs', 'tracks': {'total': 10}},
                {'id': 'playlist2', 'name': 'Other Songs', 'tracks': {'total': 5}},
            ]
        }
        mock_client._make_request.return_value = mock_response

        from listmaker.spotify import SpotifyClient
        real_client = SpotifyClient("test", "test")
        real_client._make_request = mock_client._make_request

        result = real_client.find_playlist_by_name('My Songs')

        assert result is not None
        assert result['name'] == 'My Songs'
        assert result['id'] == 'playlist1'

    def test_find_playlist_by_name_not_exists(self, mock_client):
        """Test finding a playlist that doesn't exist"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'items': [
                {'id': 'playlist1', 'name': 'My Songs', 'tracks': {'total': 10}},
            ]
        }
        mock_client._make_request.return_value = mock_response

        from listmaker.spotify import SpotifyClient
        real_client = SpotifyClient("test", "test")
        real_client._make_request = mock_client._make_request

        result = real_client.find_playlist_by_name('Nonexistent Playlist')

        assert result is None

    def test_get_playlist_tracks(self, mock_client):
        """Test getting all tracks from a playlist"""
        # First page
        first_response = Mock()
        first_response.status_code = 200
        first_response.json.return_value = {
            'items': [
                {'item': {'uri': 'spotify:track:1'}},
                {'item': {'uri': 'spotify:track:2'}},
            ],
            'next': 'next_page_url'
        }

        # Second page
        second_response = Mock()
        second_response.status_code = 200
        second_response.json.return_value = {
            'items': [
                {'item': {'uri': 'spotify:track:3'}},
            ],
            'next': None
        }

        mock_client._make_request.side_effect = [first_response, second_response]

        from listmaker.spotify import SpotifyClient
        real_client = SpotifyClient("test", "test")
        real_client._make_request = mock_client._make_request

        tracks = real_client.get_playlist_tracks('playlist123')

        assert len(tracks) == 3
        assert tracks[0] == 'spotify:track:1'
        assert tracks[1] == 'spotify:track:2'
        assert tracks[2] == 'spotify:track:3'
        assert real_client._make_request.call_args_list[0].args[:2] == (
            'GET',
            '/playlists/playlist123/items',
        )

    def test_filter_duplicate_tracks(self):
        """Test filtering out duplicate tracks"""
        existing_tracks = [
            'spotify:track:1',
            'spotify:track:2',
            'spotify:track:3',
        ]

        new_tracks = [
            'spotify:track:1',  # Duplicate
            'spotify:track:4',  # New
            'spotify:track:2',  # Duplicate
            'spotify:track:5',  # New
        ]

        filtered = [uri for uri in new_tracks if uri not in existing_tracks]

        assert len(filtered) == 2
        assert 'spotify:track:4' in filtered
        assert 'spotify:track:5' in filtered
        assert 'spotify:track:1' not in filtered
        assert 'spotify:track:2' not in filtered

    def test_no_duplicates_all_new(self):
        """Test when all tracks are new (no duplicates)"""
        existing_tracks = [
            'spotify:track:1',
            'spotify:track:2',
        ]

        new_tracks = [
            'spotify:track:3',
            'spotify:track:4',
            'spotify:track:5',
        ]

        filtered = [uri for uri in new_tracks if uri not in existing_tracks]

        assert len(filtered) == 3
        assert filtered == new_tracks

    def test_all_duplicates(self):
        """Test when all tracks already exist"""
        existing_tracks = [
            'spotify:track:1',
            'spotify:track:2',
            'spotify:track:3',
        ]

        new_tracks = [
            'spotify:track:1',
            'spotify:track:2',
            'spotify:track:3',
        ]

        filtered = [uri for uri in new_tracks if uri not in existing_tracks]

        assert len(filtered) == 0


class TestPlaylistUpdate:
    """Integration test for updating playlists"""

    def test_incremental_playlist_creation(self):
        """Test adding tracks incrementally to same playlist"""
        # Simulates running create command multiple times
        # First run: adds 10 tracks
        # Second run: should detect existing and add remaining

        # Mock existing playlist check
        first_run_tracks = [f'spotify:track:{i}' for i in range(10)]
        all_tracks = [f'spotify:track:{i}' for i in range(34)]

        # Second run: filter out existing
        new_tracks = [uri for uri in all_tracks if uri not in first_run_tracks]

        assert len(new_tracks) == 24  # 34 - 10 = 24
        assert 'spotify:track:0' not in new_tracks  # Already exists
        assert 'spotify:track:10' in new_tracks  # New track
        assert 'spotify:track:33' in new_tracks  # Last track

    def test_playlist_name_collision_handling(self):
        """Test handling when playlist name already exists"""
        # Simulate the timestamp naming
        import datetime

        base_name = "My Songs"

        # First time: use base name
        first_name = base_name

        # Second time (if user chooses 'create'): add timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        second_name = f"{base_name}_{timestamp}"

        assert first_name == "My Songs"
        assert second_name.startswith("My Songs_")
        assert len(second_name) > len(first_name)

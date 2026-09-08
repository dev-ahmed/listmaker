"""Tests for Spotify API integration"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from listmaker.spotify import SpotifyClient


class TestSpotifyClient:
    @pytest.fixture
    def client(self):
        """Create a test client"""
        return SpotifyClient("test_client_id", "test_client_secret")

    def test_generate_code_verifier(self, client):
        """Test PKCE code verifier generation"""
        verifier = client._generate_code_verifier()
        assert len(verifier) > 0
        assert isinstance(verifier, str)

    def test_generate_code_challenge(self, client):
        """Test PKCE code challenge generation"""
        verifier = "test_verifier"
        challenge = client._generate_code_challenge(verifier)
        assert len(challenge) > 0
        assert isinstance(challenge, str)

    @patch('listmaker.spotify.requests.request')
    def test_search_track_success(self, mock_request, client):
        """Test successful track search"""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'tracks': {
                'items': [
                    {
                        'name': 'Bleeding Love',
                        'artists': [{'name': 'Leona Lewis'}],
                        'uri': 'spotify:track:123',
                        'popularity': 72
                    }
                ]
            }
        }
        mock_request.return_value = mock_response

        # Set access token
        client.access_token = "test_token"

        # Search
        results = client.search_track("Bleeding Love - Leona Lewis")

        assert len(results) == 1
        assert results[0]['name'] == 'Bleeding Love'
        assert results[0]['artists'][0]['name'] == 'Leona Lewis'

    @patch('listmaker.spotify.requests.request')
    def test_search_track_invalid_limit_error(self, mock_request, client):
        """Test handling of invalid limit error"""
        # Mock 400 Bad Request response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = '{"error": {"status": 400, "message": "Invalid limit"}}'
        mock_request.return_value = mock_response

        client.access_token = "test_token"

        with pytest.raises(Exception) as exc_info:
            client.search_track("Test Song")

        assert "Invalid limit" in str(exc_info.value)

    @patch('listmaker.spotify.requests.request')
    def test_search_podcast_success(self, mock_request, client):
        """Test podcast-only search"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'episodes': {
                'items': [{
                    'name': 'Test Episode',
                    'show': {'name': 'Test Podcast'},
                    'uri': 'spotify:episode:123',
                    'type': 'episode'
                }]
            }
        }
        mock_request.return_value = mock_response
        client.access_token = "test_token"

        results = client.search_track("Test Episode", item_type="episode")

        assert results[0]['type'] == 'episode'
        assert mock_request.call_args.kwargs['params']['type'] == 'episode'

    @patch('listmaker.spotify.requests.request')
    def test_get_user_id(self, mock_request, client):
        """Test getting user ID"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'id': 'test_user_id'}
        mock_request.return_value = mock_response

        client.access_token = "test_token"
        user_id = client.get_user_id()

        assert user_id == 'test_user_id'

    @patch('listmaker.spotify.requests.request')
    def test_create_playlist_success(self, mock_request, client):
        """Test successful playlist creation"""
        # Mock user ID request
        user_response = Mock()
        user_response.status_code = 200
        user_response.json.return_value = {'id': 'test_user'}

        # Mock playlist creation request
        playlist_response = Mock()
        playlist_response.status_code = 201
        playlist_response.json.return_value = {
            'id': 'playlist123',
            'name': 'Test Playlist',
            'external_urls': {'spotify': 'https://open.spotify.com/playlist/123'}
        }

        mock_request.side_effect = [user_response, playlist_response]

        client.access_token = "test_token"
        playlist = client.create_playlist("Test Playlist")

        assert playlist['id'] == 'playlist123'
        assert playlist['name'] == 'Test Playlist'

    @patch('listmaker.spotify.requests.request')
    def test_create_playlist_forbidden(self, mock_request, client):
        """Test 403 Forbidden error when creating playlist"""
        # Mock user ID request
        user_response = Mock()
        user_response.status_code = 200
        user_response.json.return_value = {'id': 'test_user'}

        # Mock 403 response
        forbidden_response = Mock()
        forbidden_response.status_code = 403
        forbidden_response.text = '{"error": {"status": 403, "message": "Forbidden"}}'

        mock_request.side_effect = [user_response, forbidden_response]

        client.access_token = "test_token"

        with pytest.raises(Exception) as exc_info:
            client.create_playlist("Test Playlist")

        assert "403 Forbidden" in str(exc_info.value)
        assert "Development Mode" in str(exc_info.value)

    @patch('listmaker.spotify.requests.request')
    def test_add_tracks_to_playlist(self, mock_request, client):
        """Test adding tracks to playlist"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_request.return_value = mock_response

        client.access_token = "test_token"
        track_uris = ['spotify:track:1', 'spotify:track:2']

        # Should not raise exception
        client.add_tracks_to_playlist('playlist123', track_uris)
        assert mock_request.call_args.args[:2] == (
            'POST',
            'https://api.spotify.com/v1/playlists/playlist123/items',
        )

    @patch('listmaker.spotify.requests.request')
    def test_add_tracks_batching(self, mock_request, client):
        """Test that large track lists are batched (max 100 per request)"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_request.return_value = mock_response

        client.access_token = "test_token"

        # Create 150 tracks (should be 2 requests)
        track_uris = [f'spotify:track:{i}' for i in range(150)]

        client.add_tracks_to_playlist('playlist123', track_uris)

        # Should make 2 API calls (100 + 50)
        assert mock_request.call_count == 2

    @patch('listmaker.spotify.requests.request')
    def test_token_refresh_on_401(self, mock_request, client):
        """Test automatic token refresh on 401 Unauthorized"""
        # First request returns 401
        unauthorized_response = Mock()
        unauthorized_response.status_code = 401

        # Refresh token request
        refresh_response = Mock()
        refresh_response.status_code = 200
        refresh_response.json.return_value = {
            'access_token': 'new_token',
            'refresh_token': 'new_refresh_token'
        }

        # Second request succeeds
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {'id': 'test_user'}

        mock_request.side_effect = [unauthorized_response, refresh_response, success_response]

        client.access_token = "old_token"
        client.refresh_token = "refresh_token"

        user_id = client.get_user_id()

        assert user_id == 'test_user'
        assert client.access_token == 'new_token'

"""Spotify API integration with OAuth PKCE flow"""
import json
import hashlib
import base64
import secrets
import webbrowser
from pathlib import Path
from typing import Optional, Dict, Any, List
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, parse_qs, urlparse
import requests


CONFIG_DIR = Path.home() / ".config" / "listmaker"
TOKEN_FILE = CONFIG_DIR / "tokens.json"
CACHE_FILE = CONFIG_DIR / "cache.json"

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = [
    "user-read-email",
    "user-read-private",
    "playlist-modify-public",
    "playlist-modify-private",
    "playlist-read-private"
]


class CallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback"""
    auth_code = None

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        if 'code' in query:
            CallbackHandler.auth_code = query['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>Authentication successful! You can close this window.</h1></body></html>')
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        pass


class SpotifyClient:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._load_tokens()

    def _load_tokens(self):
        """Load saved tokens from disk"""
        if TOKEN_FILE.exists():
            try:
                with open(TOKEN_FILE) as f:
                    data = json.load(f)
                    self.access_token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")
            except Exception:
                pass

    def _save_tokens(self):
        """Save tokens to disk"""
        with open(TOKEN_FILE, 'w') as f:
            json.dump({
                "access_token": self.access_token,
                "refresh_token": self.refresh_token
            }, f)

    def _generate_code_verifier(self) -> str:
        """Generate PKCE code verifier"""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

    def _generate_code_challenge(self, verifier: str) -> str:
        """Generate PKCE code challenge from verifier"""
        digest = hashlib.sha256(verifier.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')

    def authenticate(self):
        """Perform OAuth flow with PKCE"""
        code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(code_verifier)

        # Build authorization URL
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': REDIRECT_URI,
            'scope': ' '.join(SCOPES),
            'code_challenge_method': 'S256',
            'code_challenge': code_challenge
        }
        auth_url = f"{SPOTIFY_AUTH_URL}?{urlencode(params)}"

        print(f"\nOpening browser for Spotify authentication...")
        print(f"If browser doesn't open, visit:\n{auth_url}\n")
        webbrowser.open(auth_url)

        # Start local server to receive callback
        server = HTTPServer(('127.0.0.1', 8888), CallbackHandler)
        server.handle_request()

        if not CallbackHandler.auth_code:
            raise Exception("Failed to receive authorization code")

        # Exchange code for tokens
        token_data = {
            'client_id': self.client_id,
            'grant_type': 'authorization_code',
            'code': CallbackHandler.auth_code,
            'redirect_uri': REDIRECT_URI,
            'code_verifier': code_verifier
        }

        response = requests.post(SPOTIFY_TOKEN_URL, data=token_data)
        if response.status_code != 200:
            raise Exception(f"Token exchange failed: {response.text}")

        tokens = response.json()
        self.access_token = tokens['access_token']
        self.refresh_token = tokens.get('refresh_token')
        self._save_tokens()

        print("✓ Authentication successful!\n")

    def _refresh_access_token(self):
        """Refresh expired access token"""
        if not self.refresh_token:
            raise Exception("No refresh token available")

        token_data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.client_id
        }

        response = requests.post(SPOTIFY_TOKEN_URL, data=token_data)
        if response.status_code != 200:
            raise Exception("Token refresh failed")

        tokens = response.json()
        self.access_token = tokens['access_token']
        if 'refresh_token' in tokens:
            self.refresh_token = tokens['refresh_token']
        self._save_tokens()

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make authenticated API request with automatic token refresh"""
        if not self.access_token:
            raise Exception("Not authenticated. Run 'musiclist auth' first.")

        headers = kwargs.pop('headers', {})
        headers['Authorization'] = f'Bearer {self.access_token}'

        url = f"{SPOTIFY_API_BASE}/{endpoint.lstrip('/')}"
        response = requests.request(method, url, headers=headers, **kwargs)

        # Try to refresh token if unauthorized
        if response.status_code == 401 and self.refresh_token:
            self._refresh_access_token()
            headers['Authorization'] = f'Bearer {self.access_token}'
            response = requests.request(method, url, headers=headers, **kwargs)

        return response

    def search_track(
        self,
        query: str,
        limit: int = 10,
        item_type: str = 'track'
    ) -> List[Dict[str, Any]]:
        """Search for tracks or podcast episodes on Spotify"""
        params = {
            'q': query,
            'type': item_type
        }
        # Only add limit if it's valid (1-50, but dev mode may restrict to 10)
        if 1 <= limit <= 10:
            params['limit'] = limit
        response = self._make_request('GET', '/search', params=params)

        if response.status_code != 200:
            raise Exception(f"Search failed: {response.text}")

        return response.json()[f'{item_type}s']['items']

    def get_user_id(self) -> str:
        """Get current user's Spotify ID"""
        response = self._make_request('GET', '/me')
        if response.status_code != 200:
            raise Exception(f"Failed to get user info: {response.text}")
        return response.json()['id']

    def create_playlist(self, name: str, description: str = "") -> Dict[str, Any]:
        """Create a new playlist"""
        user_id = self.get_user_id()

        # Try the newer endpoint first (v1/me/playlists)
        data = {
            'name': name,
            'description': description,
            'public': False  # Use private playlist for Development Mode compatibility
        }

        response = self._make_request('POST', '/me/playlists', json=data)

        if response.status_code == 403:
            # Get user email for debugging
            user_info = self._make_request('GET', '/me').json()
            user_email = user_info.get('email', 'unknown')

            raise Exception(
                f"403 Forbidden - Development Mode restriction.\n\n"
                f"Currently authenticated as: {user_email}\n\n"
                f"Solutions:\n\n"
                f"Option 1 - Request Extended Quota Mode (RECOMMENDED):\n"
                f"  1. Go to https://developer.spotify.com/dashboard\n"
                f"  2. Click your app → 'Request Extension'\n"
                f"  3. Explain it's a personal CLI tool\n"
                f"  4. Wait for approval\n\n"
                f"Option 2 - Verify Development Mode setup:\n"
                f"  1. Go to https://developer.spotify.com/dashboard\n"
                f"  2. Click your app → 'Users and Access'\n"
                f"  3. Verify '{user_email}' is listed\n"
                f"  4. If not, add it and re-run: listmaker clear-auth && listmaker auth"
            )

        if response.status_code != 201:
            raise Exception(f"Failed to create playlist: {response.text}")

        return response.json()

    def get_playlist_info(self, playlist_id: str) -> Dict[str, Any]:
        """Get playlist information including track count"""
        response = self._make_request('GET', f'/playlists/{playlist_id}')
        if response.status_code != 200:
            raise Exception(f"Failed to get playlist info: {response.text}")
        return response.json()

    def get_user_playlists(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's playlists"""
        response = self._make_request('GET', f'/me/playlists', params={'limit': limit})
        if response.status_code != 200:
            raise Exception(f"Failed to get playlists: {response.text}")
        return response.json()['items']

    def find_playlist_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find a playlist by name"""
        playlists = self.get_user_playlists()
        for playlist in playlists:
            if playlist['name'] == name:
                return playlist
        return None

    def get_playlist_tracks(self, playlist_id: str) -> List[str]:
        """Get all track URIs in a playlist"""
        track_uris = []
        offset = 0
        limit = 100

        while True:
            response = self._make_request('GET', f'/playlists/{playlist_id}/items',
                                        params={'offset': offset, 'limit': limit})
            if response.status_code != 200:
                raise Exception(f"Failed to get playlist tracks: {response.text}")

            data = response.json()
            for item in data['items']:
                if item['item']:
                    track_uris.append(item['item']['uri'])

            if not data['next']:
                break
            offset += limit

        return track_uris

    def add_tracks_to_playlist(self, playlist_id: str, track_uris: List[str], batch_size: int = None):
        """Add tracks to a playlist

        Args:
            playlist_id: Spotify playlist ID
            track_uris: List of track URIs to add
            batch_size: Number of tracks per batch (None = auto-detect, tries smaller batches on 403)
        """
        # If batch_size specified, use it; otherwise use conservative default
        if batch_size is None:
            batch_size = 10

        for i in range(0, len(track_uris), batch_size):
            chunk = track_uris[i:i+batch_size]
            data = {'uris': chunk}

            response = self._make_request('POST', f'/playlists/{playlist_id}/items', json=data)

            if response.status_code == 403:
                # Development Mode restriction - raise with info about which batch failed
                tracks_added = i
                tracks_remaining = len(track_uris) - i

                raise Exception(
                    f"403 Forbidden after adding {tracks_added} tracks.\n"
                    f"Development Mode may limit total tracks or batch size.\n"
                    f"Remaining tracks: {tracks_remaining}"
                )

            if response.status_code not in [200, 201]:
                raise Exception(f"Failed to add tracks (batch starting at {i}): {response.text}")

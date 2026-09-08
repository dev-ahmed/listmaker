"""Tests for CLI functionality"""
import pytest
from unittest.mock import patch, MagicMock
from listmaker.cli import cache_key, interactive_select, format_track


class TestInteractiveSelect:
    def test_interactive_select_valid_choice(self):
        """Test selecting option 1"""
        alternatives = [
            ({"name": "Song 1", "artists": [{"name": "Artist 1"}], "popularity": 80, "uri": "spotify:track:1"}, 0.9),
            ({"name": "Song 2", "artists": [{"name": "Artist 2"}], "popularity": 70, "uri": "spotify:track:2"}, 0.8),
        ]

        with patch('listmaker.cli.readchar.readkey', side_effect=['1', '\r']):
            result = interactive_select("Test Song", "Test Artist", alternatives)
            assert result == ["spotify:track:1"]

    def test_interactive_select_skip(self):
        """Test skipping selection"""
        alternatives = [
            ({"name": "Song 1", "artists": [{"name": "Artist 1"}], "popularity": 80, "uri": "spotify:track:1"}, 0.9),
        ]

        with patch('listmaker.cli.readchar.readkey', return_value='s'):
            result = interactive_select("Test Song", "Test Artist", alternatives)
            assert result is None

    def test_interactive_select_invalid_then_valid(self):
        """Test invalid input followed by valid input"""
        alternatives = [
            ({"name": "Song 1", "artists": [{"name": "Artist 1"}], "popularity": 80, "uri": "spotify:track:1"}, 0.9),
        ]

        with patch('listmaker.cli.readchar.readkey', side_effect=['99', '1', '\r']):
            result = interactive_select("Test Song", "Test Artist", alternatives)
            assert result == ["spotify:track:1"]

    def test_interactive_select_case_insensitive(self):
        """Test that 'S' and 's' both work for skip"""
        alternatives = [
            ({"name": "Song 1", "artists": [{"name": "Artist 1"}], "popularity": 80, "uri": "spotify:track:1"}, 0.9),
        ]

        with patch('listmaker.cli.readchar.readkey', return_value='S'):
            result = interactive_select("Test Song", "Test Artist", alternatives)
            assert result is None

    @pytest.mark.parametrize("choice", ["1.", "١"])
    def test_interactive_select_flexible_number(self, choice):
        alternatives = [
            ({"name": "Song 1", "artists": [{"name": "Artist 1"}], "uri": "spotify:track:1"}, 0.9),
        ]

        with patch('listmaker.cli.readchar.readkey', side_effect=[choice, '\r']):
            result = interactive_select("Test Song", "Test Artist", alternatives)
            assert result == ["spotify:track:1"]

    def test_interactive_select_multiple(self):
        alternatives = [
            ({"name": "Song 1", "artists": [], "uri": "spotify:track:1"}, 0.9),
            ({"name": "Song 2", "artists": [], "uri": "spotify:track:2"}, 0.8),
        ]

        with patch('listmaker.cli.readchar.readkey', side_effect=['1', '2', '\r']):
            result = interactive_select("Test Song", None, alternatives)
            assert result == ["spotify:track:1", "spotify:track:2"]

    def test_interactive_select_empty_defaults_to_skip(self):
        """Test that empty input defaults to skip"""
        alternatives = [
            ({"name": "Song 1", "artists": [{"name": "Artist 1"}], "popularity": 80, "uri": "spotify:track:1"}, 0.9),
        ]

        with patch('listmaker.cli.readchar.readkey', return_value=''):
            result = interactive_select("Test Song", "Test Artist", alternatives)
            assert result is None


class TestFormatTrack:
    def test_format_track_basic(self):
        track = {
            "name": "Bleeding Love",
            "type": "track",
            "artists": [{"name": "Leona Lewis"}],
            "popularity": 72
        }
        result = format_track(track)
        assert "Bleeding Love" in result
        assert "[track]" in result
        assert "Leona Lewis" in result
        assert "72" in result

    def test_format_track_multiple_artists(self):
        track = {
            "name": "Just Give Me a Reason",
            "artists": [{"name": "P!nk"}, {"name": "Nate Ruess"}],
            "popularity": 80
        }
        result = format_track(track)
        assert "P!nk" in result
        assert "Nate Ruess" in result
        assert "," in result

    def test_format_track_arabic(self):
        track = {
            "name": "خابط نفسي بسلاح حامي",
            "type": "track",
            "artists": [{"name": "Magdy El Zahar"}],
            "popularity": 0
        }
        result = format_track(track)
        assert result.startswith("[track]")
        assert "ﻂﺑﺎﺧ" in result

    def test_format_podcast(self):
        episode = {
            "name": "Test Episode",
            "type": "episode",
            "show": {"name": "Test Podcast"}
        }
        result = format_track(episode)
        assert result.startswith("[episode]")
        assert "Test Podcast" in result


def test_podcast_cache_is_separate():
    song_key = cache_key("Same title", None, "track")
    podcast_key = cache_key("Same title", None, "episode")
    assert song_key != podcast_key

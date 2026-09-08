"""Tests for song matching logic"""
import pytest
from listmaker.matcher import (
    normalize_string,
    parse_song_line,
    similarity_score,
    is_undesirable_version,
    score_track,
    read_song_file,
    read_song_text
)


class TestNormalization:
    def test_normalize_string_lowercase(self):
        assert normalize_string("Bleeding Love") == "bleeding love"

    def test_normalize_string_punctuation(self):
        assert normalize_string("P!nk") == "pnk"
        assert normalize_string("Can't Stop") == "cant stop"

    def test_normalize_string_ampersand(self):
        assert normalize_string("Salt & Pepper") == "salt and pepper"

    def test_normalize_string_featuring(self):
        assert "featuring" in normalize_string("Song feat. Artist")
        assert "featuring" in normalize_string("Song ft. Artist")

    def test_normalize_string_whitespace(self):
        assert normalize_string("  Too   Much   Space  ") == "too much space"


class TestParsing:
    def test_parse_song_line_with_separator(self):
        title, artist = parse_song_line("Bleeding Love - Leona Lewis")
        assert title == "Bleeding Love"
        assert artist == "Leona Lewis"

    def test_parse_song_line_without_separator(self):
        title, artist = parse_song_line("Bleeding Love")
        assert title == "Bleeding Love"
        assert artist is None

    def test_parse_song_line_empty(self):
        title, artist = parse_song_line("")
        assert title is None
        assert artist is None

    def test_parse_song_line_comment(self):
        title, artist = parse_song_line("# This is a comment")
        assert title is None
        assert artist is None

    def test_parse_song_line_whitespace(self):
        title, artist = parse_song_line("  Shape of You  -  Ed Sheeran  ")
        assert title == "Shape of You"
        assert artist == "Ed Sheeran"


class TestSimilarity:
    def test_similarity_exact_match(self):
        score = similarity_score("Bleeding Love", "Bleeding Love")
        assert score == 1.0

    def test_similarity_different_case(self):
        score = similarity_score("Bleeding Love", "bleeding love")
        assert score == 1.0

    def test_similarity_partial_match(self):
        score = similarity_score("Bleeding Love", "Bleeding")
        assert 0.5 < score < 1.0

    def test_similarity_no_match(self):
        score = similarity_score("Bleeding Love", "Shape of You")
        assert score < 0.3


class TestUndesirableVersions:
    def test_karaoke_version(self):
        assert is_undesirable_version("Bleeding Love - Karaoke Version")

    def test_live_version(self):
        assert is_undesirable_version("Bleeding Love (Live)")

    def test_remix_version(self):
        assert is_undesirable_version("Bleeding Love - Remix")

    def test_instrumental_version(self):
        assert is_undesirable_version("Bleeding Love - Instrumental")

    def test_sped_up_version(self):
        assert is_undesirable_version("Bleeding Love (Sped Up)")

    def test_acoustic_version(self):
        assert is_undesirable_version("Bleeding Love - Acoustic")

    def test_original_version(self):
        assert not is_undesirable_version("Bleeding Love")


class TestTrackScoring:
    def test_score_track_exact_match(self):
        track = {
            "name": "Bleeding Love",
            "artists": [{"name": "Leona Lewis"}],
            "popularity": 80
        }
        score = score_track(track, "Bleeding Love", "Leona Lewis")
        assert score > 0.9

    def test_score_track_no_artist_provided(self):
        track = {
            "name": "Bleeding Love",
            "artists": [{"name": "Leona Lewis"}],
            "popularity": 80
        }
        score = score_track(track, "Bleeding Love", None)
        assert score > 0.7

    def test_score_track_wrong_artist(self):
        track = {
            "name": "Bleeding Love",
            "artists": [{"name": "Wrong Artist"}],
            "popularity": 80
        }
        score = score_track(track, "Bleeding Love", "Leona Lewis")
        assert score < 0.7

    def test_score_track_undesirable_version_penalty(self):
        track_original = {
            "name": "Bleeding Love",
            "artists": [{"name": "Leona Lewis"}],
            "popularity": 80
        }
        track_karaoke = {
            "name": "Bleeding Love - Karaoke",
            "artists": [{"name": "Leona Lewis"}],
            "popularity": 80
        }
        score_original = score_track(track_original, "Bleeding Love", "Leona Lewis")
        score_karaoke = score_track(track_karaoke, "Bleeding Love", "Leona Lewis")
        assert score_original > score_karaoke

    def test_score_track_popularity_influence(self):
        track_popular = {
            "name": "Shape of You",
            "artists": [{"name": "Ed Sheeran"}],
            "popularity": 95
        }
        track_unpopular = {
            "name": "Shape of You",
            "artists": [{"name": "Ed Sheeran"}],
            "popularity": 20
        }
        score_popular = score_track(track_popular, "Shape of You", "Ed Sheeran")
        score_unpopular = score_track(track_unpopular, "Shape of You", "Ed Sheeran")
        assert score_popular > score_unpopular


class TestFileReading:
    def test_read_song_text(self):
        songs = read_song_text("Song One - Artist One\nSong Two\n")
        assert songs == [
            ("Song One", "Artist One", "Song One - Artist One"),
            ("Song Two", None, "Song Two"),
        ]

    def test_read_song_file(self, tmp_path):
        # Create test file
        test_file = tmp_path / "test_songs.txt"
        test_file.write_text("""# Test song list
Bleeding Love - Leona Lewis
Shape of You - Ed Sheeran

Rolling in the Deep - Adele
# Comment
Just Give Me a Reason - P!nk
""")

        songs = read_song_file(str(test_file))

        assert len(songs) == 4
        assert songs[0] == ("Bleeding Love", "Leona Lewis", "Bleeding Love - Leona Lewis")
        assert songs[1] == ("Shape of You", "Ed Sheeran", "Shape of You - Ed Sheeran")
        assert songs[2] == ("Rolling in the Deep", "Adele", "Rolling in the Deep - Adele")
        assert songs[3] == ("Just Give Me a Reason", "P!nk", "Just Give Me a Reason - P!nk")

    def test_read_song_file_with_no_artist(self, tmp_path):
        test_file = tmp_path / "test_songs.txt"
        test_file.write_text("Bleeding Love\nShape of You\n")

        songs = read_song_file(str(test_file))

        assert len(songs) == 2
        assert songs[0] == ("Bleeding Love", None, "Bleeding Love")
        assert songs[1] == ("Shape of You", None, "Shape of You")

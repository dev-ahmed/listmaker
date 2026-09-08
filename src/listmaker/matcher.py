"""Song matching and scoring logic"""
import re
from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher


def normalize_string(s: str) -> str:
    """Normalize string for comparison"""
    s = s.lower()
    # Replace common patterns
    s = s.replace(' & ', ' and ')
    s = re.sub(r'\bfeat\.?\b', 'featuring', s)
    s = re.sub(r'\bft\.?\b', 'featuring', s)
    # Remove punctuation except spaces
    s = re.sub(r'[^\w\s]', '', s)
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def parse_song_line(line: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse a song line into title and artist

    Returns:
        (title, artist) or (query, None) if no separator found
    """
    line = line.strip()

    # Ignore empty lines and comments
    if not line or line.startswith('#'):
        return None, None

    # Try to split on ' - '
    if ' - ' in line:
        parts = line.split(' - ', 1)
        title = parts[0].strip()
        artist = parts[1].strip() if len(parts) > 1 else None
        return title, artist

    # No separator, use whole line as search query
    return line, None


def similarity_score(a: str, b: str) -> float:
    """Calculate similarity between two strings (0-1)"""
    return SequenceMatcher(None, normalize_string(a), normalize_string(b)).ratio()


def is_undesirable_version(track_name: str) -> bool:
    """Check if track name suggests an undesirable version"""
    name_lower = track_name.lower()

    undesirable_keywords = [
        'karaoke',
        'instrumental',
        'acapella',
        'tribute',
        'cover version',
        'sped up',
        'slowed',
        'nightcore',
        '8d audio',
        'remix',  # Can be controversial, but usually we want originals
        'live',
        'acoustic',  # Sometimes desirable, but prefer studio
        'demo',
        'remaster'  # Prefer original unless specifically requested
    ]

    for keyword in undesirable_keywords:
        if keyword in name_lower:
            return True

    return False


def score_track(
    track: Dict[str, Any],
    query_title: str,
    query_artist: Optional[str] = None
) -> float:
    """Score how well a Spotify track matches the query

    Returns:
        Score from 0-1, where 1 is perfect match
    """
    track_name = track['name']
    track_artists = [a['name'] for a in track.get('artists', [])]
    if not track_artists and track.get('show', {}).get('name'):
        track_artists = [track['show']['name']]
    track_popularity = track.get('popularity', 0)  # 0-100

    # Title similarity (most important)
    title_score = similarity_score(query_title, track_name)

    # Artist similarity (if provided)
    artist_score = 0.0
    if query_artist and track_artists:
        # Check all artists, take best match
        artist_scores = [similarity_score(query_artist, artist) for artist in track_artists]
        artist_score = max(artist_scores)

    # Popularity bonus (normalized to 0-1)
    popularity_score = track_popularity / 100.0

    # Penalize undesirable versions
    version_penalty = 0.3 if is_undesirable_version(track_name) else 0.0

    # Weighted combination
    if query_artist:
        # If artist specified, weight it heavily
        score = (title_score * 0.5) + (artist_score * 0.35) + (popularity_score * 0.15)
    else:
        # No artist, rely more on title and popularity
        score = (title_score * 0.7) + (popularity_score * 0.3)

    # Apply penalty
    score = max(0, score - version_penalty)

    return score


def find_best_match(
    tracks: List[Dict[str, Any]],
    query_title: str,
    query_artist: Optional[str] = None,
    confidence_threshold: float = 0.75
) -> Tuple[Optional[Dict[str, Any]], float, List[Tuple[Dict[str, Any], float]]]:
    """Find best matching track from search results

    Returns:
        (best_track, confidence, top_alternatives)
        - best_track: The best match (or None)
        - confidence: Score of best match (0-1)
        - top_alternatives: List of (track, score) for top 5 alternatives
    """
    if not tracks:
        return None, 0.0, []

    # Score all tracks
    scored_tracks = [(track, score_track(track, query_title, query_artist)) for track in tracks]

    # Sort by score descending
    scored_tracks.sort(key=lambda x: x[1], reverse=True)

    best_track, best_score = scored_tracks[0]
    top_alternatives = scored_tracks[:5]

    # Check confidence
    if best_score < confidence_threshold:
        return None, best_score, top_alternatives

    return best_track, best_score, top_alternatives


def read_song_text(text: str) -> List[Tuple[str, Optional[str], str]]:
    """Parse songs or podcasts from multiline text."""
    parsed_lines = (
        (parse_song_line(line), line.strip())
        for line in text.splitlines()
    )
    return [
        (title, artist, original_line)
        for ((title, artist), original_line) in parsed_lines
        if title
    ]


def read_song_file(file_path: str) -> List[Tuple[str, Optional[str], str]]:
    """Read and parse a song or podcast file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return read_song_text(f.read())

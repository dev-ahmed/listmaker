"""CLI interface for listmaker"""
import os
import sys
import json
import time
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

import typer
import readchar
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn

from .spotify import SpotifyClient, CONFIG_DIR, CACHE_FILE
from .matcher import read_song_file, read_song_text, find_best_match, normalize_string
from .utils import format_terminal_text, parse_selection


app = typer.Typer(help="Convert text lists into music playlists (Spotify, Anghami) - supports songs and podcasts")
console = Console()


def get_credentials() -> Tuple[str, str]:
    """Get Spotify credentials from environment"""
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')

    if not client_id or not client_secret:
        console.print("[red]Spotify credentials are not configured.[/red]\n")
        console.print("Set the following environment variables:")
        console.print("  SPOTIFY_CLIENT_ID=your_client_id")
        console.print("  SPOTIFY_CLIENT_SECRET=your_client_secret\n")
        console.print("Get credentials from: https://developer.spotify.com/dashboard\n")
        raise typer.Exit(1)

    return client_id, client_secret


def load_cache() -> Dict[str, Any]:
    """Load song cache"""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(cache: Dict[str, Any]):
    """Save song cache"""
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)


def cache_key(
    title: str,
    artist: Optional[str],
    item_type: str = 'track'
) -> str:
    """Generate cache key for a song"""
    if artist:
        key = f"{normalize_string(title)}||{normalize_string(artist)}"
    else:
        key = normalize_string(title)
    return key if item_type == 'track' else f"{item_type}||{key}"


def format_track(track: Dict[str, Any]) -> str:
    """Format track for display"""
    name = track['name']
    item_type = track.get('type', 'unknown')
    artists = ', '.join(a['name'] for a in track.get('artists', []))
    if not artists:
        artists = track.get('show', {}).get('name', '')
    popularity = track.get('popularity', 0)
    display_name = format_terminal_text(name)
    display_artists = format_terminal_text(artists)
    return f"[{item_type}] {display_name} — {display_artists} [popularity: {popularity}]"


def interactive_select(
    title: str,
    artist: Optional[str],
    alternatives: List[Tuple[Dict[str, Any], float]]
) -> Optional[List[str]]:
    """Interactively select one or more ambiguous matches

    Returns:
        Track URIs or None to skip
    """
    console.print(f"\n[yellow]? Could not confidently match:[/yellow]")
    console.print(f"  Input: {title}" + (f" - {artist}" if artist else ""))
    console.print()

    for index, (track, _) in enumerate(alternatives, 1):
        console.print(f"  {index}. {format_track(track)}")
    console.print("  S. ⊘ Skip")

    selected_indices = ()
    while True:
        try:
            console.print("\nPress numbers to toggle, Enter to confirm, or S to skip: ", end="")
            choice = readchar.readkey()
            console.print(choice)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

        if choice == readchar.key.CTRL_C:
            console.print("\n[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

        if choice in (readchar.key.ENTER, '\n', '\r'):
            if not selected_indices:
                console.print("[red]Select at least one number or press S.[/red]")
                continue

            selected_tracks = [alternatives[index][0] for index in selected_indices]
            for track in selected_tracks:
                console.print(f"[green]✓ Selected: {format_track(track)}[/green]")
            return [track['uri'] for track in selected_tracks]

        selected_index = parse_selection(choice, len(alternatives))
        if selected_index is None:
            console.print("[yellow]⊘ Skipped[/yellow]")
            return None

        if selected_index >= 0:
            if selected_index in selected_indices:
                selected_indices = tuple(
                    index for index in selected_indices if index != selected_index
                )
            else:
                selected_indices = (*selected_indices, selected_index)
            selected_numbers = ", ".join(str(index + 1) for index in selected_indices)
            console.print(f"[cyan]Selected: {selected_numbers or 'none'}[/cyan]")
            continue

        console.print("[red]Invalid choice. Press a listed number or S.[/red]")


@app.command()
def auth():
    """Authenticate with Spotify"""
    client_id, client_secret = get_credentials()
    client = SpotifyClient(client_id, client_secret)

    console.print("Starting Spotify authentication...\n")
    try:
        client.authenticate()
        console.print("[green]✓ Authentication complete![/green]")
    except Exception as e:
        console.print(f"[red]Authentication failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def version():
    """Show version information"""
    from . import __version__
    console.print(f"playlist-maker version {__version__}")


@app.command()
def clear_auth():
    """Clear saved authentication tokens"""
    from .spotify import TOKEN_FILE, CACHE_FILE

    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        console.print("[green]✓ Cleared authentication tokens[/green]")
    else:
        console.print("[yellow]No tokens found[/yellow]")

    if CACHE_FILE.exists():
        console.print("\nCache file still exists. To clear it:")
        console.print(f"  rm {CACHE_FILE}")

    console.print("\nRun 'plm auth' to authenticate again")


@app.command()
def reload_auth():
    """Clear and re-authenticate (shortcut for clear-auth + auth)"""
    from .spotify import TOKEN_FILE

    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        console.print("[green]✓ Cleared authentication tokens[/green]\n")

    client_id, client_secret = get_credentials()
    client = SpotifyClient(client_id, client_secret)
    client.authenticate()


@app.command()
def whoami():
    """Show currently authenticated Spotify user"""
    client_id, client_secret = get_credentials()
    client = SpotifyClient(client_id, client_secret)

    if not client.access_token:
        console.print("[red]Not authenticated[/red]")
        console.print("Run 'plm auth' first")
        raise typer.Exit(1)

    try:
        response = client._make_request('GET', '/me')
        if response.status_code == 200:
            user = response.json()
            console.print(f"\n[green]✓ Authenticated as:[/green]")
            console.print(f"  Display Name: {user.get('display_name', 'N/A')}")
            console.print(f"  Email: {user.get('email', 'N/A')}")
            console.print(f"  User ID: {user.get('id')}")
            console.print(f"  Country: {user.get('country', 'N/A')}")
            console.print(f"  Product: {user.get('product', 'free')}")
        else:
            console.print(f"[red]Failed to get user info: {response.text}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def check_playlist(
    playlist_id: str = typer.Argument(..., help="Spotify playlist ID or URL")
):
    """Check playlist ownership and permissions"""
    client_id, client_secret = get_credentials()
    client = SpotifyClient(client_id, client_secret)

    if not client.access_token:
        console.print("[red]Not authenticated. Run 'plm auth' first.[/red]")
        raise typer.Exit(1)

    if 'spotify.com/playlist/' in playlist_id:
        playlist_id = playlist_id.split('/')[-1].split('?')[0]

    try:
        user_response = client._make_request('GET', '/me')
        user = user_response.json()
        user_id = user.get('id')

        console.print(f"\n[cyan]Your User ID:[/cyan] {user_id}")
        console.print(f"[cyan]Your Email:[/cyan] {user.get('email')}\n")

        playlist_info = client.get_playlist_info(playlist_id)

        console.print(f"[cyan]Playlist Name:[/cyan] {playlist_info['name']}")
        console.print(f"[cyan]Playlist Owner:[/cyan] {playlist_info['owner']['id']}")
        console.print(f"[cyan]Total Tracks:[/cyan] {playlist_info.get('items', {}).get('total', 0)}")
        console.print(f"[cyan]Public:[/cyan] {playlist_info.get('public', 'N/A')}")
        console.print(f"[cyan]Collaborative:[/cyan] {playlist_info.get('collaborative', False)}\n")

        if playlist_info['owner']['id'] != user_id:
            console.print("[red]⚠️  You don't own this playlist![/red]")
            console.print("[yellow]You can only modify playlists you created.[/yellow]")
        else:
            console.print("[green]✓ You own this playlist[/green]")

        console.print(f"\nTrying to read tracks...")
        try:
            tracks = client.get_playlist_tracks(playlist_id)
            console.print(f"[green]✓ Successfully read {len(tracks)} tracks[/green]")
        except Exception as e:
            console.print(f"[red]✗ Failed to read tracks: {e}[/red]")

        console.print(f"\nTrying to add a test track...")
        try:
            test_results = client.search_track("test", limit=1)
            if test_results:
                test_uri = test_results[0]['uri']
                response = client._make_request('POST', f'/playlists/{playlist_id}/items',
                                              json={'uris': [test_uri]})
                if response.status_code in [200, 201]:
                    console.print(f"[green]✓ Successfully added test track[/green]")
                    console.print("[yellow]Removing test track...[/yellow]")
                    client._make_request('DELETE', f'/playlists/{playlist_id}/items',
                                       json={'items': [{'uri': test_uri}]})
                else:
                    console.print(f"[red]✗ Failed to add track: {response.status_code} - {response.text}[/red]")
        except Exception as e:
            console.print(f"[red]✗ Failed to add track: {e}[/red]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def add_to_playlist(
    playlist_url: str = typer.Argument(..., help="Spotify playlist URL or ID"),
    file_path: str = typer.Argument(..., help="Path to list file (songs or podcasts)"),
    batch_size: int = typer.Option(10, "--batch-size", "-b", help="Number of tracks to add at once (max 10 for Dev Mode)"),
    delay: float = typer.Option(2.0, "--delay", "-d", help="Delay in seconds between batches (helps avoid rate limits)")
):
    """Add songs from a file to an existing Spotify playlist"""

    # Extract playlist ID from URL or use directly
    playlist_id = playlist_url
    if 'spotify.com/playlist/' in playlist_url:
        playlist_id = playlist_url.split('playlist/')[-1].split('?')[0]

    console.print(f"Playlist ID: {playlist_id}\n")

    # Get credentials and create client
    client_id, client_secret = get_credentials()
    client = SpotifyClient(client_id, client_secret)

    # Check authentication
    if not client.access_token:
        console.print("[yellow]Not authenticated. Starting authentication...[/yellow]\n")
        try:
            client.authenticate()
        except Exception as e:
            console.print(f"[red]Authentication failed: {e}[/red]")
            raise typer.Exit(1)

    # Get playlist info to check current track count
    try:
        playlist_info = client.get_playlist_info(playlist_id)
        current_track_count = playlist_info['items']['total']
        playlist_name = playlist_info['name']
        console.print(f"[cyan]Playlist:[/cyan] {playlist_name}")
        console.print(f"[cyan]Current tracks:[/cyan] {current_track_count}\n")

        if current_track_count >= 10:
            console.print(f"[yellow]⚠ Warning: Playlist already has {current_track_count} tracks[/yellow]")
            console.print(f"[yellow]Development Mode typically limits playlists to ~10-25 tracks total[/yellow]")
            console.print(f"[yellow]You may not be able to add more tracks[/yellow]\n")

    except Exception as e:
        console.print(f"[yellow]Could not get playlist info: {e}[/yellow]\n")

    # Load cache
    cache = load_cache()

    # Read songs
    console.print(f"Reading {file_path}...\n")
    try:
        songs = read_song_file(file_path)
    except Exception as e:
        console.print(f"[red]Failed to read file: {e}[/red]")
        raise typer.Exit(1)

    if not songs:
        console.print("[red]No songs found in file[/red]")
        raise typer.Exit(1)

    # Process songs (same as create command)
    matched_tracks: List[Tuple[str, str, str]] = []
    auto_matched = 0
    interactive_matched = 0
    skipped = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        for title, artist, original_line in songs:
            key = cache_key(title, artist)
            if key in cache:
                cached_value = cache[key]
                if cached_value:
                    cached_uris = cached_value if isinstance(cached_value, list) else [cached_value]
                    matched_tracks.extend(
                        (uri, title, artist or "") for uri in cached_uris
                    )
                    console.print(f"[green]✓[/green] [dim](cached)[/dim] {title}" + (f" — {artist}" if artist else ""))
                    auto_matched += 1
                else:
                    console.print(f"[yellow]⊘[/yellow] [dim](cached skip)[/dim] {title}" + (f" — {artist}" if artist else ""))
                    skipped += 1
                continue

            task = progress.add_task(f"Searching: {title[:40]}...", total=None)

            try:
                query = f"{title} {artist}" if artist else title
                results = client.search_track(query, limit=10)

                best_track, confidence, alternatives = find_best_match(results, title, artist)

                progress.remove_task(task)

                if best_track and confidence >= 0.75:
                    track_uri = best_track['uri']
                    matched_tracks.append((track_uri, title, artist or ""))
                    console.print(f"[green]✓[/green] {format_track(best_track)}")
                    cache[key] = track_uri
                    auto_matched += 1
                elif alternatives:
                    track_uris = interactive_select(title, artist, alternatives)
                    if track_uris:
                        matched_tracks.extend(
                            (uri, title, artist or "") for uri in track_uris
                        )
                        cache[key] = track_uris
                        interactive_matched += 1
                    else:
                        cache[key] = None
                        skipped += 1
                else:
                    console.print(f"[red]✗ No results for: {title}[/red]" + (f" - {artist}" if artist else ""))
                    cache[key] = None
                    skipped += 1
            except Exception as e:
                progress.remove_task(task)
                console.print(f"[red]✗ Error searching {title}: {e}[/red]")
                skipped += 1

    save_cache(cache)

    # Summary
    console.print()
    console.print(f"[bold]{len(songs)} songs processed[/bold]")
    console.print(f"  {auto_matched} matched automatically")
    if interactive_matched > 0:
        console.print(f"  {interactive_matched} matched interactively")
    if skipped > 0:
        console.print(f"  {skipped} skipped")
    console.print()

    if not matched_tracks:
        console.print("[yellow]No tracks to add to playlist[/yellow]")
        raise typer.Exit(0)

    # Add tracks in batches
    try:
        track_uris = [uri for uri, _, _ in matched_tracks]
        total_tracks = len(track_uris)

        console.print(f"Adding {total_tracks} tracks in batches of {batch_size}...")

        added = 0
        for i in range(0, total_tracks, batch_size):
            batch = track_uris[i:i+batch_size]
            try:
                client.add_tracks_to_playlist(playlist_id, batch, batch_size=len(batch))
                added += len(batch)
                console.print(f"[green]✓[/green] Added tracks {i+1}-{min(i+len(batch), total_tracks)} of {total_tracks}")

                # Wait between batches (except for the last batch)
                if i + batch_size < total_tracks and delay > 0:
                    console.print(f"[dim]  Waiting {delay:.1f}s before next batch...[/dim]")
                    time.sleep(delay)

            except Exception as e:
                error_msg = str(e)
                console.print(f"\n[yellow]⚠ Stopped at track {added+1}[/yellow]")
                console.print(f"[yellow]Error: {error_msg[:200]}[/yellow]")

                if added > 0:
                    console.print(f"\n[cyan]✓ Successfully added {added} out of {total_tracks} tracks[/cyan]")
                else:
                    console.print(f"\n[red]✗ Could not add any tracks[/red]")

                if "403 Forbidden" in error_msg:
                    console.print(f"\n[yellow]Development Mode Restriction:[/yellow]")

                    # Check current track count
                    try:
                        current_info = client.get_playlist_info(playlist_id)
                        final_count = current_info['items']['total']
                        console.print(f"  - Playlist now has {final_count} tracks total")
                        console.print(f"  - This may be the Development Mode limit for this playlist")
                    except:
                        pass

                    console.print(f"\n[cyan]Solutions:[/cyan]")
                    console.print(f"  1. Create a NEW playlist for remaining tracks")
                    console.print(f"  2. Request Extended Quota Mode from Spotify Dashboard")
                    console.print(f"  3. Try smaller batch size: --batch-size 1")
                    console.print(f"  4. Try longer delay: --delay 2")

                raise typer.Exit(1)

        console.print()
        console.print(f"[green]✓ Successfully added all {added} tracks![/green]")
        console.print(f"\nhttps://open.spotify.com/playlist/{playlist_id}")

    except Exception as e:
        if "Successfully added" not in str(e):
            console.print(f"\n[red]Failed to add tracks: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def create(
    file_path: Optional[str] = typer.Argument(None, help="Optional path to a song or podcast list"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Playlist name"),
    content_type: str = typer.Option("song", "--type", help="Content type: song or podcast"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show matches without creating playlist"),
    batch_size: int = typer.Option(5, "--batch-size", "-b", help="Number of tracks to add per batch"),
    delay: float = typer.Option(2.0, "--delay", "-d", help="Delay in seconds between batches")
):
    """Create a Spotify playlist from a file or pasted text"""

    content_type = content_type.lower()
    if content_type not in ('song', 'podcast'):
        console.print("[red]Type must be 'song' or 'podcast'.[/red]")
        raise typer.Exit(1)
    search_type = 'episode' if content_type == 'podcast' else 'track'

    if file_path and not Path(file_path).exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        raise typer.Exit(1)

    try:
        if file_path:
            console.print(f"Reading {file_path}...\n")
            songs = read_song_file(file_path)
            source_name = Path(file_path).name
        else:
            console.print("Paste your list below, then press Ctrl-D when finished:\n")
            songs = read_song_text(sys.stdin.read())
            source_name = "pasted text"
    except Exception as e:
        console.print(f"[red]Failed to read input: {e}[/red]")
        raise typer.Exit(1)

    if not songs:
        console.print("[red]No items found in input[/red]")
        raise typer.Exit(1)

    # Get credentials and create client
    client_id, client_secret = get_credentials()
    client = SpotifyClient(client_id, client_secret)

    # Check authentication
    if not client.access_token:
        console.print("[yellow]Not authenticated. Starting authentication...[/yellow]\n")
        try:
            client.authenticate()
        except Exception as e:
            console.print(f"[red]Authentication failed: {e}[/red]")
            raise typer.Exit(1)

    # Load cache
    cache = load_cache()

    # Process songs
    matched_tracks: List[Tuple[str, str, str]] = []  # (uri, title, artist)
    auto_matched = 0
    interactive_matched = 0
    skipped = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        for title, artist, original_line in songs:
            # Check cache
            key = cache_key(title, artist, search_type)
            if key in cache:
                cached_value = cache[key]
                if cached_value:
                    cached_uris = cached_value if isinstance(cached_value, list) else [cached_value]
                    matched_tracks.extend(
                        (uri, title, artist or "") for uri in cached_uris
                    )
                    console.print(f"[green]✓[/green] [dim](cached)[/dim] {title}" + (f" — {artist}" if artist else ""))
                    auto_matched += 1
                else:
                    console.print(f"[yellow]⊘[/yellow] [dim](cached skip)[/dim] {title}" + (f" — {artist}" if artist else ""))
                    skipped += 1
                continue

            # Search Spotify
            task = progress.add_task(f"Searching: {title[:40]}...", total=None)

            try:
                query = f"{title} {artist}" if artist else title
                results = client.search_track(query, limit=10, item_type=search_type)

                best_track, confidence, alternatives = find_best_match(results, title, artist)

                progress.remove_task(task)

                if best_track and confidence >= 0.75:
                    # High confidence match
                    track_uri = best_track['uri']
                    matched_tracks.append((track_uri, title, artist or ""))
                    console.print(f"[green]✓[/green] {format_track(best_track)}")
                    cache[key] = track_uri
                    auto_matched += 1

                elif alternatives:
                    # Ambiguous - ask user
                    track_uris = interactive_select(title, artist, alternatives)
                    if track_uris:
                        matched_tracks.extend(
                            (uri, title, artist or "") for uri in track_uris
                        )
                        cache[key] = track_uris
                        interactive_matched += 1
                    else:
                        console.print(f"[yellow]⊘ Skipped[/yellow]")
                        cache[key] = None
                        skipped += 1

                else:
                    # No results
                    console.print(f"[red]✗ No results for: {title}[/red]" + (f" - {artist}" if artist else ""))
                    cache[key] = None
                    skipped += 1

            except Exception as e:
                progress.remove_task(task)
                console.print(f"[red]✗ Error searching {title}: {e}[/red]")
                skipped += 1

    # Save cache
    save_cache(cache)

    # Summary
    console.print()
    console.print(f"[bold]{len(songs)} songs processed[/bold]")
    console.print(f"  {auto_matched} matched automatically")
    if interactive_matched > 0:
        console.print(f"  {interactive_matched} matched interactively")
    if skipped > 0:
        console.print(f"  {skipped} skipped")
    console.print()

    if not matched_tracks:
        console.print("[yellow]No tracks to add to playlist[/yellow]")
        raise typer.Exit(0)

    if dry_run:
        console.print("[cyan]Dry run - playlist not created[/cyan]")
        raise typer.Exit(0)

    # Determine playlist name
    if not name:
        name = Path(file_path).stem if file_path else "playlist-maker"

    # Check if playlist already exists
    console.print(f"\nChecking for existing playlist '{name}'...")
    existing_playlist = None
    try:
        existing_playlist = client.find_playlist_by_name(name)
    except Exception as e:
        console.print(f"[yellow]Could not check for existing playlists: {e}[/yellow]")

    playlist = None
    existing_track_uris = []

    if existing_playlist:
        console.print(f"[cyan]Found existing playlist:[/cyan] {existing_playlist['name']}")

        # Get full playlist info to get track count
        try:
            full_playlist_info = client.get_playlist_info(existing_playlist['id'])
            track_count = full_playlist_info.get('items', {}).get('total', 0)
            console.print(f"[cyan]Current tracks:[/cyan] {track_count}")
        except Exception as e:
            console.print(f"[cyan]Current tracks:[/cyan] Unknown")

        console.print(f"[cyan]URL:[/cyan] {existing_playlist['external_urls']['spotify']}\n")

        # Get existing tracks to avoid duplicates
        try:
            existing_track_uris = client.get_playlist_tracks(existing_playlist['id'])
            console.print(f"[dim]Loaded {len(existing_track_uris)} existing tracks[/dim]\n")
        except Exception as e:
            console.print(f"[yellow]Could not load existing tracks: {e}[/yellow]\n")

        choice = Prompt.ask(
            "What would you like to do?",
            choices=["update", "create", "cancel"],
            default="update"
        )

        if choice == "cancel":
            console.print("Cancelled")
            raise typer.Exit(0)
        elif choice == "update":
            playlist = existing_playlist
            console.print(f"\n[green]Updating existing playlist...[/green]")
        else:
            # Create new with different name
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"{name}_{timestamp}"
            console.print(f"\n[green]Creating new playlist: {name}[/green]")
    else:
        # Confirm creation
        if not Confirm.ask(f'Create playlist "{name}"?', default=True):
            console.print("Cancelled")
            raise typer.Exit(0)

    # Create playlist if needed
    try:
        if playlist is None:
            console.print(f"\nCreating playlist...")
            playlist = client.create_playlist(
                name,
                description=f"Created by playlist-maker from {source_name}"
            )

        track_uris = [uri for uri, _, _ in matched_tracks]

        # Filter out tracks that already exist in the playlist
        if existing_track_uris:
            new_track_uris = [uri for uri in track_uris if uri not in existing_track_uris]
            skipped_count = len(track_uris) - len(new_track_uris)

            if skipped_count > 0:
                console.print(f"[yellow]Skipping {skipped_count} tracks already in playlist[/yellow]")

            track_uris = new_track_uris

            if not track_uris:
                console.print(f"\n[green]All tracks already in playlist! Nothing to add.[/green]")
                console.print(f"\n{playlist['external_urls']['spotify']}")
                raise typer.Exit(0)

        console.print(f"Adding {len(track_uris)} tracks in batches of {batch_size}...")

        # Add tracks in batches with delays
        added = 0

        for i in range(0, len(track_uris), batch_size):
            batch = track_uris[i:i+batch_size]
            try:
                client.add_tracks_to_playlist(playlist['id'], batch, batch_size=len(batch))
                added += len(batch)
                console.print(f"[green]✓[/green] Added tracks {i+1}-{min(i+len(batch), len(track_uris))} of {len(track_uris)}")

                # Wait between batches
                if i + batch_size < len(track_uris):
                    console.print(f"[dim]  Waiting {delay:.1f}s...[/dim]")
                    time.sleep(delay)

            except Exception as e:
                error_msg = str(e)
                console.print(f"\n[yellow]⚠ Stopped at track {added+1}[/yellow]")
                console.print(f"[yellow]Error: {error_msg[:200]}[/yellow]")

                if added > 0:
                    console.print(f"\n[cyan]✓ Successfully added {added} out of {len(track_uris)} tracks[/cyan]")
                    console.print(f"\n[cyan]Playlist created but not all tracks added:[/cyan]")
                    console.print(f"  {playlist['external_urls']['spotify']}")
                    if file_path:
                        console.print(f"\n[yellow]To add remaining tracks, use:[/yellow]")
                        console.print(f"  plm add-to-playlist {playlist['id']} {file_path} --batch-size 1")
                else:
                    console.print(f"\n[red]✗ Could not add any tracks[/red]")

                if "403 Forbidden" in error_msg:
                    console.print(f"\n[yellow]Development Mode Restriction:[/yellow]")
                    console.print(f"  - Playlists may be limited to ~10-25 tracks total")
                    console.print(f"  - Request Extended Quota Mode from Spotify Dashboard")

                raise typer.Exit(1)

        console.print()
        console.print("[green]✓ Playlist created successfully![/green]")
        console.print()
        console.print(f"[bold]{playlist['name']}[/bold]")
        console.print(playlist['external_urls']['spotify'])

    except Exception as e:
        if "Stopped at track" not in str(e):
            console.print(f"\n[red]Failed to create playlist: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

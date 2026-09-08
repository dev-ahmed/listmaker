# listmaker

Convert plain-text lists into music playlists with one command.

## What it does

- Reads a plain-text file with songs or podcasts
- Searches music platforms (Spotify, Anghami support planned)
- Intelligently matches tracks (prefers originals over remixes/live/karaoke)
- Creates a playlist
- Adds all matched items

**Current support:** Spotify (songs and podcasts)
**Future support:** Anghami

## Requirements

- Python 3.8+
- Spotify account
- Spotify Developer App credentials

## Spotify Developer Setup

1. Go to https://developer.spotify.com/dashboard
2. Log in with your Spotify account
3. Click "Create app"
4. Fill in:
   - App name: `listmaker` (or anything)
   - App description: `Personal CLI tool for creating playlists`
   - Redirect URI: `http://127.0.0.1:8888/callback`
   - Check **Web API**
5. Click "Save"
6. Click "Settings" and copy your **Client ID** and **Client Secret**
7. **IMPORTANT:** Click "Users and Access" on the left sidebar
8. Click "Add New User"
9. Enter the email address associated with your Spotify account
10. Click "Add"

**Note:** Apps in Development Mode can only be used by users you explicitly add. If you get a 403 Forbidden error, make sure you added your Spotify email in step 7-10.

## Installation

```bash
cd listmaker
pip install -e .
```

Or with pipx for isolated installation:

```bash
pipx install .
```

## Configuration

Set environment variables with your Spotify credentials:

```bash
export SPOTIFY_CLIENT_ID="your_client_id_here"
export SPOTIFY_CLIENT_SECRET="your_client_secret_here"
```

Add these to your `~/.zshrc` or `~/.bashrc` to persist them.

## Authentication

First time usage:

```bash
listmaker auth
```

This will:
1. Open your browser
2. Ask you to authorize the app
3. Save credentials locally in `~/.config/listmaker/`

You only need to do this once. Tokens are automatically refreshed.

## Usage

Create a text file with songs or podcasts (one per line):

**songs.txt**
```
Bleeding Love - Leona Lewis
Shape of You - Ed Sheeran
Rolling in the Deep - Adele
Because of You - Kelly Clarkson
Just Give Me a Reason - P!nk
Stay - Rihanna
```

Format: `Title - Artist/Creator Name`

You can also use just the title:
```
Bleeding Love
```

Empty lines and lines starting with `#` are ignored.

**For podcasts:** Use the same format
```
The Joe Rogan Experience - Joe Rogan
Serial - Sarah Koenig
```

### Create playlist

```bash
listmaker create songs.txt
```

With custom name:

```bash
listmaker create songs.txt --name "My Favorites"
```

Dry run (search without creating playlist):

```bash
listmaker create songs.txt --dry-run
```

## How it works

1. **Automatic matching**: High-confidence matches are auto-accepted
2. **Interactive selection**: Ambiguous matches show you options
3. **Caching**: Resolved songs are cached to speed up repeated use
4. **Smart scoring**: Prefers exact title/artist matches and higher popularity

## Example Output

```
Reading songs.txt...

✓ Bleeding Love — Leona Lewis [popularity: 72]
✓ Shape of You — Ed Sheeran [popularity: 94]
✓ Rolling in the Deep — Adele [popularity: 88]

? Could not confidently match:
  Input: Unknown Song - Unknown Artist

  1. Unknown Song — Artist A [popularity: 65]
  2. Unknown Song — Artist B [popularity: 42]

  Choose [1-2, s=skip, q=quit]: 1

6 songs processed
  5 matched automatically
  1 matched interactively

Create playlist "songs"? [Y/n]: y

✓ Playlist created successfully!

songs
https://open.spotify.com/playlist/...
```

## Cache

Matched items are cached in `~/.config/listmaker/cache.json`. This means:
- Faster repeated searches
- Consistent results for the same items

Clear cache:

```bash
rm ~/.config/listmaker/cache.json
```

## Troubleshooting

**"Spotify credentials are not configured"**
- Set `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` environment variables

**"Not authenticated"**
- Run `listmaker auth`

**"Failed to create playlist: 403 Forbidden"**
- Your Spotify app is in Development Mode
- Go to https://developer.spotify.com/dashboard
- Click on your app → "Users and Access"
- Add your Spotify email address as a user
- Run `listmaker auth` again to re-authenticate

**"Failed to create playlist"**
- Check your Spotify app has the redirect URI `http://127.0.0.1:8888/callback`
- Make sure you're authenticated: `listmaker auth`

**Poor matches**
- Use the format: `Title - Artist/Creator Name` for better accuracy
- Interactive mode lets you select correct match when confidence is low

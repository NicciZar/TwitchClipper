# TwitchClipper

A Python-based Twitch clip downloader with hotkey support, featuring a system tray interface and comprehensive clip library management.

## Features

- **Hotkey-triggered Clipping**: Create and download clips with a single hotkey press
- **System Tray Integration**: Minimize to tray for unobtrusive operation
- **Clip Library Management**: Browse, organize, and manage your downloaded clips
- **Automatic Organization**: Clips are sorted by broadcaster and game
- **Twitch API Integration**: Fetch game names and clip metadata from Twitch Helix API
- **Multi-language Support**: English and German translations included
- **Session Logging**: Detailed logs of all actions and API interactions
- **Build Metadata in UI**: Version, build date, and repository link in a dedicated About tab
- **Release Automation**: Semantic versioning, EXE metadata stamping, and GitHub Release upload

## Prerequisites

- Python 3.x
- Twitch API credentials (Client ID and Access Token)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/TwitchClipper.git
   cd TwitchClipper
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure your settings:
  - Via the UI (recommended)
  - Or manually edit `config.json` with your Twitch API credentials and preferred broadcaster name (not recommended)

## Usage

### Starting the Application from Source Code via Python

```bash
python -m main
```

The application will launch with a system tray icon. Click the icon to open the main settings window.

### Hotkey Commands

- **Primary Hotkey**: Creates a clip on Twitch for the configured duration (default: 30s) and, by default, automatically downloads it (default: **ctrl+shift+c**)

### Settings Window

The settings window provides:
- **Auth Tab**: Authenticate with Twitch using your Client ID and Client Secret
- **Clip Tab**: Configure clip-related settings such as broadcaster, hotkey, clip title template, and download options
- **Notifications Tab**: Configure notification settings such as UI language, display, and position
- **Clip Library Tab**: View and manage your downloaded clips
  - Delete clips and remove them from disk
  - Filter clips by status
- **Twitch Clips Tab**: Browse clips from your configured broadcaster channel
  - Download clips directly
  - Set custom broadcaster/game organization
- **Session Log Tab**: View real-time logs of all operations
- **Import / Export Tab**: Import / Export user configuration
- **About Tab**: View app metadata such as version, build date (local timezone), repository URL, issue tracker URL, commit hash, build type, and Python runtime

## Build From Source

```bash
build.bat
```

This creates `dist/TwitchClipper.exe` for local testing without creating tags or publishing a GitHub release.

## Release Process

Automated release flow is available via:

```bash
release.bat
```

What it does:
- Computes next semantic version from commits since last `vX.Y.Z` tag
- Uses standard bump rules:
  - `major`: commit contains `BREAKING CHANGE` or `type!:`
  - `minor`: at least one `feat` commit
  - `patch`: all other commits
- Generates a release notes summary (bump type + included commits) and publishes it with the GitHub release
- Generates build metadata (`app_version.py`) and PyInstaller version resource
- Builds `dist/TwitchClipper.exe`
- Creates and pushes a git tag
- Creates a GitHub Release and uploads the EXE

Requirements:
- GitHub CLI (`gh`) installed and authenticated
- Clean working tree before running `release.bat`
- At least one commit since the latest release tag

## Runtime Data Paths

Source/dev runs (`python -m main`) continue to use workspace-local files.

Frozen release EXE runs use user-profile locations:

- Config: `%APPDATA%\\TwitchClipper\\config.json`
- Logs: `%LOCALAPPDATA%\\TwitchClipper\\logs\\`
- Default clips folder: `%USERPROFILE%\\Videos\\TwitchClipper`
  - Fallback when Videos folder is unavailable: `%LOCALAPPDATA%\\TwitchClipper\\clips`

On first frozen run, the app performs a one-time migration from legacy EXE-adjacent paths when applicable.

## Manual Configuration (not recommended)

Edit `config.json` manually to configure:

```json
{
  "broadcaster_name": "your_channel_name",
  "client_id": "your_twitch_client_id",
  "access_token": "your_twitch_access_token",
  "download_folder": "./clips",
  "hotkey": "ctrl+shift+c",
  "language": "auto"
}
```

## Project Structure

```
TwitchClipper/
├── main.py                 # Application entry point
├── tray.py                 # System tray interface
├── settings_window.py      # Main GUI settings window
├── twitch_api.py           # Twitch API interactions
├── hotkey_listener.py      # Hotkey detection and clip handling
├── app_logs.py             # Logging and clip library persistence
├── auth.py                 # Twitch authentication
├── config.py               # Configuration management
├── i18n.py                 # Internationalization (EN, DE)
├── popup_notify.py         # Toast notifications
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues, questions, or suggestions, please open an issue on the GitHub repository.

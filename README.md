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

## Prerequisites

- Python 3.x
- Twitch API credentials (Client ID and Access Token)
- FFmpeg (for audio extraction if needed)

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
   - Edit `config.json` with your Twitch API credentials and preferred broadcaster name
   - Set your desired hotkey binding in the settings window

## Usage

### Starting the Application

```bash
python -m main
```

The application will launch with a system tray icon. Click the icon to open the main settings window.

### Hotkey Commands

- **Primary Hotkey**: Download the current clip from the active Twitch stream

### Settings Window

The settings window provides:
- **Library Tab**: View and manage your downloaded clips
  - Delete clips and remove them from disk
  - Filter clips by status
- **Twitch Clips Tab**: Browse clips from your followed channels
  - Download clips directly
  - Set custom broadcaster/game organization
- **Session Log Tab**: View real-time logs of all operations

## Configuration

Edit `config.json` to configure:

```json
{
  "broadcaster_name": "your_channel_name",
  "client_id": "your_twitch_client_id",
  "access_token": "your_twitch_access_token",
  "download_folder": "./clips",
  "hotkey": "ctrl+alt+c",
  "language": "en"
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

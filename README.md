# TwitchAutoVOD

![License](https://img.shields.io/badge/license-GPL%203.0-blue.svg)
![Version](https://img.shields.io/badge/version-1.0--alpha-orange.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)

> Download your Twitch VODs and chat when you finish streaming

TwitchAutoVOD monitors your Twitch channel and downloads your VODs with chat messages when you go offline. You won't lose content before it expires.

## Features

- Monitors your stream status via Twitch EventSub WebSocket
- Downloads VOD and chat when your stream ends
- Saves chat messages in JSON format for analysis or rendering
- Runs in the background without manual intervention
- Refreshes OAuth tokens to maintain connection

## Prerequisites

You need:

- Python 3.8 or higher
- A Twitch account
- A Twitch Developer Application (free to create)

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/TwitchAutoVOD.git
   cd TwitchAutoVOD
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create a Twitch Developer Application:
   - Enable two-factor authentication (2FA) on your Twitch account if you haven't already
   - Go to the [Twitch Developer Console](https://dev.twitch.tv/console)
   - Click "Register Your Application"
   - Set the OAuth Redirect URL to: `http://localhost:8080/callback`
   - Copy your Client ID and Client Secret

## Configuration

Set your Twitch application credentials as environment variables.

**Option 1: Use .env file (Recommended)**

Copy the `.env.example` file and rename it to `.env`:

```bash
cp .env.example .env
```

Then edit `.env` and add your credentials:

```
TWITCH_CLIENT_ID=your_client_id_here
TWITCH_CLIENT_SECRET=your_client_secret_here
```

**Option 2: Set environment variables manually**

Windows (PowerShell):

```powershell
$env:TWITCH_CLIENT_ID="your_client_id_here"
$env:TWITCH_CLIENT_SECRET="your_client_secret_here"
```

Linux/macOS:

```bash
export TWITCH_CLIENT_ID="your_client_id_here"
export TWITCH_CLIENT_SECRET="your_client_secret_here"
```

**Additional Configuration**

You can customize the app behavior by editing the YAML files in the `config/` directory:

- `config/logging.yaml` for logging settings
- `config/twitch.yaml` for Twitch-specific configuration

## Usage

1. Start the application:

   ```bash
   python twitch_auto_vodl.py
   ```

2. Authenticate:
   - The app opens your browser for OAuth authentication
   - Log in with your Twitch account and authorize the app
   - The local callback server captures the token

3. Run the app:
   - The app monitors your channel for stream events
   - When you go live, it detects the stream start
   - When you end your stream, it downloads the VOD and chat
   - Downloaded files save to the `vods/` directory

## How It Works

1. Uses OAuth 2.0 flow with a local callback server to obtain access tokens
2. Establishes a persistent Twitch EventSub WebSocket connection
3. Listens for `stream.online` and `stream.offline` events
4. Triggers download queue when stream goes offline
5. Uses TwitchDownloaderCLI to download video and chat data
6. Refreshes OAuth tokens to maintain connection

## Project Structure

```
TwitchAutoVOD/
├── twitch_auto_vodl.py          Main entry point
├── twitch_auth.py               OAuth authentication handler
├── twitch_callback.py           OAuth callback server
├── twitch_websocket.py          EventSub WebSocket client
├── twitch_vod_download.py       VOD download manager
├── config/                      Configuration files
│   ├── logging.yaml
│   └── twitch.yaml
├── utils/                       Utility modules
│   ├── auth_state_manager.py
│   ├── config_manager.py
│   ├── download_queue_manager.py
│   └── token_refresh_monitor.py
├── state/                       Authentication and stream state
├── vods/                        Downloaded VODs and chat
└── twitch_downloader_cli/       TwitchDownloaderCLI dependency
```

## Roadmap

Planned features:

- Eliminate need for personal Twitch app credentials
- Add Docker support with external and network drive mounting
- Build GUI desktop version with background task support
- Monitor and download VODs from multiple channels at once
- Add OBS macro script to work without WebSocket connection
- Improve credential handling and security
- Better error handling and performance
- Build custom VOD, chat download, and rendering pipeline

## Current Status

Alpha v1.0. The app works but may have occasional issues. I use it for personal projects and continue to develop it.

Report any bugs or issues you find.

## Contributing

Contributions are welcome. This project started for personal use and learning.

To contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

I appreciate bug fixes, features, documentation improvements, and suggestions.

## License

This project uses the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.

You can use, modify, and distribute this software. Any derivative works must also be open source under the same license.

## Acknowledgments

- [TwitchDownloaderCLI](https://github.com/lay295/TwitchDownloader) provides the VOD and chat download functionality
- Twitch EventSub provides the WebSocket API for real-time monitoring
- The Twitch developer community

## Support

If you have issues or questions:

- Check existing [Issues](https://github.com/yourusername/TwitchAutoVOD/issues)
- Open a new issue with details about your problem
- Make sure you use the latest version of the code

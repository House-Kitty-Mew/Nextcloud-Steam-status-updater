# Steam to Nextcloud Status Sync

A lightweight Python script that automatically updates your Nextcloud user status based on the game you're currently playing on Steam. It features dynamic polling intervals and desktop notifications for status changes.

## Features

- Real-time sync - Detects when you start or stop playing a game on Steam and updates your Nextcloud status accordingly.
- Dynamic polling - Checks more frequently while gaming (every 5 seconds) to quickly detect when you stop playing, then gradually backs off to once per minute when idle to save resources.
- Status verification - Before updating Nextcloud, it reads the current status and only makes an API call if a change is actually needed. This also corrects any manual changes or stale states.
- Desktop notifications - Shows a pop-up when your status changes (requires notify-send, which is typically available on SteamOS).
- Robust error handling - Continues running even if the Steam or Nextcloud API fails temporarily; logs errors to the console.

## Requirements

- Python 3.6 or higher
- requests library
- A Steam API key
- A Nextcloud instance with the User Status app enabled
- (Optional) libnotify for desktop notifications (already present on most SteamOS installations)

## Installation

1. Clone this repository or download the script.
2. Install the required Python package:
   pip install requests
3. Make the script executable (optional):
   chmod +x steam_nextcloud_status.py

## Configuration

Edit the script and set the following variables at the top:

- STEAM_API_KEY - Your Steam API key (get it from https://steamcommunity.com/dev/apikey).
- STEAM_ID - Your 64-bit Steam ID (use a site like https://steamid.io to find it).
- NEXTCLOUD_URL - The base URL of your Nextcloud instance (e.g., https://cloud.example.com).
- NEXTCLOUD_USER - Your Nextcloud username.
- NEXTCLOUD_APP_PASSWORD - An app password generated in your Nextcloud security settings.

You can also adjust the polling intervals:

- IN_GAME_INTERVAL - Seconds between checks while playing a game (default: 5).
- RECENT_INTERVAL - Seconds between checks for 5 minutes after a game ends (default: 15).
- IDLE_INTERVAL - Seconds between checks when no game has been played for a while (default: 60).
- RECENT_WINDOW - How many seconds to stay in "recently active" mode after a game ends (default: 300, i.e., 5 minutes).

## Usage

Run the script from a terminal:

python3 steam_nextcloud_status.py

It will continue running until you press Ctrl+C. For permanent background operation, consider using a systemd service or a terminal multiplexer like tmux.

## How It Works

1. The script polls the Steam Web API for your player summary every few seconds.
2. When the game you're playing changes (starts or stops), it checks your current Nextcloud status.
3. If the Nextcloud status differs from the desired state ("Playing <game>" with a (game) icon, or cleared), it sends an update request.
4. A desktop notification is displayed on status changes.
5. The polling interval adapts: while gaming it's very short (5s) to catch game exits quickly; after a game ends it stays at a medium interval (15s) for 5 minutes in case you start another game soon; then it drops to a long interval (60s) to be gentle on the API and your system.

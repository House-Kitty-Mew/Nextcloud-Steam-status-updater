#!/usr/bin/env python3
import time
import requests
from requests.auth import HTTPBasicAuth
import subprocess
import sys
from datetime import datetime

# --- CONFIGURATION ---
STEAM_API_KEY = ""
STEAM_ID = ""

NEXTCLOUD_URL = ""
NEXTCLOUD_USER = ""
NEXTCLOUD_APP_PASSWORD = ""

# Polling intervals (seconds)
IN_GAME_INTERVAL = 5
RECENT_INTERVAL = 15
IDLE_INTERVAL = 60

# Time window for "recently active" after a game ends (seconds)
RECENT_WINDOW = 300   # 5 minutes
# --------------------

def notify(title, message):
    """Send a desktop notification using notify-send (if available)."""
    try:
        subprocess.run(['notify-send', title, message], check=False)
    except FileNotFoundError:
        pass  # notify-send not installed, silently ignore
    except Exception as e:
        print(f"Notification error: {e}")

def get_current_steam_game():
    """Return the name of the game currently being played, or None."""
    url = "http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
    params = {
        "key": STEAM_API_KEY,
        "steamids": STEAM_ID
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        player = data["response"]["players"][0]
        return player.get("gameextrainfo")  # None if not in a game
    except Exception as e:
        print(f"Error fetching Steam data: {e}")
        return None  # Assume no change on error

def get_nextcloud_status():
    """Return current status message and icon from Nextcloud, or (None, None) if none."""
    url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/user_status/api/v1/user_status"
    headers = {"OCS-APIRequest": "true"}
    auth = HTTPBasicAuth(NEXTCLOUD_USER, NEXTCLOUD_APP_PASSWORD)
    try:
        resp = requests.get(url, headers=headers, auth=auth, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # OCS response structure: data contains message and icon
        ocs_data = data.get('ocs', {}).get('data', {})
        message = ocs_data.get('message')
        icon = ocs_data.get('icon')
        return message, icon
    except Exception as e:
        print(f"Error fetching Nextcloud status: {e}")
        return None, None  # Indicate failure

def set_nextcloud_status(game_name):
    """Set Nextcloud status to the game name, or clear it if game_name is None."""
    # Desired values
    if game_name:
        desired_message = f"Playing {game_name}"
        desired_icon = "🎮"
    else:
        desired_message = None
        desired_icon = None

    # Check current status to avoid unnecessary updates
    current_message, current_icon = get_nextcloud_status()
    # If fetch failed, we'll attempt to set anyway (current_message will be None)
    if current_message == desired_message and current_icon == desired_icon:
        print("Status already matches, skipping update.")
        return

    # Set or clear accordingly
    headers = {"OCS-APIRequest": "true"}
    auth = HTTPBasicAuth(NEXTCLOUD_USER, NEXTCLOUD_APP_PASSWORD)

    if game_name:
        # Set custom status
        url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/user_status/api/v1/user_status/message/custom"
        data = {
            "statusIcon": desired_icon,
            "message": desired_message
        }
        try:
            resp = requests.put(url, headers=headers, auth=auth, data=data, timeout=10)
            resp.raise_for_status()
            print(f"Status updated: {desired_message}")
            notify("Nextcloud Status", f"Now playing: {game_name}")
        except Exception as e:
            print(f"Failed to set status: {e}")
    else:
        # Clear status (DELETE endpoint)
        url_clear = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/user_status/api/v1/user_status/message"
        try:
            resp = requests.delete(url_clear, headers=headers, auth=auth, timeout=10)
            resp.raise_for_status()
            print("Status cleared.")
            notify("Nextcloud Status", "Stopped playing")
        except Exception as e:
            print(f"Failed to clear status: {e}")

def main():
    current_game = None          # last known game from Steam
    in_game = False              # are we currently in a game?
    last_game_end = time.time() - RECENT_WINDOW * 2  # start as idle

    while True:
        new_game = get_current_steam_game()
        now = time.time()

        # State transitions and status update
        if new_game != current_game:
            # Game changed
            if new_game is None:
                # Game ended
                if in_game:
                    last_game_end = now
                    in_game = False
                set_nextcloud_status(None)
            else:
                # Game started
                in_game = True
                set_nextcloud_status(new_game)
            current_game = new_game
        else:
            # No change, but we might still need to correct Nextcloud if it was
            # changed externally. Optionally, we could periodically verify,
            # but that would add many API calls. For now, we only update on change.

        # Determine next poll interval based on state
        if in_game:
            interval = IN_GAME_INTERVAL
        else:
            # Not in a game: check if we're still in the "recent" window
            if (now - last_game_end) < RECENT_WINDOW:
                interval = RECENT_INTERVAL
            else:
                interval = IDLE_INTERVAL

        time.sleep(interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nScript stopped by user.")
        sys.exit(0)

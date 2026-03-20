#!/usr/bin/env python3
import time
import requests
from requests.auth import HTTPBasicAuth
import subprocess
import sys

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

# Global variable to store the status that was present before a game started
PREVIOUS_STATUS = None
# --------------------

def notify(title, message):
    try:
        subprocess.run(['notify-send', title, message], check=False)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Notification error: {e}")

def get_current_steam_game():
    url = "http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
    params = {"key": STEAM_API_KEY, "steamids": STEAM_ID}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        player = data["response"]["players"][0]
        return player.get("gameextrainfo")
    except Exception as e:
        print(f"Error fetching Steam data: {e}")
        return None

def get_nextcloud_status():
    """
    Return current status message and icon from Nextcloud.
    Returns: (message, icon, success)
        success is True if the fetch succeeded, False otherwise.
    """
    url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/user_status/api/v1/user_status"
    headers = {
        "OCS-APIRequest": "true",
        "Accept": "application/json"
    }
    params = {"format": "json"}
    auth = HTTPBasicAuth(NEXTCLOUD_USER, NEXTCLOUD_APP_PASSWORD)

    try:
        resp = requests.get(url, headers=headers, params=params, auth=auth, timeout=10)
        content_type = resp.headers.get('Content-Type', '')
        if 'application/json' not in content_type:
            print(f"WARNING: Response is not JSON. Content-Type: {content_type}")
            print(f"Response preview: {resp.text[:200]}")
            return None, None, False

        resp.raise_for_status()
        data = resp.json()

        ocs_data = data.get('ocs', {})
        meta = ocs_data.get('meta', {})

        if meta.get('status') != 'ok':
            print(f"API returned error: {meta.get('message')}")
            return None, None, False

        status_data = ocs_data.get('data', {})
        message = status_data.get('message')
        icon = status_data.get('icon')

        return message, icon, True

    except requests.exceptions.RequestException as e:
        print(f"Network error fetching Nextcloud status: {e}")
        return None, None, False
    except ValueError as e:
        print(f"JSON parse error: {e}")
        print(f"Raw response: {resp.text[:200] if 'resp' in locals() else 'No response'}")
        return None, None, False
    except Exception as e:
        print(f"Unexpected error fetching Nextcloud status: {e}")
        return None, None, False

def get_nextcloud_status_with_retry(max_retries=3, delay=1):
    for attempt in range(max_retries):
        message, icon, success = get_nextcloud_status()
        if success:
            return message, icon, True
        if attempt < max_retries - 1:
            print(f"Retry {attempt+1}/{max_retries} in {delay}s...")
            time.sleep(delay)
            delay *= 2
    return None, None, False

def set_nextcloud_status(game_name):
    global PREVIOUS_STATUS
    headers = {
        "OCS-APIRequest": "true",
        "Accept": "application/json"
    }
    params = {"format": "json"}
    auth = HTTPBasicAuth(NEXTCLOUD_USER, NEXTCLOUD_APP_PASSWORD)

    if game_name:  # Game started
        if PREVIOUS_STATUS is None:
            print("Attempting to fetch previous status before setting game...")
            current_message, current_icon, success = get_nextcloud_status_with_retry(max_retries=3)
            if success:
                PREVIOUS_STATUS = (current_message, current_icon)
                print(f"Stored previous status: message='{current_message}', icon={current_icon}")
            else:
                print("Failed to fetch previous status after multiple attempts.")
        else:
            print("Previous status already stored, not overwriting.")

        # Set game status
        url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/user_status/api/v1/user_status/message/custom"
        data = {
            "statusIcon": "🎮",
            "message": f"Playing {game_name}"
        }
        try:
            resp = requests.put(url, headers=headers, params=params, auth=auth, data=data, timeout=10)
            resp.raise_for_status()
            print(f"Status updated: Playing {game_name}")
            notify("Nextcloud Status", f"Now playing: {game_name}")
        except Exception as e:
            print(f"Failed to set status: {e}")

    else:  # Game ended
        if PREVIOUS_STATUS is not None:
            prev_message, prev_icon = PREVIOUS_STATUS
            if prev_message is not None:
                # Build data: only include icon if it was not None
                data = {"message": prev_message}
                if prev_icon is not None:
                    data["statusIcon"] = prev_icon
                print(f"Restoring with data: {data}")
                url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/user_status/api/v1/user_status/message/custom"
                try:
                    resp = requests.put(url, headers=headers, params=params, auth=auth, data=data, timeout=10)
                    resp.raise_for_status()
                    print(f"Restored previous status: {prev_message}")
                    notify("Nextcloud Status", "Restored previous status")
                except Exception as e:
                    print(f"Failed to restore previous status: {e}")
            else:
                # Previous status had no message – just clear
                url_clear = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/user_status/api/v1/user_status/message"
                try:
                    resp = requests.delete(url_clear, headers=headers, params=params, auth=auth, timeout=10)
                    resp.raise_for_status()
                    print("Status cleared (previous status had no message).")
                    notify("Nextcloud Status", "Stopped playing")
                except Exception as e:
                    print(f"Failed to clear status: {e}")
            PREVIOUS_STATUS = None
        else:
            # No previous status stored – just clear
            url_clear = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/user_status/api/v1/user_status/message"
            try:
                resp = requests.delete(url_clear, headers=headers, params=params, auth=auth, timeout=10)
                resp.raise_for_status()
                print("Status cleared (no previous status stored).")
                notify("Nextcloud Status", "Stopped playing")
            except Exception as e:
                print(f"Failed to clear status: {e}")

def main():
    current_game = None
    in_game = False
    last_game_end = time.time() - RECENT_WINDOW * 2

    while True:
        new_game = get_current_steam_game()
        now = time.time()

        if new_game != current_game:
            if new_game is None:  # Game ended
                if in_game:
                    last_game_end = now
                    in_game = False
                set_nextcloud_status(None)
            else:  # Game started
                in_game = True
                set_nextcloud_status(new_game)
            current_game = new_game

        # Determine next poll interval
        if in_game:
            interval = IN_GAME_INTERVAL
        else:
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

import os
import json
import requests
import re
import sys

# --- Constants & Setup ---
GRAPH_API_VERSION = "v19.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
RULES_FILE = "rules.json"
PROCESSED_FILE = "processed_comments.json"

# --- Environment Variables ---
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
IG_USER_ID = os.getenv("IG_USER_ID")
INPUT_POST_URL = os.getenv("INPUT_POST_URL")
INPUT_KEYWORD = os.getenv("INPUT_KEYWORD")
INPUT_REPLY = os.getenv("INPUT_REPLY")

if not ACCESS_TOKEN or not IG_USER_ID:
    print("❌ ERROR: ACCESS_TOKEN and IG_USER_ID must be set in environment variables.")
    sys.exit(1)

# --- Helper Functions ---
def load_json(filepath, default_type):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ WARNING: {filepath} is corrupted. Initializing with default.")
            return default_type()
    return default_type()

def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"💾 Saved updates to {filepath}")

def extract_shortcode(url):
    # Matches /p/SHORTCODE or /reel/SHORTCODE and ignores query parameters
    match = re.search(r"(?:p|reel)/([^/?#&]+)", url)
    if match:
        return match.group(1)
    return None

# --- Main Logic ---
def main():
    print("🚀 Starting Instagram Auto-Reply Bot...")

    # 1. Load local lightweight database
    rules = load_json(RULES_FILE, dict)
    processed_comments = load_json(PROCESSED_FILE, list)

    # 2. Add new rule if inputs are provided from workflow_dispatch
    if INPUT_POST_URL and INPUT_KEYWORD and INPUT_REPLY:
        shortcode = extract_shortcode(INPUT_POST_URL)
        if shortcode:
            rules[shortcode] = {
                "keyword": INPUT_KEYWORD.strip(),
                "reply": INPUT_REPLY.strip()
            }
            print(f"✅ Added new rule for shortcode '{shortcode}': Keyword '{INPUT_KEYWORD}'")
            save_json(RULES_FILE, rules)
        else:
            print(f"⚠️ WARNING: Could not extract shortcode from URL '{INPUT_POST_URL}'")

    if not rules:
        print("ℹ️ No rules found. Exiting gracefully.")
        sys.exit(0)

    # 3. Fetch recent media (up to 50 items)
    print(f"📡 Fetching recent media for IG User ID: {IG_USER_ID}")
    media_url = f"{BASE_URL}/{IG_USER_ID}/media"
    media_params = {
        "fields": "id,shortcode",
        "limit": 50,
        "access_token": ACCESS_TOKEN
    }
    
    response = requests.get(media_url, params=media_params)
    if response.status_code != 200:
        print(f"❌ ERROR fetching media: {response.text}")
        sys.exit(1)
        
    media_items = response.json().get("data",[])
    print(f"ℹ️ Found {len(media_items)} media items.")

    # 4. Process comments for media matching our rules
    for item in media_items:
        media_id = item.get("id")
        shortcode = item.get("shortcode")

        if shortcode in rules:
            rule = rules[shortcode]
            keyword = rule["keyword"].lower()
            reply_text = rule["reply"]

            print(f"🔍 Checking comments for matched shortcode '{shortcode}' (Media ID: {media_id})...")
            
            # Fetch comments for this media item
            comments_url = f"{BASE_URL}/{media_id}/comments"
            comments_params = {
                "fields": "id,text",
                "limit": 100, # Adjust if you receive more than 100 comments between runs
                "access_token": ACCESS_TOKEN
            }
            
            comments_response = requests.get(comments_url, params=comments_params)
            if comments_response.status_code != 200:
                print(f"⚠️ ERROR fetching comments for {shortcode}: {comments_response.text}")
                continue
                
            comments = comments_response.json().get("data",[])
            print(f"💬 Found {len(comments)} comments on this post.")

            # 5. Check keywords and reply
            for comment in comments:
                comment_id = comment.get("id")
                comment_text = comment.get("text", "").lower()

                if keyword in comment_text and comment_id not in processed_comments:
                    print(f"🎯 Keyword matched in comment ID: {comment_id}. Replying...")
                    
                    # Post public reply
                    reply_url = f"{BASE_URL}/{comment_id}/replies"
                    reply_payload = {
                        "message": reply_text,
                        "access_token": ACCESS_TOKEN
                    }
                    
                    reply_resp = requests.post(reply_url, data=reply_payload)
                    if reply_resp.status_code == 200:
                        print(f"✅ Successfully replied to {comment_id}.")
                        processed_comments.append(comment_id)
                    else:
                        print(f"❌ Failed to reply to {comment_id}: {reply_resp.text}")

    # 6. Save updated processed comments state
    save_json(PROCESSED_FILE, processed_comments)
    print("🎉 Bot execution completed.")

if __name__ == "__main__":
    main()

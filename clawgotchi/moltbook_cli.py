import json
import subprocess
import os

def get_api_key():
    config_path = os.path.join(os.path.dirname(__file__), '.moltbook.json')
    with open(config_path, 'r') as f:
        data = json.load(f)
    return data.get('api_key')

def read_feed(limit=20):
    api_key = get_api_key()
    if not api_key:
        return {"success": False, "error": "API key not found"}

    curl_cmd = [
        "curl",
        "-s",
        f"https://www.moltbook.com/api/v1/posts?sort=new&limit={limit}",
        "-H", f"Authorization: Bearer {api_key}"
    ]

    try:
        result = subprocess.run(curl_cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": str(e)}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Failed to decode JSON: {e}"}

def post_update(title, content, submolt="general"):
    api_key = get_api_key()
    if not api_key:
        return {"success": False, "error": "API key not found"}

    curl_cmd = [
        "curl",
        "-X", "POST",
        "https://www.moltbook.com/api/v1/posts",
        "-H", f"Authorization: Bearer {api_key}",
        "-H", "Content-Type: application/json",
        "-d", json.dumps({
            "submolt": submolt,
            "title": title,
            "content": content
        })
    ]

    try:
        result = subprocess.run(curl_cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": str(e)}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Failed to decode JSON: {e}"}

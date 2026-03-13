from flask import Flask, render_template, abort, send_from_directory
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json
import markdown
import os
import time
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, "static/assets"), "etohlock.png")

creds = service_account.Credentials.from_service_account_info(
    json.loads(os.environ["GOOGLE_CREDENTIALS"]),
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

_cache = {}
CACHE_TTL = 300

def get_data():
    now = time.time()
    if 'data' in _cache and now - _cache['data']['time'] < CACHE_TTL:
        return _cache['data']['value']

    result = sheet.values().get(
        spreadsheetId="1fQ7znFTWrQBqkLbKfsQpBKhujcnXbh2XoESjXZmzlis",
        range="List!A:D",
        valueRenderOption="FORMATTED_VALUE"
    ).execute()
    rows = result.get("values", [])[1:]

    grouped = {}
    for row in rows:
        if len(row) < 3:
            continue
        
        uid = row[0].strip()
        name = row[1].strip() if len(row) > 1 else "Unknown"
        
        try:
            lock_level = int(row[2].strip())
        except:
            continue
        
        desc = row[3].strip() if len(row) > 3 else ""
        image_url = f"/static/assets/users/{name}.png"

        if not uid.isdigit():
            continue

        key = name.lower()
        if key not in grouped:
            grouped[key] = {
                "name": name,
                "lock_level": lock_level,
                "description": desc,
                "image_url": image_url,
                "accounts": [uid],
            }
        else:
            grouped[key]["accounts"].append(uid)
            if lock_level > grouped[key]["lock_level"]:
                grouped[key]["lock_level"] = lock_level
            if not grouped[key]["description"] and desc:
                grouped[key]["description"] = desc

    data = sorted(grouped.values(), key=lambda x: x["lock_level"], reverse=True)
    _cache['data'] = {'value': data, 'time': now}
    return data

@app.route('/')
def index():
    data = get_data()
    total = sum(len(p["accounts"]) for p in data)
    return render_template('index.html', users=data, total=total)

@app.route('/user/<string:name>')
def user_detail(name):
    data = get_data()
    user = next((u for u in data if u["name"].lower() == name.lower()), None)
    if not user:
        abort(404)

    evidence_html = None
    evidence_path = os.path.join("static", "evidence", f"{user['name']}.md")
    if os.path.exists(evidence_path):
        with open(evidence_path, "r") as f:
            evidence_html = markdown.markdown(f.read(), extensions=["tables", "fenced_code"])

    return render_template('user.html', user=user, evidence_html=evidence_html)

if __name__ == '__main__':
    app.run(debug=True)
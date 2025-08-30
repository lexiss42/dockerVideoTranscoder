# app.py
import os
import re
import json
import subprocess
import datetime
import jwt
from flask import Flask, request, render_template_string, send_from_directory, jsonify, redirect, make_response

# ---------- Config ----------
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
SECRET_KEY = "supersecretkey"          # For production, load from env/Secrets Manager
ALLOWED_OUTPUTS = (".mp4", ".mov", ".mkv")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY

# Demo users with meaningful distinctions
USERS = {"alice": "password123", "bob": "hunter2"}

# ---------- HTML ----------
LOGIN_PAGE = """
<!DOCTYPE html><html><head><title>Login</title></head>
<body>
  <h1>Login</h1>
  <form method="post" action="/login">
    <input type="text" name="username" placeholder="Username" required><br>
    <input type="password" name="password" placeholder="Password" required><br>
    <button type="submit">Login</button>
  </form>
</body></html>
"""

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/><title>Simple Transcoder</title></head>
<body>
  <h1>Welcome {{ username }}</h1>
  <form method="post" action="/logout"><button type="submit">Logout</button></form>

  <h2>Upload Video</h2>
  <form method="post" action="/upload" enctype="multipart/form-data">
    <input type="file" name="video" required><br><br>
    <label>Quality:</label>
    <select name="quality">
      <option value="1080">1080p</option><option value="720">720p</option>
      <option value="480">480p</option><option value="360">360p</option>
    </select><br><br>
    <label>Framerate:</label>
    <select name="framerate"><option value="30">30 fps</option><option value="60">60 fps</option></select><br><br>
    <label>Output Format:</label>
    <select name="format"><option value="mp4">MP4</option><option value="mov">MOV</option><option value="mkv">MKV</option></select><br><br>
    <button type="submit">Upload & Transcode</button>
  </form>

  <h2>Your Processed Videos</h2>
  <ul>
    {% for file, meta in files %}
      <li>
        <a href="/outputs/{{ username }}/{{ file }}">{{ file }}</a><br>
        <small>Resolution: {{ meta.get("resolution","?") }} | FPS: {{ meta.get("framerate","?") }}
        | Format: {{ meta.get("format","?") }} | Size: {{ meta.get("size_kb","?") }} KB</small>
      </li>
    {% endfor %}
  </ul>
</body></html>
"""

# ---------- Helpers ----------
SCALE_MAP = {"1080": "1920:1080", "720": "1280:720", "480": "854:480", "360": "640:360"}

def sanitizeFilename(filename: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", os.path.basename(filename))

def outputPaths(user: str, originalFilename: str, quality: str, framerate: str, fmt: str):
    safeBase = sanitizeFilename(os.path.splitext(originalFilename)[0])
    userFolder = os.path.join(OUTPUT_FOLDER, user)
    os.makedirs(userFolder, exist_ok=True)
    outName = f"{safeBase}_{quality}p_{framerate}fps.{fmt}"
    return outName, os.path.join(userFolder, outName)

def getMetadata(user: str, filename: str) -> dict:
    metaFile = os.path.join(OUTPUT_FOLDER, user, filename + ".json")
    if os.path.exists(metaFile):
        with open(metaFile, "r") as f:
            return json.load(f)
    return {}

def writeMetadata(path: str, *, resolution: str, framerate: str, fmt: str):
    sizeKb = os.path.getsize(path) // 1024 if os.path.exists(path) else None
    with open(path + ".json", "w") as f:
        json.dump({"resolution": f"{resolution}p", "framerate": framerate, "format": fmt, "size_kb": sizeKb}, f)

def generateToken(username: str):
    exp = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    return jwt.encode({"username": username, "exp": exp}, SECRET_KEY, algorithm="HS256")

def verifyToken(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

def getUserFromCookie():
    token = request.cookies.get("token")
    if not token:
        return None
    decoded = verifyToken(token)
    return decoded.get("username") if decoded else None

def getUserFromHeader():
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    decoded = verifyToken(auth.split(" ")[1])
    return decoded.get("username") if decoded else None

# ---------- Auth Gate (fix) ----------
PUBLIC_PATHS = {
    "/login",            # HTML login
    "/api/login",        # API login
    "/health"            # optional health endpoint
}

@app.before_request
def requireAuth():
    # Allow public paths
    if request.path in PUBLIC_PATHS:
        return
    # Allow static file downloads for API docs etc. (adjust if you add /static)
    if request.path.startswith("/static/"):
        return
    # API: everything under /api/* except /api/login requires header JWT
    if request.path.startswith("/api/"):
        if request.path == "/api/login":
            return
        if getUserFromHeader() is None:
            return jsonify({"error": "Unauthorized"}), 401
        return
    # HTML pages: require cookie JWT for everything except /login
    if request.path == "/login":
        return
    # For other HTML routes, check cookie
    if getUserFromCookie() is None:
        return redirect("/login")

# ---------- Web Routes ----------
@app.route("/health")
def health():
    return "ok"

@app.route("/", methods=["GET"])
def index():
    user = getUserFromCookie()
    userFolder = os.path.join(OUTPUT_FOLDER, user)
    os.makedirs(userFolder, exist_ok=True)
    files = [(f, getMetadata(user, f)) for f in os.listdir(userFolder) if f.lower().endswith(ALLOWED_OUTPUTS)]
    return render_template_string(HTML_PAGE, files=files, username=user)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return LOGIN_PAGE
    username = request.form.get("username")
    password = request.form.get("password")
    if username in USERS and USERS[username] == password:
        token = generateToken(username)
        resp = make_response(redirect("/"))
        resp.set_cookie("token", token, httponly=True, samesite="Lax")
        return resp
    return "Invalid credentials", 401

@app.route("/logout", methods=["POST"])
def logout():
    resp = make_response(redirect("/login"))
    resp.delete_cookie("token")
    return resp

@app.route("/upload", methods=["POST"])
def uploadFile():
    user = getUserFromCookie()
    return handleUpload(user, request, api=False)

@app.route("/outputs/<user>/<path:filename>")
def downloadFile(user, filename):
    current = getUserFromCookie()
    if current != user:
        return "Unauthorized", 403
    return send_from_directory(os.path.join(OUTPUT_FOLDER, user), filename, as_attachment=False)

# ---------- API Routes ----------
@app.route("/api/login", methods=["POST"])
def apiLogin():
    data = request.get_json(silent=True) or {}
    username, password = data.get("username"), data.get("password")
    if username in USERS and USERS[username] == password:
        return jsonify({"token": generateToken(username)})
    return jsonify({"error": "Invalid credentials"}), 401

@app.route("/api/upload", methods=["POST"])
def apiUpload():
    user = getUserFromHeader()      # enforced by before_request too; this keeps code explicit
    return handleUpload(user, request, api=True)

@app.route("/api/videos", methods=["GET"])
def apiVideos():
    user = getUserFromHeader()
    userFolder = os.path.join(OUTPUT_FOLDER, user)
    os.makedirs(userFolder, exist_ok=True)
    videos = [{"file": f, "metadata": getMetadata(user, f), "download_url": f"/outputs/{user}/{f}"}
              for f in os.listdir(userFolder) if f.lower().endswith(ALLOWED_OUTPUTS)]
    return jsonify(videos)

@app.route("/api/videos/<path:filename>", methods=["GET"])
def apiVideo(filename):
    user = getUserFromHeader()
    path = os.path.join(OUTPUT_FOLDER, user, filename)
    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404
    return jsonify({"file": filename, "metadata": getMetadata(user, filename), "download_url": f"/outputs/{user}/{filename}"})

# ---------- Shared Upload ----------
def handleUpload(user, req, api: bool):
    if "video" not in req.files:
        return (jsonify({"error": "No file uploaded"}), 400) if api else ("No file uploaded", 400)
    file = req.files["video"]
    if not file or file.filename.strip() == "":
        return (jsonify({"error": "No selected file"}), 400) if api else ("No selected file", 400)

    quality = req.form.get("quality", "720")
    framerate = req.form.get("framerate", "30")
    fmt = req.form.get("format", "mp4").lower()

    safeName = sanitizeFilename(file.filename)
    inputPath = os.path.join(UPLOAD_FOLDER, safeName)
    file.save(inputPath)

    outFilename, outputPath = outputPaths(user, safeName, quality, framerate, fmt)
    scale = SCALE_MAP.get(quality, SCALE_MAP["720"])

    subprocess.run(
        ["ffmpeg", "-y", "-i", inputPath,
         "-vf", f"scale={scale},fps={framerate}",
         "-c:v", "libx264", "-preset", "fast", "-crf", "23",
         "-c:a", "aac", "-b:a", "128k",
         outputPath],
        check=True,
    )

    writeMetadata(outputPath, resolution=quality, framerate=framerate, fmt=fmt)

    if api:
        return jsonify({
            "message": "Upload & transcode successful",
            "file": outFilename,
            "metadata": getMetadata(user, outFilename),
            "download_url": f"/outputs/{user}/{outFilename}"
        })
    else:
        return f"File uploaded and transcoded: <a href='/outputs/{user}/{outFilename}'>{outFilename}</a>"

# ---------- Main ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

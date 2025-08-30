# app.py
import os
import re
import json
import subprocess
from flask import Flask, request, render_template_string, send_from_directory, jsonify

# --------- Config ---------
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
ALLOWED_OUTPUTS = (".mp4", ".mov", ".mkv")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER

# --------- HTML Template ---------
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/><title>Simple Transcoder</title></head>
<body>
  <h1>Upload Video</h1>
  <form method="post" action="/upload" enctype="multipart/form-data">
    <input type="file" name="video" required><br><br>

    <label>Quality:</label>
    <select name="quality">
      <option value="1080">1080p</option>
      <option value="720">720p</option>
      <option value="480">480p</option>
      <option value="360">360p</option>
    </select><br><br>

    <label>Framerate:</label>
    <select name="framerate"><option value="30">30 fps</option><option value="60">60 fps</option></select><br><br>

    <label>Output Format:</label>
    <select name="format"><option value="mp4">MP4</option><option value="mov">MOV</option><option value="mkv">MKV</option></select><br><br>

    <button type="submit">Upload & Transcode</button>
  </form>

  <h2>Processed Videos</h2>
  <ul>
    {% for file, meta in files %}
      <li>
        <a href="/outputs/{{ file }}">{{ file }}</a><br>
        <small>
          Resolution: {{ meta.get("resolution","?") }} |
          FPS: {{ meta.get("framerate","?") }} |
          Format: {{ meta.get("format","?") }} |
          Size: {{ meta.get("size_kb","?") }} KB
        </small>
      </li>
    {% endfor %}
  </ul>
</body>
</html>
"""

# --------- Helpers ---------
SCALE_MAP = {
    "1080": "1920:1080",
    "720" : "1280:720",
    "480" : "854:480",
    "360" : "640:360",
}

def sanitizeFilename(filename: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", os.path.basename(filename))

def outputPaths(originalFilename: str, quality: str, framerate: str, fmt: str):
    safeBase = sanitizeFilename(os.path.splitext(originalFilename)[0])
    outName = f"{safeBase}_{quality}p_{framerate}fps.{fmt}"
    return outName, os.path.join(OUTPUT_FOLDER, outName)

def getMetadata(filename: str) -> dict:
    metaFile = os.path.join(OUTPUT_FOLDER, filename + ".json")
    if os.path.exists(metaFile):
        with open(metaFile, "r") as f:
            return json.load(f)
    return {}

def writeMetadata(path: str, *, resolution: str, framerate: str, fmt: str):
    sizeKb = os.path.getsize(path) // 1024 if os.path.exists(path) else None
    with open(path + ".json", "w") as f:
        json.dump({"resolution": f"{resolution}p", "framerate": framerate, "format": fmt, "size_kb": sizeKb}, f)

def listVideos():
    items = []
    for f in os.listdir(OUTPUT_FOLDER):
        if f.lower().endswith(ALLOWED_OUTPUTS):
            items.append({"file": f, "metadata": getMetadata(f), "download_url": f"/outputs/{f}"})
    return items

# --------- Routes ---------
@app.route("/", methods=["GET"])
def index():
    # Always return HTML at root
    files = [(f["file"], f["metadata"]) for f in listVideos()]
    return render_template_string(HTML_PAGE, files=files)

@app.route("/upload", methods=["POST"])
def uploadFile():
    if "video" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["video"]
    if not file or file.filename.strip() == "":
        return jsonify({"error": "No selected file"}), 400

    quality = request.form.get("quality", "720")
    framerate = request.form.get("framerate", "30")
    fmt = request.form.get("format", "mp4").lower()

    safeName = sanitizeFilename(file.filename)
    inputPath = os.path.join(UPLOAD_FOLDER, safeName)
    file.save(inputPath)

    outFilename, outputPath = outputPaths(safeName, quality, framerate, fmt)
    scale = SCALE_MAP.get(quality, SCALE_MAP["720"])

    subprocess.run([
        "ffmpeg", "-y", "-i", inputPath,
        "-vf", f"scale={scale},fps={framerate}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        outputPath], check=True)

    writeMetadata(outputPath, resolution=quality, framerate=framerate, fmt=fmt)
    return jsonify({"message": "Upload & transcode successful", "file": outFilename,
                    "metadata": getMetadata(outFilename), "download_url": f"/outputs/{outFilename}"})

@app.route("/outputs/<path:filename>", methods=["GET"])
def downloadFile(filename):
    if not any(filename.lower().endswith(ext) for ext in ALLOWED_OUTPUTS):
        return jsonify({"error": "Invalid filename"}), 400
    fullPath = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(fullPath):
        return jsonify({"error": "File not found"}), 404
    return jsonify({"file": filename, "metadata": getMetadata(filename), "download_url": f"/outputs/{filename}"})

@app.route("/videos", methods=["GET"])
def videos():
    return jsonify(listVideos())

# --------- Main ---------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

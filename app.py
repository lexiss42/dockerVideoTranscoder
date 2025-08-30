# app.py
import os
import subprocess
from flask import Flask, request, render_template_string, send_from_directory

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Simple Transcoder</title>
</head>
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
        <select name="framerate">
            <option value="30">30 fps</option>
            <option value="60">60 fps</option>
        </select><br><br>

        <label>Output Format:</label>
        <select name="format">
            <option value="mp4">MP4</option>
            <option value="mov">MOV</option>
            <option value="mkv">MKV</option>
        </select><br><br>

        <button type="submit">Upload & Transcode</button>
    </form>

    <h2>Processed Videos</h2>
    <ul>
    {% for file in files %}
        <li><a href="/outputs/{{ file }}">{{ file }}</a></li>
    {% endfor %}
    </ul>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    files = os.listdir(OUTPUT_FOLDER)
    return render_template_string(HTML_PAGE, files=files)

@app.route("/upload", methods=["POST"])
def upload_file():
    if "video" not in request.files:
        return "No file part", 400
    file = request.files["video"]
    if file.filename == "":
        return "No selected file", 400

    quality = request.form.get("quality", "720")
    framerate = request.form.get("framerate", "30")
    output_format = request.form.get("format", "mp4")

    input_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    base_name = os.path.splitext(file.filename)[0]
    output_filename = f"{base_name}_{quality}p_{framerate}fps.{output_format}"
    output_path = os.path.join(app.config["OUTPUT_FOLDER"], output_filename)

    file.save(input_path)

    # FFmpeg scaling filter
    scale_map = {
        "1080": "1920:1080",
        "720": "1280:720",
        "480": "854:480",
        "360": "640:360"
    }
    scale = scale_map.get(quality, "1280:720")

    subprocess.run(
        [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"scale={scale},fps={framerate}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            output_path
        ],
        check=True
    )

    return f"File uploaded and transcoded: <a href='/outputs/{os.path.basename(output_path)}'>{os.path.basename(output_path)}</a>"

@app.route("/outputs/<path:filename>")
def download_file(filename):
    return send_from_directory(app.config["OUTPUT_FOLDER"], filename, as_attachment=False)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

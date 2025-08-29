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

# Simple inline HTML template
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Simple Transcoder</title>
</head>
<body>
    <h1>Upload Video</h1>
    <form method="post" action="/upload" enctype="multipart/form-data">
        <input type="file" name="video"><br><br>

        <label for="quality">Select Quality:</label>
        <select name="quality">
            <option value="1080p_30">1080p 30fps</option>
            <option value="1080p_60">1080p 60fps</option>
            <option value="720p_30">720p 30fps</option>
            <option value="720p_60">720p 60fps</option>
            <option value="480p_30">480p 30fps</option>
            <option value="480p_60">480p 60fps</option>
            <option value="360p_30">360p 30fps</option>
            <option value="360p_60">360p 60fps</option>
        </select><br><br>

        <label for="format">Select Format:</label>
        <select name="format">
            <option value="mp4" selected>MP4</option>
            <option value="mov">MOV</option>
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
def uploadFile():
    if "video" not in request.files:
        return "No file part", 400
    file = request.files["video"]
    if file.filename == "":
        return "No selected file", 400

    quality = request.form.get("quality", "1080p_30")
    fmt = request.form.get("format", "mp4")

    # Parse resolution and fps
    resolution_map = {
        "1080p": "1920:1080",
        "720p": "1280:720",
        "480p": "854:480",
        "360p": "640:360",
    }
    res, fps = quality.split("_")
    scale = resolution_map[res]

    input_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    output_filename = f"{os.path.splitext(file.filename)[0]}_{res}_{fps}.{fmt}"
    output_path = os.path.join(app.config["OUTPUT_FOLDER"], output_filename)

    # Save uploaded file
    file.save(input_path)

    # Run ffmpeg synchronously
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"scale={scale},fps={fps}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            output_path
        ],
        check=True
    )

    return f"File uploaded and transcoded: <a href='/outputs/{os.path.basename(output_path)}'>{os.path.basename(output_path)}</a>"

@app.route("/outputs/<path:filename>")
def downloadFile(filename):
    return send_from_directory(app.config["OUTPUT_FOLDER"], filename, as_attachment=False)

if __name__ == "__main__":
    app.run(debug=True, port=5000)

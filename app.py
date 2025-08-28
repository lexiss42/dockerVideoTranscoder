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
        <input type="file" name="video">
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

    input_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    output_path = os.path.join(app.config["OUTPUT_FOLDER"], f"{os.path.splitext(file.filename)[0]}_transcoded.mp4")

    file.save(input_path)

    subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, "-c:v", "libx264", "-preset", "fast", "-crf", "23", output_path],
        check=True
    )

    return f"File uploaded and transcoded: <a href='/outputs/{os.path.basename(output_path)}'>{os.path.basename(output_path)}</a>"

@app.route("/outputs/<path:filename>")
def download_file(filename):
    return send_from_directory(app.config["OUTPUT_FOLDER"], filename, as_attachment=False)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


import os
import subprocess
import jwt
import datetime
from flask import Flask, request, send_from_directory, jsonify

app = Flask(__name__)

app.config["UPLOAD_FOLDER"] = "uploads"
app.config["OUTPUT_FOLDER"] = "outputs"
app.config["SECRET_KEY"] = "your-secret-key"

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["OUTPUT_FOLDER"], exist_ok=True)

# ---------------- TOKEN UTILS ---------------- #

def generateToken(user_id):
    expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    token = jwt.encode({"user_id": user_id, "exp": expiration}, app.config["SECRET_KEY"], algorithm="HS256")
    return token

def verifyToken(token):
    try:
        data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        return data
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def getJWTUser(token):
    data = verifyToken(token)
    if data:
        return data["user_id"]
    return None

# ---------------- ROUTES ---------------- #

@app.route("/")
def index():
    return """
    <!DOCTYPE html>
    <html>
    <body>
        <h2>Upload and Transcode Video</h2>
        <form action="/upload" method="post" enctype="multipart/form-data">
            <label for="video">Choose file:</label>
            <input type="file" name="video" required><br><br>

            <label for="quality">Quality:</label>
            <select name="quality">
                <option value="1080p">1080p</option>
                <option value="720p" selected>720p</option>
                <option value="480p">480p</option>
                <option value="360p">360p</option>
            </select><br><br>

            <label for="fps">FPS:</label>
            <select name="fps">
                <option value="30" selected>30</option>
                <option value="60">60</option>
            </select><br><br>

            <label for="filetype">Output type:</label>
            <select name="filetype">
                <option value="mp4" selected>mp4</option>
                <option value="webm">webm</option>
                <option value="mov">mov</option>
            </select><br><br>

            <button type="submit">Upload</button>
        </form>
    </body>
    </html>
    """

@app.route("/upload", methods=["POST"])
def uploadFile():
    if "video" not in request.files:
        return "No file part", 400
    file = request.files["video"]
    if file.filename == "":
        return "No selected file", 400

    input_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    output_ext = request.form.get("filetype", "mp4")
    output_path = os.path.join(app.config["OUTPUT_FOLDER"],
        f"{os.path.splitext(file.filename)[0]}_transcoded.{output_ext}")

    # Save uploaded file
    file.save(input_path)

    # Build ffmpeg args from quality + fps
    quality = request.form.get("quality", "720p")
    fps = request.form.get("fps", "30")

    scale_map = {
        "1080p": "1920:1080",
        "720p": "1280:720",
        "480p": "854:480",
        "360p": "640:360"
    }

    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale={scale_map.get(quality, '1280:720')},fps={fps}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        output_path
    ], check=True)

    return f"File uploaded and transcoded: <a href='/outputs/{os.path.basename(output_path)}'>{os.path.basename(output_path)}</a>"

@app.route("/outputs/<path:filename>")
def downloadFile(filename):
    return send_from_directory(app.config["OUTPUT_FOLDER"], filename, as_attachment=False)

# ---------------- MAIN ---------------- #

if __name__ == "__main__":
    app.run(debug=True)

# app.py
import os
import subprocess
import datetime
import jwt
from flask import Flask, request, render_template_string, send_from_directory, redirect, make_response

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
SECRET_KEY = "supersecretkey"  # change this in production!

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER
app.config["SECRET_KEY"] = SECRET_KEY

# Demo user (hardcoded for simplicity)
USER_CREDENTIALS = {"username": "admin", "password": "password123"}

# HTML Templates
LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head><title>Login</title></head>
<body>
    <h1>Login</h1>
    <form method="post" action="/login">
        <input type="text" name="username" placeholder="Username" required><br>
        <input type="password" name="password" placeholder="Password" required><br>
        <button type="submit">Login</button>
    </form>
</body>
</html>
"""

UPLOAD_PAGE = """
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

    <form action="/logout" method="post">
        <button type="submit">Logout</button>
    </form>
</body>
</html>
"""

# ---------------- AUTH HELPERS ----------------
def generateToken(username):
    expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    token = jwt.encode({"username": username, "exp": expiration}, app.config["SECRET_KEY"], algorithm="HS256")
    return token

def verifyToken(token):
    try:
        decoded = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        return decoded
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def getJWTUser():
    token = request.cookies.get("token")
    if not token:
        return None
    return verifyToken(token)

# ---------------- ROUTES ----------------
@app.route("/", methods=["GET"])
def index():
    user = getJWTUser()
    files = os.listdir(OUTPUT_FOLDER)

    if not user:
        return redirect("/login")

    return render_template_string(UPLOAD_PAGE, files=files)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return LOGIN_PAGE

    username = request.form.get("username")
    password = request.form.get("password")

    if username == USER_CREDENTIALS["username"] and password == USER_CREDENTIALS["password"]:
        token = generateToken(username)
        resp = make_response(redirect("/"))
        resp.set_cookie("token", token)
        return resp
    return "Invalid credentials", 401

@app.route("/logout", methods=["POST"])
def logout():
    resp = make_response(redirect("/login"))
    resp.delete_cookie("token")
    return resp

@app.route("/upload", methods=["POST"])
def uploadFile():
    user = getJWTUser()
    if not user:
        return redirect("/login")

    if "video" not in request.files:
        return "No file part", 400
    file = request.files["video"]
    if file.filename == "":
        return "No selected file", 400

    input_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    output_filename = f"{os.path.splitext(file.filename)[0]}_transcoded.mp4"
    output_path = os.path.join(app.config["OUTPUT_FOLDER"], output_filename)

    file.save(input_path)

    subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, "-c:v", "libx264", "-preset", "fast", "-crf", "23", output_path],
        check=True
    )

    return f"File uploaded and transcoded: <a href='/outputs/{output_filename}'>{output_filename}</a>"

@app.route("/outputs/<path:filename>")
def downloadFile(filename):
    return send_from_directory(app.config["OUTPUT_FOLDER"], filename, as_attachment=False)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

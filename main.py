from flask import Flask, render_template
from flask_session import Session
import os

app = Flask(__name__)
app.secret_key = os.environ.get("WEBHOOK_SECRET")
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


@app.route("/")
def index():
    return render_template("index.html")



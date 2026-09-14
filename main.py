import os
import secrets
import subprocess

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, abort
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash

import db
import sso
from projects import PROJECTS, get_project

app = Flask(__name__)
app.secret_key = os.environ.get("WEBHOOK_SECRET")
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db.init_db()


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return db.get_user_by_id(uid)


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


@app.context_processor
def inject_csrf():
    return {"csrf_token": get_csrf_token()}


def csrf_ok():
    sent = request.form.get("csrf_token", "")
    return bool(sent) and sent == session.get("csrf_token")


def safe_next(target):
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return "/"


@app.route("/login", methods=["GET", "POST"])
def login():
    next_url = safe_next(request.args.get("next") or request.form.get("next"))

    if request.method == "POST":
        if not csrf_ok():
            flash("That form expired - try again.", "error")
            return redirect(url_for("login", next=next_url))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = db.get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            return redirect(next_url)

        flash("Wrong username or password.", "error")
        return render_template("auth.html", mode="login", next=next_url)

    return render_template("auth.html", mode="login", next=next_url)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    next_url = safe_next(request.args.get("next") or request.form.get("next"))

    if request.method == "POST":
        if not csrf_ok():
            flash("That form expired - try again.", "error")
            return redirect(url_for("signup", next=next_url))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if len(username) < 3:
            flash("Username needs to be at least 3 characters.", "error")
        elif len(password) < 8:
            flash("Password needs to be at least 8 characters.", "error")
        elif password != confirm:
            flash("Passwords don't match.", "error")
        elif db.get_user_by_username(username):
            flash("That username's taken.", "error")
        else:
            user_id = db.create_user(username, generate_password_hash(password))
            session["user_id"] = user_id
            return redirect(next_url)

        return render_template("auth.html", mode="signup", next=next_url)

    return render_template("auth.html", mode="signup", next=next_url)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.pop("user_id", None)
    return redirect(url_for("index"))

@app.route("/sso/authorize")
def sso_authorize():
    client_id = request.args.get("client_id", "")
    redirect_uri = request.args.get("redirect_uri", "")

    client = sso.CLIENTS.get(client_id)
    if not client or redirect_uri != client["redirect_uri"]:
        return render_template("sso_error.html"), 400

    user = current_user()
    if not user:
        next_url = url_for("sso_authorize", client_id=client_id, redirect_uri=redirect_uri)
        return redirect(url_for("login", next=next_url))

    token = sso.issue_token(app.secret_key, user["id"], user["username"], client_id)
    return redirect(f"{redirect_uri}?token={token}")


@app.route("/sso/verify", methods=["POST"])
def sso_verify():
    data = request.get_json(silent=True) or request.form
    client_id = data.get("client_id", "")
    client_secret = data.get("client_secret", "")
    token = data.get("token", "")

    if not sso.check_client_secret(client_id, client_secret):
        return jsonify({"ok": False, "error": "bad client credentials"}), 401

    try:
        payload = sso.redeem_token(app.secret_key, token, client_id)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    return jsonify({
        "ok": True,
        "username": payload["username"],
        "cow_user_id": payload["uid"],
    })


def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


@app.route("/features", methods=["GET", "POST"])
@login_required
def features():
    user = current_user()

    if user == "theorangecow":
        admin = True
    else:
        admin = False

    if request.method == "POST":
        if not csrf_ok():
            flash("That form expired - try again.", "error")
            return redirect(url_for("features"))

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        if not title:
            flash("Give it a title.", "error")
        else:
            db.create_feature_request(user["id"], user["username"], title, description)
            flash("Request submitted - thanks!", "success")
        return redirect(url_for("features"))

    requests_list = db.get_all_feature_requests()
    return render_template("features.html", requests=requests_list, admin=admin)


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    user = current_user()
    if request.method == "POST":
        if not csrf_ok():
            flash("That form expired - try again.", "error")
            return redirect(url_for("account"))

        action = request.form.get("action")

        if action == "change_username":
            new_username = request.form.get("new_username", "").strip()
            current_password = request.form.get("current_password_u", "")

            if not check_password_hash(user["password_hash"], current_password):
                flash("Current password is incorrect.", "error")
            elif len(new_username) < 3:
                flash("Username needs to be at least 3 characters.", "error")
            elif db.get_user_by_username(new_username):
                flash("That username's taken.", "error")
            else:
                db.update_username(user["id"], new_username)
                flash("Username updated.", "success")

        elif action == "change_password":
            current_password = request.form.get("current_password_p", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not check_password_hash(user["password_hash"], current_password):
                flash("Current password is incorrect.", "error")
            elif len(new_password) < 8:
                flash("New password needs to be at least 8 characters.", "error")
            elif new_password != confirm_password:
                flash("Passwords don't match.", "error")
            else:
                db.update_password(user["id"], generate_password_hash(new_password))
                flash("Password updated.", "success")

        return redirect(url_for("account"))

    return render_template("account.html")

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user["username"] != "theorangecow":
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/admin/features", methods=["GET", "POST"])
@admin_required
def admin_features():
    if request.method == "POST":
        if not csrf_ok():
            flash("That form expired - try again.", "error")
            return redirect(url_for("admin_features"))

        feature_id = request.form.get("feature_id")
        new_status = request.form.get("status")

        valid_statuses = {"requested", "planned", "in_progress", "done", "declined"}

        if feature_id and new_status in valid_statuses:
            if new_status == "declined":
                db.delete_feature_request(int(feature_id))
                flash("Feature request declined and deleted.", "success")
            else:
                db.update_feature_status(int(feature_id), new_status)
                flash("Status updated.", "success")
        else:
            flash("Invalid status.", "error")

        return redirect(url_for("admin_features"))

    requests_list = db.get_all_feature_requests()
    return render_template("admin_features.html", requests=requests_list)


@app.route("/")
def index():
    roadmap = db.get_public_roadmap()
    return render_template("index.html", roadmap=roadmap)


@app.route("/library")
def library():
    return render_template("library.html")


@app.route("/projects")
def projects_list():
    return render_template("projects.html", projects=PROJECTS)


@app.route("/projects/<slug>")
def project_detail(slug):
    project = get_project(slug)
    if not project:
        abort(404)
    return render_template("project_detail.html", project=project)

APPLICATIONS = {
    "brainwave": {
        "name": "Brain Wave",
        "path": "/var/www/brainwave",
        "port": 7000
    },
    "flaskapp": {
        "name": "TheOrangeCow",
        "path": "/var/www/flaskapp",
        "port": 5000
    },
    "fun": {
        "name": "Cow.fun",
        "path": "/var/www/fun",
        "port": 6002
    },
    "libary": {
        "name": "Library",
        "path": "/var/www/libary",
        "port": 6000
    },
    "sockets": {
        "name": "Cow Servers",
        "path": "/var/www/sockets",
        "port": 6001
    },
    "post": {
        "name": "post",
        "path": "/var/www/post",
        "port": 6500
    }
}


def application_running(port):
    result = subprocess.run(
        ["sudo", "fuser", f"{port}/tcp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return result.returncode == 0


@admin_required
@app.route("/control")
def control():
    if not csrf_ok():
        flash("That form expired - try again.", "error")
        return redirect(url_for("control"))
    
    applications = {}

    for key, application in APPLICATIONS.items():
        applications[key] = {
            **application,
            "running": application_running(application["port"])
        }

    return render_template(
        "control.html",
        applications=applications
    )


@admin_required
@app.route("/control/<name>/start", methods=["POST"])
def control_start(name):
    if not csrf_ok():
        flash("That form expired - try again.", "error")
        return redirect(url_for("control"))
    application = APPLICATIONS.get(name)

    if not application:
        abort(404)

    subprocess.Popen(
        ["bash", os.path.join(application["path"], "update_app.sh")],
        cwd=application["path"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    flash(f"{application['name']} update started.", "success")

    return redirect(url_for("control"))


@admin_required
@app.route("/control/<name>/stop", methods=["POST"])
def control_stop(name):
    if not csrf_ok():
        flash("That form expired - try again.", "error")
        return redirect(url_for("control"))
    application = APPLICATIONS.get(name)

    if not application:
        abort(404)

    subprocess.run(
        ["sudo", "fuser", "-k", f"{application['port']}/tcp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    flash(f"{application['name']} stopped.", "success")

    return redirect(url_for("control"))


@admin_required
@app.route("/control/<name>/restart", methods=["POST"])
def control_restart(name):
    if not csrf_ok():
        flash("That form expired - try again.", "error")
        return redirect(url_for("control"))
    
    application = APPLICATIONS.get(name)

    if not application:
        abort(404)

    subprocess.run(
        ["sudo", "fuser", "-k", f"{application['port']}/tcp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    subprocess.Popen(
        ["bash", os.path.join(application["path"], "update_app.sh")],
        cwd=application["path"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    flash(f"{application['name']} restarted.", "success")

    return redirect(url_for("control"))

if __name__ == "__main__":
    app.run(debug=True)

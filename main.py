from flask import Flask, render_template, request, jsonify, session
import requests
import markdown
import base64
from flask_session import Session
import os
import hmac
import hashlib
import subprocess
from flask import request, abort

app = Flask(__name__)
app.secret_key = "super-secret-key"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

CUSTOM_DIR = {
    "house-778/": {
        "site": "http://127.0.0.1:5000/project/house-778",
        "house-778.github": "http://127.0.0.1:5000/repo/house-778"
    },
    "cheese/": {
        "site": "https://example.com/projectx",
        "Cheese.github": "https://example.com/projecty"
    },
    "github_repos/": {}
}

def get_current_folder():
    return session.get("current_folder", "")

def set_current_folder(path):
    session["current_folder"] = path

def build_prompt():
    path = get_current_folder()
    if path:
        return f"C:\\TheOrangeCow\\{path.rstrip('/')}>"
    return "C:\\TheOrangeCow>"

def get_github_repos():
    url = "https://api.github.com/users/TheOrangeCow/repos"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return [repo["name"].lower() + ".github" for repo in data]
    except:
        return []

@app.route("/")
def index():
    return render_template("index.html")

SECRET = os.environ.get("WEBHOOK_SECRET").encode()

@app.route('/update', methods=['POST'])
def update():
    signature = request.headers.get('X-Hub-Signature-256')
    if not signature:
        return "Forbidden", 403

    sha_name, received_sig = signature.split('=')

    mac = hmac.new(SECRET, msg=request.data, digestmod=hashlib.sha256)

    if not hmac.compare_digest(mac.hexdigest(), received_sig):
        return "Forbidden", 403

    subprocess.Popen(["/bin/bash", "/var/www/flaskapp/update_app.sh"])
    return "OK", 200

@app.route("/repo/<repo_name>")
def repo_page(repo_name):
    repo_url = f"https://api.github.com/repos/TheOrangeCow/{repo_name}"
    readme_url = f"https://api.github.com/repos/TheOrangeCow/{repo_name}/readme"
    contrib_url = f"https://api.github.com/repos/TheOrangeCow/{repo_name}/contributors"
    repo = requests.get(repo_url).json()
    readme = requests.get(readme_url).json()
    contributors = requests.get(contrib_url).json()
    readme_html = ""
    if "content" in readme:
        readme_md = base64.b64decode(readme["content"]).decode("utf-8")
        readme_html = markdown.markdown(readme_md, extensions=["fenced_code", "tables"])
    contrib_list = []
    for c in contributors[:5]:
        contrib_list.append({
            "name": c["login"],
            "avatar": c["avatar_url"],
            "url": c["html_url"]
        })
    return render_template(
        "repo.html",
        name=repo["name"],
        description=repo["description"],
        github=repo["html_url"],
        stars=repo["stargazers_count"],
        forks=repo["forks_count"],
        watchers=repo["watchers_count"],
        language=repo["language"],
        contributors=contrib_list,
        readme=readme_html
    )

@app.route("/command", methods=["POST"])
def command():
    cmd = request.json.get("command", "").strip()
    current_path = get_current_folder()
    if cmd.lower() == "dir":
        if current_path == "github_repos/":
            github_repos = get_github_repos()
            dirs = github_repos if github_repos else ["<Could not fetch GitHub repos>"]
        elif current_path == "":
            dirs = list(CUSTOM_DIR.keys())
        else:
            dirs = list(CUSTOM_DIR.get(current_path, {}).keys())
        return jsonify({"output": "\n".join(dirs), "prompt": build_prompt()})
    if cmd.lower().startswith("cd "):
        target = cmd[3:].strip()
        if target == "..":
            set_current_folder("")
            return jsonify({"output": "Back to root", "prompt": build_prompt()})
        elif target in CUSTOM_DIR:
            set_current_folder(target)
            return jsonify({"output": f"Entered folder {target}", "prompt": build_prompt()})
        else:
            return jsonify({"output": "Folder not found", "prompt": build_prompt()})
    if cmd.lower().startswith("start "):
        target = cmd[6:].strip()
        folder_contents = CUSTOM_DIR.get(current_path, {})
        if current_path == "github_repos/":
            github_repos = get_github_repos()
            if target in github_repos:
                repo_name = target.replace(".github", "")
                url = f"http://87.106.74.42/repo/{repo_name}"
                return jsonify({"output": f"Opening GitHub repository {repo_name}...", "prompt": build_prompt(), "redirect": url})
        if target in folder_contents:
            return jsonify({"output": f"Opening {target}...", "prompt": build_prompt(), "redirect": folder_contents[target]})
        return jsonify({"output": "Link or repository not found", "prompt": build_prompt()})

    if cmd.lower().startswith("load"):
        if current_path == "github_repos/":
            github_repos = get_github_repos()
            dirs = github_repos if github_repos else ["<Could not fetch GitHub repos>"]
        elif current_path == "":
            dirs = list(CUSTOM_DIR.keys())
        else:
            dirs = list(CUSTOM_DIR.get(current_path, {}).keys())
        ouput = ""
        for button in dirs:
            ouput += f"<button onclick=\"gotoplace('{button}')\">{button}</button><br>\n"
        return jsonify({"output": ouput, "prompt": build_prompt()})

    return jsonify({"output": "Command not recognized", "prompt": build_prompt()})


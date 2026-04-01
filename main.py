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
app.secret_key = os.environ.get("WEBHOOK_SECRET")
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

CUSTOM_DIR = {
    "favourite/": {
        "house-778": "https://house-778.theorangecow.org/",
        "cow-servers": "https://cow-servers.theorangecow.org/",
        "amoebavirtualmachine.github": "/repo/amoebavirtualmachine",
        "video-to-askii-art.github": "https://github.com/TheOrangeCow/Video-to-ASKII-Art",
        "unwinnable-0-x.github":"/repo/unwinnable-0-x"
    },
    "cow-servers/": {
        "site": "https://cow-servers.theorangecow.org/",
        "cow-servers.github": "/repo/cow_servers"
    },
    "house-778/": {
        "site": "https://house-778.theorangecow.org/",
        "cow-servers.github": "/repo/house-778"
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
    repos = []
    page = 1
    per_page = 100
    while True:
        url = f"https://api.github.com/users/TheOrangeCow/repos?per_page={per_page}&page={page}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            if not data:
                break
            repos.extend([repo["name"].lower() + ".github" for repo in data])
            page += 1
        except requests.RequestException:
            break
    return repos

@app.route("/")
def index():
    return render_template("index.html")



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
        elif target in CUSTOM_DIR.get(current_path, {}):
            if isinstance(CUSTOM_DIR[current_path][target], dict):
                set_current_folder(current_path + target + "/")
                return jsonify({"output": f"Entered folder {target}", "prompt": build_prompt()})
            else:
                return jsonify({"output": f"Opening {target}...", "prompt": build_prompt(), "redirect": CUSTOM_DIR[current_path][target]})
        else:
            return jsonify({"output": "Folder not found", "prompt": build_prompt()})

    if cmd.lower().startswith("start "):
        target = cmd[6:].strip()
        folder_contents = CUSTOM_DIR.get(current_path, {})
        if target in folder_contents:
            value = folder_contents[target]
            if isinstance(value, dict):
                set_current_folder(current_path + target + "/")
                return jsonify({"output": f"Entered folder {target}", "prompt": build_prompt()})
            else:
                return jsonify({"output": f"Opening {target}...", "prompt": build_prompt(), "redirect": value})
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


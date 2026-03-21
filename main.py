from flask import Flask, render_template, request, jsonify
import requests
import webbrowser
import markdown
import base64

app = Flask(__name__)

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

current_folder = {"path": ""}

def build_prompt():
    if current_folder["path"]:
        return f"C:\\TheOrangeCow\\{current_folder['path'].rstrip('/')}>"
    return "C:\\TheOrangeCow>"

def get_github_repos():
    url = "https://api.github.com/users/TheOrangeCow/repos"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if not data:
            return ["<no repos found>"]
        return [repo["name"].lower() + ".github" for repo in data]
    except Exception as e:
        print("Error fetching GitHub repos:", e)
        return ["<error fetching repos>"]

def list_current_dir():
    path = current_folder["path"]
    if path == "":
        return list(CUSTOM_DIR.keys())
    if path == "github_repos/":
        repos = get_github_repos()
        return repos if repos else ["<no repos found>"]
    folder_contents = CUSTOM_DIR.get(path, {})
    return list(folder_contents.keys()) if folder_contents else ["<empty folder>"]

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
        name=repo.get("name", ""),
        description=repo.get("description", ""),
        github=repo.get("html_url", ""),
        stars=repo.get("stargazers_count", 0),
        forks=repo.get("forks_count", 0),
        watchers=repo.get("watchers_count", 0),
        language=repo.get("language", ""),
        contributors=contrib_list,
        readme=readme_html
    )

@app.route("/command", methods=["POST"])
def command():
    cmd_raw = request.json.get("command", "").strip()
    cmd = cmd_raw.lower()
    if cmd == "dir":
        dirs = list_current_dir()
        return jsonify({"output": "\n".join(dirs), "prompt": build_prompt()})
    if cmd.startswith("cd "):
        target = cmd_raw[3:].strip()
        if target == "..":
            current_folder["path"] = ""
            return jsonify({"output": "Back to root", "prompt": build_prompt()})
        available_dirs = list_current_dir()
        available_dirs_normalized = [d.rstrip(".github") if d.endswith(".github") else d for d in available_dirs]
        if target in available_dirs_normalized:
            if target + ".github" in available_dirs:
                current_folder["path"] = "github_repos/"
            else:
                current_folder["path"] = target if target.endswith("/") else target + "/"
            return jsonify({"output": f"Entered folder {target}", "prompt": build_prompt()})
        return jsonify({"output": "Folder not found", "prompt": build_prompt()})
    if cmd.startswith("start "):
        target = cmd_raw[6:].strip()
        path = current_folder["path"]
        if path == "github_repos/":
            github_repos = get_github_repos()
            if target.lower() + ".github" in github_repos:
                repo_name = target.lower()
                return jsonify({
                    "output": f"Opening GitHub repository {repo_name}...",
                    "redirect": f"http://127.0.0.1:5000/repo/{repo_name}",
                    "prompt": build_prompt()
                })
        folder_contents = CUSTOM_DIR.get(path, {})
        if target in folder_contents:
            webbrowser.open(folder_contents[target])
            return jsonify({"output": f"Opening {target}...", "prompt": build_prompt()})
        return jsonify({"output": "Link or repository not found", "prompt": build_prompt()})
    return jsonify({"output": "Command not recognized", "prompt": build_prompt()})


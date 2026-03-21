#     .-.;;;;;;'                                                   .-._   .-._.          
#    (_)  .; .;           .;;.    .-                             .: (_)`-'               
#         :  ;;-.  .-.   ;;  `;`-'.;.::..-.    . ,';.  ,:.,' .-. ::      .-.  `;     .-  
#       .:' ;;  ;.;.-'  ;;    :.  .;   ;   :   ;;  ;; :   ;.;.-' ::   _ ;   ;';  ;   ;   
#     .-:._.;`  ` `:::';;     ;'.;'    `:::'-'';  ;;   `-:' `:::'`: .; )`;;'  `.' `.'    
#    (_/  `-           `;.__.'                ;    `.-._:'         `--'                  

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

global current_folder
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
        return [repo["name"].lower() + ".github" for repo in data]
    except Exception as e:
        print("Error fetching GitHub repos:", e)
        return []

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
    cmd = request.json.get("command", "").strip().lower()

    path = current_folder["path"]

    # ---- DIR ----
    if cmd == "dir":
        if path == "":
            dirs = list(CUSTOM_DIR.keys())
        elif path == "github_repos/":
            dirs = get_github_repos()
        else:
            dirs = list(CUSTOM_DIR.get(path, {}).keys())
        return jsonify({"output": "\n".join(dirs), "prompt": build_prompt()})

    # ---- CD ----
    if cmd.startswith("cd "):
        target = cmd[3:].strip()
        if target == "..":
            current_folder["path"] = ""
            return jsonify({"output": "Back to root", "prompt": build_prompt()})
        elif target in CUSTOM_DIR:
            current_folder["path"] = target
            return jsonify({"output": f"Entered folder {target}", "prompt": build_prompt()})
        elif path == "github_repos/":
            # only allow cd inside github_repos if folder matches a repo
            if target in get_github_repos():
                current_folder["path"] = f"github_repos/{target}/"
                return jsonify({"output": f"Entered GitHub repo {target}", "prompt": build_prompt()})
        return jsonify({"output": "Folder not found", "prompt": build_prompt()})

    # ---- START ----
    if cmd.startswith("start "):
        target = cmd[6:].strip()
        if path == "github_repos/":
            github_repos = get_github_repos()
            if target in github_repos:
                repo_name = target.replace(".github", "")
                return jsonify({
                    "output": f"Opening GitHub repository {repo_name}...",
                    "redirect": f"/repo/{repo_name}",
                    "prompt": build_prompt()
                })
            else:
                return jsonify({"output": "Repository not found", "prompt": build_prompt()})
        elif path:
            folder_links = CUSTOM_DIR.get(path, {})
            if target in folder_links:
                return jsonify({
                    "output": f"Opening {target}...",
                    "redirect": folder_links[target],
                    "prompt": build_prompt()
                })
        else:
            # check root level links
            for folder, links in CUSTOM_DIR.items():
                if target in links:
                    return jsonify({
                        "output": f"Opening {target}...",
                        "redirect": links[target],
                        "prompt": build_prompt()
                    })
        return jsonify({"output": "Link or repository not found", "prompt": build_prompt()})

    return jsonify({"output": "Command not recognized", "prompt": build_prompt()})


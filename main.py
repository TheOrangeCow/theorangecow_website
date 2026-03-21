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
    cmd = request.json.get("command", "").strip()

    # Handle 'dir'
    if cmd.lower() == "dir":
        if current_folder["path"] == "github_repos/":
            dirs = get_github_repos()
        elif current_folder["path"] == "":
            dirs = list(CUSTOM_DIR.keys())
        else:
            folder_name = current_folder["path"]
            dirs = list(CUSTOM_DIR.get(folder_name, {}).keys())
        return jsonify({
            "output": "\n".join(dirs),
            "prompt": build_prompt()
            })

    # Handle 'cd'
    if cmd.lower().startswith("cd "):
        target = cmd[3:].strip()
        if target == "..":
            current_folder["path"] = ""
            return jsonify({
                "output": "Back to root",
                "prompt": build_prompt()
                })
        elif target in CUSTOM_DIR:
            current_folder["path"] = target
            return jsonify({
                "output": f"Entered folder {target}",
                "prompt": build_prompt()
                })
        else:
            return jsonify({
                "output": "Folder not found",
                "prompt": build_prompt()
                })

    # Handle 'start'
    
    if cmd.lower().startswith("start "):
        target = cmd[6:].strip()

       
        if current_folder["path"] == "github_repos/":
            github_repos = get_github_repos()
            print(target)
            if target in github_repos:
                repo_name = target.replace(".github", "")
                url = f"https://github.com/TheOrangeCow/{repo_name}"
                print(url)
                return jsonify({
                    "output": f"Opening GitHub repository {repo_name}...",
                    "redirect":f"http://127.0.0.1:5000/repo/{repo_name}",
                    "prompt": build_prompt()
                    })
        elif current_folder["path"]:
            folder_contents = CUSTOM_DIR.get(current_folder["path"], {})
            if target in folder_contents:
                webbrowser.open(folder_contents[target])
                return jsonify({
                    "output": f"Opening {target}...",
                    "prompt": build_prompt()
                    })
            else:
                return jsonify({
                    "output": "Link not found in current folder",
                    "prompt": build_prompt()
                    })

        for folder, links in CUSTOM_DIR.items():
            if target in links:
                webbrowser.open(links[target])
                return jsonify({
                    "output": f"Opening {target}...",
                    "prompt": build_prompt()
                    })

        

        return jsonify({
            "output": "Link or repository not found",
            "prompt": build_prompt()
            })

    return jsonify({
        "output": "Command not recognized",
        "prompt": build_prompt()
        })

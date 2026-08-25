from flask import Flask, request, jsonify
import subprocess
import shlex

app = Flask(__name__)

DOCKSMITH_BIN = "docksmith"  # assumes it's on PATH; use full path if sudo strips it

def run_docksmith(args_list, use_sudo=False):
    cmd = (["sudo"] if use_sudo else []) + [DOCKSMITH_BIN] + args_list
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return {
        "cmd": " ".join(shlex.quote(c) for c in cmd),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }

@app.route("/build", methods=["POST"])
def build():
    data = request.get_json(force=True, silent=True) or {}
    tag = data.get("tag", "myapp:latest")
    context = data.get("context", "sampleapp/")
    no_cache = data.get("no_cache", False)

    args = ["build", "-t", tag, context]
    if no_cache:
        args.append("--no-cache")

    result = run_docksmith(args)
    return jsonify(result), (200 if result["returncode"] == 0 else 500)

@app.route("/run", methods=["POST"])
def run_container():
    data = request.get_json(force=True, silent=True) or {}
    tag = data.get("tag", "myapp:latest")
    env_overrides = data.get("env", {})  # e.g. {"GREETING": "Heyyyy"}

    args = ["run"]
    for k, v in env_overrides.items():
        args += ["-e", f"{k}={v}"]
    args.append(tag)

    result = run_docksmith(args, use_sudo=True)  # run needs sudo for chroot
    return jsonify(result), (200 if result["returncode"] == 0 else 500)

@app.route("/images", methods=["GET"])
def list_images():
    result = run_docksmith(["images"])
    return jsonify(result), (200 if result["returncode"] == 0 else 500)

@app.route("/rmi", methods=["POST"])
def remove_image():
    data = request.get_json(force=True, silent=True) or {}
    tag = data.get("tag")
    if not tag:
        return jsonify({"error": "tag is required"}), 400

    result = run_docksmith(["rmi", tag])
    return jsonify(result), (200 if result["returncode"] == 0 else 500)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

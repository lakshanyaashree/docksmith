import json
import os
import hashlib
from datetime import datetime, timezone

DOCKSMITH_DIR = os.path.expanduser("~/.docksmith")
IMAGES_DIR = os.path.join(DOCKSMITH_DIR, "images")
LAYERS_DIR = os.path.join(DOCKSMITH_DIR, "layers")
CACHE_DIR = os.path.join(DOCKSMITH_DIR, "cache")

def ensure_dirs():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(LAYERS_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

def image_path(name, tag):
    return os.path.join(IMAGES_DIR, f"{name}_{tag}.json")

def load_image(name, tag):
    path = image_path(name, tag)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Image {name}:{tag} not found in local store.")
    with open(path, "r") as f:
        return json.load(f)

def save_image(manifest):
    ensure_dirs()
    name = manifest["name"]
    tag = manifest["tag"]
    path = image_path(name, tag)

    # Compute digest: serialize with digest="" then hash
    temp = dict(manifest)
    temp["digest"] = ""
    serialized = json.dumps(temp, sort_keys=True).encode("utf-8")
    digest = "sha256:" + hashlib.sha256(serialized).hexdigest()
    manifest["digest"] = digest

    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)

    return digest

def list_images():
    ensure_dirs()
    images = []
    for fname in os.listdir(IMAGES_DIR):
        if fname.endswith(".json"):
            with open(os.path.join(IMAGES_DIR, fname), "r") as f:
                manifest = json.load(f)
                images.append(manifest)
    return images

def delete_image(name, tag):
    path = image_path(name, tag)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Image {name}:{tag} not found.")
    with open(path, "r") as f:
        manifest = json.load(f)
    for layer in manifest.get("layers", []):
        digest = layer["digest"]
        layer_file = os.path.join(LAYERS_DIR, digest.replace("sha256:", "") + ".tar")
        if os.path.exists(layer_file):
            os.remove(layer_file)
    os.remove(path)

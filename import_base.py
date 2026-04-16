import json
import os
import hashlib
import shutil
from datetime import datetime, timezone

DOCKSMITH_DIR = os.path.expanduser("~/.docksmith")
IMAGES_DIR = os.path.join(DOCKSMITH_DIR, "images")
LAYERS_DIR = os.path.join(DOCKSMITH_DIR, "layers")

def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return "sha256:" + h.hexdigest()

def import_base_image(tar_path, name, tag):
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(LAYERS_DIR, exist_ok=True)

    digest = sha256_of_file(tar_path)
    hex_digest = digest.replace("sha256:", "")
    dest = os.path.join(LAYERS_DIR, hex_digest + ".tar")

    if not os.path.exists(dest):
        shutil.copy2(tar_path, dest)
        print(f"Stored layer: {dest}")
    else:
        print(f"Layer already exists: {dest}")

    size = os.path.getsize(dest)

    manifest = {
        "name": name,
        "tag": tag,
        "digest": "",
        "created": datetime.now(timezone.utc).isoformat(),
        "config": {
            "Env": [],
            "Cmd": ["/bin/sh"],
            "WorkingDir": "/"
        },
        "layers": [
            {
                "digest": digest,
                "size": size,
                "createdBy": f"imported from {os.path.basename(tar_path)}"
            }
        ]
    }

    temp = dict(manifest)
    temp["digest"] = ""
    serialized = json.dumps(temp, sort_keys=True).encode("utf-8")
    final_digest = "sha256:" + hashlib.sha256(serialized).hexdigest()
    manifest["digest"] = final_digest

    image_path = os.path.join(IMAGES_DIR, f"{name}_{tag}.json")
    with open(image_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Imported image {name}:{tag} -> {final_digest}")

import_base_image(os.path.expanduser("~/alpine.tar.gz"), "alpine", "3.18")

import os
import hashlib
import tarfile
import tempfile
import shutil
import glob
import subprocess
import time
import json
from datetime import datetime, timezone

from .parser import parse_docksmithfile
from .image import load_image, save_image, LAYERS_DIR, IMAGES_DIR
from .cache import compute_cache_key, lookup, store

def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return "sha256:" + h.hexdigest()

def create_layer_tar(src_dir, files_to_add):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tar")
    tmp.close()
    with tarfile.open(tmp.name, "w") as tar:
        for arcname, realpath in sorted(files_to_add, key=lambda x: x[0]):
            info = tar.gettarinfo(realpath, arcname=arcname)
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            if os.path.isfile(realpath):
                with open(realpath, "rb") as f:
                    tar.addfile(info, f)
            else:
                tar.addfile(info)
    return tmp.name

def store_layer(tmp_tar_path):
    digest = sha256_of_file(tmp_tar_path)
    hex_digest = digest.replace("sha256:", "")
    dest = os.path.join(LAYERS_DIR, hex_digest + ".tar")
    os.makedirs(LAYERS_DIR, exist_ok=True)
    if not os.path.exists(dest):
        shutil.move(tmp_tar_path, dest)
    else:
        os.remove(tmp_tar_path)
    return digest, os.path.getsize(dest)

def extract_layers(layer_digests, target_dir):
    for digest in layer_digests:
        tar_path = os.path.join(LAYERS_DIR, digest.replace("sha256:", "") + ".tar")
        if not os.path.exists(tar_path):
            raise FileNotFoundError(f"Layer {digest} not found on disk.")
        with tarfile.open(tar_path, "r") as tar:
            tar.extractall(path=target_dir)

def run_in_isolation(command, rootfs, workdir, env_vars):
    full_workdir = os.path.join(rootfs, workdir.lstrip("/")) if workdir else rootfs
    os.makedirs(full_workdir, exist_ok=True)

    env = os.environ.copy()
    env.update(env_vars)

    for d in ["proc", "dev", "sys", "tmp"]:
        os.makedirs(os.path.join(rootfs, d), exist_ok=True)

    cmd = [
        "sudo", "chroot", rootfs,
        "/bin/sh", "-c", command
    ]

    result = subprocess.run(cmd, env=env)
    return result.returncode

def build(context_dir, name, tag, no_cache=False):
    docksmithfile = os.path.join(context_dir, "Docksmithfile")
    if not os.path.exists(docksmithfile):
        raise FileNotFoundError(f"No Docksmithfile found in {context_dir}")

    instructions = parse_docksmithfile(docksmithfile)

    if not instructions or instructions[0][0] != "FROM":
        raise ValueError("Docksmithfile must start with FROM")

    from_instr = instructions[0]
    from_arg = from_instr[1]
    if ":" in from_arg:
        base_name, base_tag = from_arg.split(":", 1)
    else:
        base_name, base_tag = from_arg, "latest"

    total_steps = len(instructions)
    print(f"Step 1/{total_steps} : FROM {from_arg}")

    base_image = load_image(base_name, base_tag)
    base_layers = base_image.get("layers", [])
    base_config = base_image.get("config", {})
    base_digest = base_image.get("digest", "")

    accumulated_layers = list(base_layers)
    config = {
        "Env": list(base_config.get("Env", [])),
        "Cmd": base_config.get("Cmd", []),
        "WorkingDir": base_config.get("WorkingDir", "")
    }

    env_state = {}
    for e in config["Env"]:
        if "=" in e:
            k, v = e.split("=", 1)
            env_state[k] = v

    workdir = config["WorkingDir"]
    prev_digest = base_digest
    cache_miss_triggered = False
    created_at = None

    for idx, (instruction, argument, lineno) in enumerate(instructions[1:], start=2):
        step_label = f"Step {idx}/{total_steps} : {instruction} {argument if not isinstance(argument, list) else json.dumps(argument)}"

        if instruction == "WORKDIR":
            workdir = argument
            config["WorkingDir"] = workdir
            print(step_label)
            continue

        elif instruction == "ENV":
            if "=" in argument:
                k, v = argument.split("=", 1)
                env_state[k] = v
                config["Env"].append(f"{k}={v}")
            print(step_label)
            continue

        elif instruction == "CMD":
            config["Cmd"] = argument
            print(step_label)
            continue

        elif instruction in ("COPY", "RUN"):
            cache_key = None
            if not no_cache and not cache_miss_triggered:
                cache_key = compute_cache_key(
                    prev_digest, instruction, argument,
                    workdir, env_state,
                    context_dir if instruction == "COPY" else None
                )
                cached_digest = lookup(cache_key)
                if cached_digest:
                    print(f"{step_label} [CACHE HIT]")
                    layer_entry = {
                        "digest": cached_digest,
                        "size": os.path.getsize(os.path.join(LAYERS_DIR, cached_digest.replace("sha256:", "") + ".tar")),
                        "createdBy": f"{instruction} {argument}"
                    }
                    accumulated_layers.append(layer_entry)
                    prev_digest = cached_digest
                    continue
                else:
                    cache_miss_triggered = True

            start = time.time()

            rootfs = tempfile.mkdtemp(prefix="docksmith_rootfs_")
            try:
                extract_layers([l["digest"] for l in accumulated_layers], rootfs)

                if instruction == "COPY":
                    parts = argument.split()
                    src_pattern = parts[0]
                    dest = parts[1]
                    dest_full = os.path.join(rootfs, dest.lstrip("/"))
                    os.makedirs(dest_full, exist_ok=True)

                    matched = sorted(glob.glob(os.path.join(context_dir, src_pattern), recursive=True))
                    files_to_add = []
                    for fpath in matched:
                        if os.path.isfile(fpath):
                            arcname = os.path.join(dest.lstrip("/"), os.path.basename(fpath))
                            dest_file = os.path.join(rootfs, arcname)
                            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                            shutil.copy2(fpath, dest_file)
                            files_to_add.append((arcname, dest_file))

                    tmp_tar = create_layer_tar(rootfs, files_to_add)

                elif instruction == "RUN":
                    env_dict = dict(e.split("=", 1) for e in config["Env"] if "=" in e)
                    rc = run_in_isolation(argument, rootfs, workdir, env_dict)
                    if rc != 0:
                        raise RuntimeError(f"RUN command failed with exit code {rc}: {argument}")

                    files_to_add = []
                    for dirpath, dirnames, filenames in os.walk(rootfs):
                        for fname in filenames:
                            full = os.path.join(dirpath, fname)
                            arcname = os.path.relpath(full, rootfs)
                            files_to_add.append((arcname, full))

                    tmp_tar = create_layer_tar(rootfs, files_to_add)

                elapsed = time.time() - start
                digest, size = store_layer(tmp_tar)

                if not no_cache and cache_key:
                    store(cache_key, digest)

                print(f"{step_label} [CACHE MISS] {elapsed:.2f}s")

                layer_entry = {
                    "digest": digest,
                    "size": size,
                    "createdBy": f"{instruction} {argument}"
                }
                accumulated_layers.append(layer_entry)
                prev_digest = digest

            finally:
                shutil.rmtree(rootfs, ignore_errors=True)

    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()

    manifest = {
        "name": name,
        "tag": tag,
        "digest": "",
        "created": created_at,
        "config": config,
        "layers": accumulated_layers
    }

    digest = save_image(manifest)
    short = digest.replace("sha256:", "")[:12]
    print(f"Successfully built sha256:{short} {name}:{tag}")
    return digest

import json
import os
import hashlib

DOCKSMITH_DIR = os.path.expanduser("~/.docksmith")
CACHE_DIR = os.path.join(DOCKSMITH_DIR, "cache")
LAYERS_DIR = os.path.join(DOCKSMITH_DIR, "layers")

CACHE_INDEX = os.path.join(CACHE_DIR, "index.json")

def load_index():
    if not os.path.exists(CACHE_INDEX):
        return {}
    with open(CACHE_INDEX, "r") as f:
        return json.load(f)

def save_index(index):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_INDEX, "w") as f:
        json.dump(index, f, indent=2)

def compute_cache_key(prev_digest, instruction, argument, workdir, env_state, context_dir=None):
    hasher = hashlib.sha256()
    hasher.update(prev_digest.encode("utf-8"))
    hasher.update(instruction.encode("utf-8"))

    if isinstance(argument, list):
        hasher.update(json.dumps(argument).encode("utf-8"))
    else:
        hasher.update(argument.encode("utf-8"))

    hasher.update(workdir.encode("utf-8"))

    # ENV state sorted lexicographically
    sorted_env = sorted(env_state.items())
    env_str = "&".join(f"{k}={v}" for k, v in sorted_env)
    hasher.update(env_str.encode("utf-8"))

    # For COPY: hash each source file sorted by path
    if instruction == "COPY" and context_dir:
        parts = argument.split()
        src = parts[0]
        import glob
        pattern = os.path.join(context_dir, src)
        files = sorted(glob.glob(pattern, recursive=True))
        for fpath in files:
            if os.path.isfile(fpath):
                with open(fpath, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                rel = os.path.relpath(fpath, context_dir)
                hasher.update(rel.encode("utf-8"))
                hasher.update(file_hash.encode("utf-8"))

    return hasher.hexdigest()

def lookup(cache_key):
    index = load_index()
    if cache_key not in index:
        return None
    digest = index[cache_key]
    layer_file = os.path.join(LAYERS_DIR, digest.replace("sha256:", "") + ".tar")
    if not os.path.exists(layer_file):
        return None
    return digest

def store(cache_key, digest):
    index = load_index()
    index[cache_key] = digest
    save_index(index)

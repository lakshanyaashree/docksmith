import os
import subprocess
import tempfile
import shutil
import tarfile

from .image import load_image, LAYERS_DIR

def extract_layers(layer_digests, target_dir):
    for digest in layer_digests:
        tar_path = os.path.join(LAYERS_DIR, digest.replace("sha256:", "") + ".tar")
        if not os.path.exists(tar_path):
            raise FileNotFoundError(f"Layer {digest} not found on disk.")
        with tarfile.open(tar_path, "r") as tar:
            tar.extractall(path=target_dir)

def run_container(name, tag, cmd_override=None, env_overrides=None):
    if env_overrides is None:
        env_overrides = {}

    manifest = load_image(name, tag)
    config = manifest.get("config", {})
    layers = manifest.get("layers", [])

    cmd = cmd_override if cmd_override else config.get("Cmd", [])
    if not cmd:
        raise ValueError(f"No CMD defined in image {name}:{tag} and no command provided.")

    # Start with image ENV
    env = {}
    for e in config.get("Env", []):
        if "=" in e:
            k, v = e.split("=", 1)
            env[k] = v

    # Apply overrides on top
    env.update(env_overrides)

    workdir = config.get("WorkingDir", "/")

    rootfs = tempfile.mkdtemp(prefix="docksmith_run_")
    try:
        extract_layers([l["digest"] for l in layers], rootfs)

        for d in ["proc", "dev", "sys", "tmp"]:
            os.makedirs(os.path.join(rootfs, d), exist_ok=True)

        full_workdir = os.path.join(rootfs, workdir.lstrip("/"))
        os.makedirs(full_workdir, exist_ok=True)

        if isinstance(cmd, list):
            shell_cmd = " ".join(cmd)
        else:
            shell_cmd = cmd

        # Build env string for chroot
        env_args = []
        for k, v in env.items():
            env_args.extend(["-e", f"{k}={v}"])

        run_cmd = ["sudo", "env"] + [f"{k}={v}" for k, v in env.items()] + [
            "chroot", rootfs,
            "/bin/sh", "-c", shell_cmd
        ]

        result = subprocess.run(run_cmd)
        print(f"Container exited with code {result.returncode}")
        return result.returncode

    finally:
        shutil.rmtree(rootfs, ignore_errors=True)

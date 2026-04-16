import argparse
import sys
import os

from .builder import build
from .image import list_images, delete_image, load_image
from .runtime import run_container

def cmd_build(args):
    name, tag = args.tag.split(":") if ":" in args.tag else (args.tag, "latest")
    context = os.path.abspath(args.context)
    build(context, name, tag, no_cache=args.no_cache)

def cmd_images(args):
    images = list_images()
    if not images:
        print("No images found.")
        return
    print(f"{'NAME':<20} {'TAG':<15} {'ID':<15} {'CREATED'}")
    print("-" * 70)
    for img in images:
        name = img.get("name", "")
        tag = img.get("tag", "")
        digest = img.get("digest", "")
        short_id = digest.replace("sha256:", "")[:12]
        created = img.get("created", "")
        print(f"{name:<20} {tag:<15} {short_id:<15} {created}")

def cmd_rmi(args):
    if ":" in args.name:
        name, tag = args.name.split(":", 1)
    else:
        name, tag = args.name, "latest"
    try:
        delete_image(name, tag)
        print(f"Deleted {name}:{tag}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

def cmd_run(args):
    if ":" in args.image:
        name, tag = args.image.split(":", 1)
    else:
        name, tag = args.image, "latest"

    env_overrides = {}
    for e in args.env:
        if "=" in e:
            k, v = e.split("=", 1)
            env_overrides[k] = v

    cmd_override = args.cmd if args.cmd else None

    try:
        run_container(name, tag, cmd_override=cmd_override, env_overrides=env_overrides)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(prog="docksmith")
    subparsers = parser.add_subparsers(dest="command")

    # build
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("-t", dest="tag", required=True)
    build_parser.add_argument("context")
    build_parser.add_argument("--no-cache", action="store_true")

    # images
    subparsers.add_parser("images")

    # rmi
    rmi_parser = subparsers.add_parser("rmi")
    rmi_parser.add_argument("name")

    # run
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("image")
    run_parser.add_argument("-e", dest="env", action="append", default=[])
    run_parser.add_argument("cmd", nargs="?", default=None)

    args = parser.parse_args()

    if args.command == "build":
        cmd_build(args)
    elif args.command == "images":
        cmd_images(args)
    elif args.command == "rmi":
        cmd_rmi(args)
    elif args.command == "run":
        cmd_run(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

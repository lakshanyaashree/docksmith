# Docksmith 🔨

A simplified Docker-like build and container runtime system built from scratch in Python — no Docker, no runc, no containerd. Uses raw Linux OS primitives for process isolation.

---

## What It Does

Docksmith implements three things from scratch:

1. **A build system** — reads a `Docksmithfile` and executes 6 instructions (`FROM`, `COPY`, `RUN`, `WORKDIR`, `ENV`, `CMD`). Each `COPY` and `RUN` produces an immutable delta layer stored as a content-addressed tar file.
2. **A build cache** — deterministic and correct. Computes a cache key before every `COPY`/`RUN` and prints `[CACHE HIT]` or `[CACHE MISS]`. Any miss cascades all steps below it.
3. **A container runtime** — assembles the image filesystem from layers and isolates a process into that root using `chroot`. The same isolation is used for `RUN` during build and `docksmith run`.

All state lives in `~/.docksmith/` — no daemon, no background process.

---

## Prerequisites

- **Linux only** (Ubuntu recommended). macOS/Windows must use WSL2 or a Linux VM.
- Python 3.8+
- pip3
- sudo access (required for `chroot` isolation)
- wget (for one-time base image download)

> ⚠️ Do NOT install or use Docker. Docksmith implements container isolation directly using OS primitives.

---

## Project Structure

```
docksmith/
├── docksmith/
│   ├── __init__.py
│   ├── cli.py          # Entry point for all commands
│   ├── builder.py      # Build engine: parses Docksmithfile, manages layers and cache
│   ├── cache.py        # Cache key computation and index
│   ├── image.py        # Image manifest read/write
│   ├── parser.py       # Docksmithfile parser
│   └── runtime.py      # Container runtime using chroot
├── sampleapp/
│   ├── Docksmithfile   # Uses all 6 instructions
│   └── app.sh          # Sample app script
├── import_base.py      # One-time base image importer
├── setup.py
└── README.md
```

---

## One-Time Setup

### 1. Create state directories
```bash
mkdir -p ~/.docksmith/images ~/.docksmith/layers ~/.docksmith/cache
```

### 2. Install docksmith
```bash
pip3 install -e . --break-system-packages
export PATH=$PATH:~/.local/bin
echo 'export PATH=$PATH:~/.local/bin' >> ~/.bashrc
```

### 3. Download the base image (only internet access required)
```bash
wget https://dl-cdn.alpinelinux.org/alpine/v3.18/releases/x86_64/alpine-minirootfs-3.18.0-x86_64.tar.gz -O ~/alpine.tar.gz
```

### 4. Import the base image into local store
```bash
python3 import_base.py
```

After this, everything works fully offline.

---

## CLI Reference

```bash
docksmith build -t <name:tag> <context>    # Build image from Docksmithfile
docksmith build -t <name:tag> <context> --no-cache  # Build skipping cache
docksmith images                            # List all images
docksmith run <name:tag>                    # Run container
docksmith run -e KEY=VALUE <name:tag>       # Run with env override
docksmith rmi <name:tag>                    # Delete image and its layers
```

---

## Demo

### Cold build — all steps show [CACHE MISS]
```bash
docksmith build -t myapp:latest sampleapp/
```

### Warm build — all steps show [CACHE HIT]
```bash
docksmith build -t myapp:latest sampleapp/
```

### Partial cache invalidation — edit a file and rebuild
```bash
echo "# changed" >> sampleapp/app.sh
docksmith build -t myapp:latest sampleapp/
# COPY step and below → [CACHE MISS], steps above → [CACHE HIT]
```

### List images
```bash
docksmith images
```

### Run container
```bash
docksmith run myapp:latest
# Hello from Docksmith!
# Container is running successfully.
# Container exited with code 0
```

### Run with environment variable override
```bash
docksmith run -e GREETING=Heyyyy myapp:latest
# Heyyyy from Docksmith!
```

### Isolation test (pass/fail)
```bash
docksmith run myapp:latest "/bin/sh -c 'echo secret > /test_isolation.txt'"
ls /test_isolation.txt
# ls: cannot access '/test_isolation.txt': No such file or directory  ✅
```

### Delete image
```bash
docksmith rmi myapp:latest
```

> ⚠️ After `rmi`, re-run `python3 import_base.py` before building again — `rmi` removes all layer files including the base image layer.

---

## State Directory Layout

```
~/.docksmith/
├── images/    # JSON manifest per image
├── layers/    # Content-addressed tar files named by sha256 digest
└── cache/     # index.json mapping cache keys to layer digests
```

---

## Constraints

- No network access during build or run
- No Docker, runc, or containerd used anywhere
- Process isolation via `sudo chroot`
- Builds are byte-for-byte reproducible: tar entries sorted, timestamps zeroed
- Layers are immutable once written

---

## License

MIT

import json
import re

VALID_INSTRUCTIONS = {"FROM", "COPY", "RUN", "WORKDIR", "ENV", "CMD"}

def parse_docksmithfile(filepath):
    instructions = []
    with open(filepath, "r") as f:
        lines = f.readlines()

    for i, line in enumerate(lines, start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split(None, 1)
        instruction = parts[0].upper()

        if instruction not in VALID_INSTRUCTIONS:
            raise ValueError(f"Unknown instruction '{instruction}' at line {i}")

        argument = parts[1] if len(parts) > 1 else ""

        if instruction == "CMD":
            try:
                argument = json.loads(argument)
            except json.JSONDecodeError:
                raise ValueError(f"CMD argument must be a JSON array at line {i}")

        instructions.append((instruction, argument, i))

    return instructions

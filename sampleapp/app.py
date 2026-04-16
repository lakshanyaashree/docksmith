import os

greeting = os.environ.get("GREETING", "Hello")
name = os.environ.get("APP_NAME", "Docksmith")

print(f"{greeting} from {name}!")
print("Container is running successfully.")

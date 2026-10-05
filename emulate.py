import subprocess

def tap(x, y):
    subprocess.run(["adb", "shell", "input", "tap", str(x), str(y)], check=True)

def double_tap(x, y):
    tap(x, y)
    tap(x, y)

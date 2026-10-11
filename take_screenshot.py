import subprocess

DEVICE_DIR = "/sdcard/tmp"
FILENAME = "TEST_SCREEN.png"

LOCAL_DIR = "img/tmp"

subprocess.run(["adb", "shell", "mkdir", "-p", DEVICE_DIR], check=True)
subprocess.run(
    ["adb", "shell", "screencap", "-p", f"{DEVICE_DIR}/{FILENAME}"], check=True
)

subprocess.run(["mkdir", "-p", LOCAL_DIR], check=True)
subprocess.run(["adb", "pull", f"{DEVICE_DIR}/{FILENAME}", f"{LOCAL_DIR}/"], check=True)


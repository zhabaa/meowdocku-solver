import subprocess


subprocess.run(["adb", "shell", "mkdir", "-p",
                "/sdcard/tmp"], check=True)
subprocess.run(["adb", "shell", "screencap", "-p", 
                "/sdcard/tmp/TEST_SCREEN.png"], check=True)

import os
import subprocess

def _kill_process_on_port(port: int):
    try:
        if os.name == "nt":
            result = subprocess.check_output(
                f"netstat -ano | findstr :{port}", shell=True
            ).decode()
            for line in result.strip().split("\n"):
                parts = line.strip().split()
                if len(parts) >= 5 and parts[1].endswith(f":{port}"):
                    pid = parts[-1]
                    if pid and pid != "0":
                        subprocess.call(
                            f"taskkill /F /PID {pid}",
                            shell=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
    except Exception:
        pass

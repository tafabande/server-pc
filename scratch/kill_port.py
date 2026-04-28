import os
import subprocess

def kill_port(port):
    try:
        if os.name == 'nt':
            result = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True).decode()
            for line in result.strip().split('\n'):
                parts = line.strip().split()
                if len(parts) >= 5 and parts[1].endswith(f":{port}"):
                    pid = parts[-1]
                    if pid and pid != "0":
                        print(f"Killing PID {pid} on port {port}")
                        subprocess.call(f'taskkill /F /PID {pid}', shell=True)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    kill_port(8000)

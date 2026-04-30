import os
import sys
import time
import threading
import multiprocessing
import psutil
import uvicorn
import customtkinter as ctk
from PIL import Image

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

def run_fastapi():
    """Entry point for the FastAPI background process."""
    try:
        # Load config inside the process
        from config import HOST, PORT
        from core.utils import _kill_process_on_port
        _kill_process_on_port(PORT)
        uvicorn.run("core.main:app", host=HOST, port=PORT, log_level="error", access_log=False)
    except Exception as e:
        print(f"Server Error: {e}")

class ServerManager(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("StreamDrop — Media Hub Control Panel")
        self.geometry("600x450")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.server_process = None
        self.is_running = False

        # ── Layout ──────────────────────────────────────
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header
        self.header = ctk.CTkLabel(self, text="StreamDrop Enterprise", font=("Inter", 24, "bold"))
        self.header.grid(row=0, column=0, pady=(20, 10))

        self.status_indicator = ctk.CTkLabel(self, text="● Server Offline", text_color="#ff5555", font=("Inter", 14))
        self.status_indicator.grid(row=1, column=0, pady=(0, 20))

        # Main Control Card
        self.card = ctk.CTkFrame(self, corner_radius=15)
        self.card.grid(row=2, column=0, padx=40, pady=20, sticky="nsew")
        self.card.grid_columnconfigure(0, weight=1)

        self.btn_toggle = ctk.CTkButton(self.card, text="Start Server", command=self.toggle_server, height=50, font=("Inter", 16, "bold"))
        self.btn_toggle.grid(row=0, column=0, padx=20, pady=30)

        # Monitoring Section
        self.mon_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.mon_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.mon_frame.grid_columnconfigure(1, weight=1)

        # CPU
        ctk.CTkLabel(self.mon_frame, text="CPU Usage", font=("Inter", 12)).grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.cpu_bar = ctk.CTkProgressBar(self.mon_frame)
        self.cpu_bar.grid(row=0, column=1, sticky="ew")
        self.cpu_bar.set(0)
        self.cpu_label = ctk.CTkLabel(self.mon_frame, text="0%", font=("Inter", 12))
        self.cpu_label.grid(row=0, column=2, padx=(10, 0))

        # RAM
        ctk.CTkLabel(self.mon_frame, text="RAM Usage", font=("Inter", 12)).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=10)
        self.ram_bar = ctk.CTkProgressBar(self.mon_frame)
        self.ram_bar.grid(row=1, column=1, sticky="ew", pady=10)
        self.ram_bar.set(0)
        self.ram_label = ctk.CTkLabel(self.mon_frame, text="0%", font=("Inter", 12))
        self.ram_label.grid(row=1, column=2, padx=(10, 0))

        # Footer
        self.footer = ctk.CTkLabel(self, text="LAN Hub active on port 8000", font=("Inter", 10), text_color="gray")
        self.footer.grid(row=3, column=0, pady=10)

        # Start monitoring loop
        self.update_stats()

    def toggle_server(self):
        if not self.is_running:
            self.start_server()
        else:
            self.stop_server()

    def start_server(self):
        self.server_process = multiprocessing.Process(target=run_fastapi, daemon=True)
        self.server_process.start()
        self.is_running = True
        self.btn_toggle.configure(text="Stop Server", fg_color="#ff5555", hover_color="#cc4444")
        self.status_indicator.configure(text="● Server Online", text_color="#50fa7b")
        self.footer.configure(text=f"Server running at http://0.0.0.0:8000")

    def stop_server(self):
        if self.server_process:
            try:
                parent = psutil.Process(self.server_process.pid)
                for child in parent.children(recursive=True):
                    child.terminate()
                parent.terminate()
                gone, alive = psutil.wait_procs(parent.children(recursive=True) + [parent], timeout=3)
                for p in alive:
                    p.kill()
            except psutil.NoSuchProcess:
                pass
            self.server_process.join()
            self.server_process = None
        self.is_running = False
        self.btn_toggle.configure(text="Start Server", fg_color=["#3B8ED0", "#1F6AA5"], hover_color=["#32769E", "#144870"])
        self.status_indicator.configure(text="● Server Offline", text_color="#ff5555")
        self.footer.configure(text="Server Stopped")

    def update_stats(self):
        """Update hardware monitoring bars every second."""
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent

        self.cpu_bar.set(cpu / 100)
        self.cpu_label.configure(text=f"{int(cpu)}%")

        self.ram_bar.set(ram / 100)
        self.ram_label.configure(text=f"{int(ram)}%")

        self.after(1000, self.update_stats)

if __name__ == '__main__':
    # Critical for PyInstaller compatibility on Windows
    multiprocessing.freeze_support()
    app = ServerManager()
    app.mainloop()

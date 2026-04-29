@echo off
set PYTHON_EXE=C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\python.exe

title StreamDrop Builder
echo +--------------------------------------+
echo :        Building StreamDrop           :
echo +--------------------------------------+
echo.
echo [*] Installing requirements...
"%PYTHON_EXE%" -m pip install pyinstaller
echo [*] Building professional directory package...
"%PYTHON_EXE%" -m pyinstaller --noconfirm --onedir --windowed --noconsole --add-data "static;static" --name "MediaHub" server_manager.py
echo.
echo [*] Build Complete! 
echo [*] You can find the MediaHub/ directory in the 'dist' folder.
echo [*] IMPORTANT: Ensure you copy the .env file into 'dist/MediaHub/' before distribution.
pause

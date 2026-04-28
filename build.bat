@echo off
set PYTHON_EXE=C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\python.exe

title StreamDrop Builder
echo +--------------------------------------+
echo :        Building StreamDrop           :
echo +--------------------------------------+
echo.
echo [*] Installing requirements...
"%PYTHON_EXE%" -m pip install pyinstaller
echo [*] Building single-file executable...
"%PYTHON_EXE%" -m pyinstaller --noconfirm --onefile --add-data "static;static" --name "StreamDrop" main.py
echo.
echo [*] Build Complete! 
echo [*] You can find StreamDrop.exe in the 'dist' folder.
echo [*] Copy StreamDrop.exe to any folder you want to host and run it!
pause

; MediaHub — Inno Setup Script
; This script generates a professional Setup Wizard (MediaHub_Install.exe)
; It packs the entire dist/MediaHub/ directory into a single installer.

[Setup]
AppName=MediaHub
AppVersion=4.0.0
DefaultDirName={autopf}\MediaHub
DefaultGroupName=MediaHub
OutputDir=.
OutputBaseFilename=MediaHub_Install
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin

[Files]
; Copy all files from the PyInstaller output directory
Source: "dist\MediaHub\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

; Include the .env file if it exists in the root (manual step recommended)
Source: ".env"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\MediaHub"; Filename: "{app}\MediaHub.exe"
Name: "{autodesktop}\MediaHub"; Filename: "{app}\MediaHub.exe"

[Run]
Filename: "{app}\MediaHub.exe"; Description: "Launch MediaHub"; Flags: postinstall nowait

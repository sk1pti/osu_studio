; Установщик osu! Studio для Inno Setup 6 (https://jrsoftware.org/isinfo.php)
; Сборка: ISCC /DAppVersion=0.3.0 installer\osu_studio.iss   (или build_installer.bat)

#ifndef AppVersion
  #define AppVersion "0.3.0"
#endif

[Setup]
AppId={{6F1C2A7E-4B0D-4C8E-9A51-0D3B7E2F9C11}
AppName=osu! Studio PRO
AppVersion={#AppVersion}
AppPublisher=osu Studio
DefaultDirName={autopf}\osu Studio
DefaultGroupName=osu! Studio
OutputDir=..\dist\installer
OutputBaseFilename=osu_studio_setup_{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayIcon={app}\osu_studio.exe
; Программа хранит данные в %APPDATA%, поэтому при удалении они не трогаются
; (пользователь сам решает, удалять ли папку).

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать значок на рабочем столе"; GroupDescription: "Дополнительно:"

[Files]
Source: "..\dist\osu_studio\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\osu! Studio PRO"; Filename: "{app}\osu_studio.exe"
Name: "{group}\Удалить osu! Studio"; Filename: "{uninstallexe}"
Name: "{autodesktop}\osu! Studio PRO"; Filename: "{app}\osu_studio.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\osu_studio.exe"; Description: "Запустить osu! Studio PRO"; Flags: nowait postinstall skipifsilent

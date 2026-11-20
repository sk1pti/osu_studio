@echo off
REM Сборка папки dist\osu_studio\ (и установщика, если установлен Inno Setup 6).
chcp 65001 >nul
python -m venv .venv || goto :error
call .venv\Scripts\activate || goto :error
python -m pip install --upgrade pip || goto :error
python -m pip install -r requirements.txt pyinstaller || goto :error
python -m PyInstaller --noconfirm --clean build_exe.spec || goto :error

set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
  %ISCC% /DAppVersion=0.3.0 installer\osu_studio.iss || goto :error
  echo Установщик: dist\installer\osu_studio_setup_0.3.0.exe
) else (
  echo Inno Setup 6 не найден — установщик не собран, готова папка dist\osu_studio\
)
echo Готово.
pause
exit /b 0
:error
echo Сборка не удалась. Смотри сообщения выше.
pause
exit /b 1

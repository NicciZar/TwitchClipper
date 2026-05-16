@echo off
setlocal

echo Building TwitchClipper...

where pyinstaller >nul 2>&1
if %ERRORLEVEL% EQU 0 (
	pyinstaller --onefile --noconsole --name TwitchClipper --icon assets\twitchclipper.ico main.py
) else (
	echo pyinstaller was not found on PATH. Trying Python module invocation...
	py -m PyInstaller --onefile --noconsole --name TwitchClipper --icon assets\twitchclipper.ico main.py
	if %ERRORLEVEL% NEQ 0 (
		python -m PyInstaller --onefile --noconsole --name TwitchClipper --icon assets\twitchclipper.ico main.py
	)
)

if %ERRORLEVEL% NEQ 0 (
	echo.
	echo Build failed.
	echo Install PyInstaller with: py -m pip install pyinstaller
	exit /b 1
)

echo.
echo Done. Executable is in the dist\ folder.

endlocal

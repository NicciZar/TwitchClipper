@echo off
setlocal

echo Building TwitchClipper...

if "%APP_VERSION%"=="" set "APP_VERSION=0.0.0-dev"
if "%APP_BUILD_DATE%"=="" set "APP_BUILD_DATE="
if "%APP_REPO_URL%"=="" set "APP_REPO_URL=https://github.com/NicciZar/TwitchClipper"

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
	py -3 scripts\generate_version_files.py --version "%APP_VERSION%" --build-date "%APP_BUILD_DATE%" --repo-url "%APP_REPO_URL%" --out-version-py "app_version.py" --out-pyinstaller "build\version_info.txt"
) else (
	python scripts\generate_version_files.py --version "%APP_VERSION%" --build-date "%APP_BUILD_DATE%" --repo-url "%APP_REPO_URL%" --out-version-py "app_version.py" --out-pyinstaller "build\version_info.txt"
)

if %ERRORLEVEL% NEQ 0 (
	echo.
	echo Failed to generate version metadata.
	exit /b 1
)

where pyinstaller >nul 2>&1
if %ERRORLEVEL% EQU 0 (
	pyinstaller --onefile --noconsole --name TwitchClipper --icon assets\twitchclipper.ico --version-file build\version_info.txt main.py
) else (
	echo pyinstaller was not found on PATH. Trying Python module invocation...
	py -m PyInstaller --onefile --noconsole --name TwitchClipper --icon assets\twitchclipper.ico --version-file build\version_info.txt main.py
	if %ERRORLEVEL% NEQ 0 (
		python -m PyInstaller --onefile --noconsole --name TwitchClipper --icon assets\twitchclipper.ico --version-file build\version_info.txt main.py
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

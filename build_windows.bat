@echo off
setlocal
pushd "%~dp0"
echo Killing any running Nomminator.exe processes...
taskkill /f /im Nomminator.exe 2>nul
echo Cleaning previous build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo Building Windows executable with PyInstaller...
python -m PyInstaller Nomminator.spec
if errorlevel 1 (
    echo.
    echo PyInstaller build failed.
    popd
    exit /b 1
)
echo.
echo Build complete. Output: dist\Nomminator.exe
popd
endlocal

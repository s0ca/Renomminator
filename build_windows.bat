@echo off
setlocal
pushd "%~dp0"
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

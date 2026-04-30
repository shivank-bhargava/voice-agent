@echo off
REM Voice Agent Windows Installer Script
REM This script creates a Windows installer using Inno Setup (if available)
REM or creates a portable distribution package

echo ========================================
echo Voice Agent Installer Creator
echo ========================================
echo.

REM Check if Inno Setup is available
where iscc >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Inno Setup found. Creating installer...
    iscc voice_agent_setup.iss
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo ========================================
        echo Installer created successfully!
        echo Output: Output\VoiceAgentSetup.exe
        echo ========================================
    ) else (
        echo Failed to create installer
    )
) else (
    echo Inno Setup not found.
    echo Creating portable distribution instead...
    echo.
    
    REM Create portable distribution
    if not exist "dist\VoiceAgent" (
        echo ERROR: Please run build.py first to create the executable
        echo Run: python build.py
        pause
        exit /b 1
    )
    
    REM Create zip file
    echo Creating portable package...
    powershell -Command "Compress-Archive -Path 'dist\VoiceAgent\*' -DestinationPath 'VoiceAgent-Portable.zip' -Force"
    
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo ========================================
        echo Portable package created successfully!
        echo Output: VoiceAgent-Portable.zip
        echo ========================================
        echo.
        echo Users can extract and run run.bat
    ) else (
        echo Failed to create portable package
    )
)

echo.
pause

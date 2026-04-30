; Voice Agent Professional Installer Script
; Requires NSIS from: https://nsis.sourceforge.io/Download

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "WinVer.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"

; General
Name "Voice Agent"
OutFile "VoiceAgent-Setup.exe"
InstallDir "$PROGRAMFILES64\VoiceAgent"
InstallDirRegKey HKLM "Software\VoiceAgent" "Install_Dir"
RequestExecutionLevel admin
ShowInstDetails show
ShowUninstDetails show

; Version information
VIProductVersion "1.0.0.0"
VIAddVersionKey "ProductName" "Voice Agent"
VIAddVersionKey "CompanyName" "Voice Agent"
VIAddVersionKey "FileDescription" "Voice Agent - Local Voice-Powered Lists"
VIAddVersionKey "FileVersion" "1.0.0.0"
VIAddVersionKey "ProductVersion" "1.0.0.0"
VIAddVersionKey "LegalCopyright" "2024"

; Variables
Var OllamaInstalled
Var OllamaPath
Var VoskModelDownloaded
Var Dialog
Var Label
Var ProgressBar
Var InstallButton
Var CancelButton
Var DownloadProgress

; Interface Settings
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\run.bat"
!define MUI_FINISHPAGE_RUN_TEXT "Launch Voice Agent"
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\README.txt"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "View README"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; Languages
!insertmacro MUI_LANGUAGE "English"

; Sections
Section "Voice Agent Core" SecCore
  SectionIn RO
  
  SetOutPath $INSTDIR
  
  ; Copy Voice Agent files
  File /r "dist\VoiceAgent\*.*"
  
  ; Create uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"
  
  ; Write registry keys
  WriteRegStr HKLM "Software\VoiceAgent" "Install_Dir" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoiceAgent" "DisplayName" "Voice Agent"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoiceAgent" "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoiceAgent" "Publisher" "Voice Agent"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoiceAgent" "DisplayVersion" "1.0.0"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoiceAgent" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoiceAgent" "NoRepair" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoiceAgent" "EstimatedSize" 500000
  
  ; Create start menu shortcuts
  CreateDirectory "$SMPROGRAMS\Voice Agent"
  CreateShortCut "$SMPROGRAMS\Voice Agent\Voice Agent.lnk" "$INSTDIR\VoiceAgent.exe" "" "$INSTDIR\VoiceAgent.exe" 0
  CreateShortCut "$SMPROGRAMS\Voice Agent\Uninstall.lnk" "$INSTDIR\uninstall.exe"
  
  ; Create desktop shortcut
  CreateShortCut "$DESKTOP\Voice Agent.lnk" "$INSTDIR\VoiceAgent.exe" "" "$INSTDIR\VoiceAgent.exe" 0
SectionEnd

Section "Ollama (Required for AI)" SecOllama
  SectionIn RO
  
  ; Check if Ollama is already installed
  IfFileExists "$PROGRAMFILES64\Ollama\ollama.exe" 0 CheckLocalAppData
    StrCpy $OllamaInstalled "1"
    StrCpy $OllamPath "$PROGRAMFILES64\Ollama"
    DetailPrint "Ollama already installed at: $OllamaPath"
    Goto OllamaDone
  
  CheckLocalAppData:
  IfFileExists "$LOCALAPPDATA\Programs\Ollama\ollama.exe" 0 DownloadOllama
    StrCpy $OllamaInstalled "1"
    StrCpy $OllamPath "$LOCALAPPDATA\Programs\Ollama"
    DetailPrint "Ollama already installed at: $OllamaPath"
    Goto OllamaDone
  
  DownloadOllama:
  ; Download and install Ollama
  DetailPrint "Downloading Ollama installer..."
  InitPluginsDir
  inetc::get /SILENT "https://ollama.com/download/OllamaSetup.exe" "$PLUGINSDIR\OllamaSetup.exe" /END
  Pop $0
  ${If} $0 == "OK"
    DetailPrint "Installing Ollama (this may take a minute)..."
    ExecWait '"$PLUGINSDIR\OllamaSetup.exe" /S' $0
    ${If} $0 == 0
      StrCpy $OllamaInstalled "1"
      
      ; Find Ollama installation path
      Sleep 3000  ; Wait for installation to complete
      IfFileExists "$PROGRAMFILES64\Ollama\ollama.exe" 0 CheckLocalAfterInstall
        StrCpy $OllamPath "$PROGRAMFILES64\Ollama"
        Goto OllamaFound
      CheckLocalAfterInstall:
      IfFileExists "$LOCALAPPDATA\Programs\Ollama\ollama.exe" 0 OllamaNotFound
        StrCpy $OllamPath "$LOCALAPPDATA\Programs\Ollama"
        Goto OllamaFound
      
      OllamaFound:
      DetailPrint "Ollama installed successfully to: $OllamPath"
    ${Else}
      DetailPrint "Ollama installation returned error code: $0"
      MessageBox MB_OK|MB_ICONEXCLAMATION "Ollama installation failed. Please install it manually from https://ollama.com/download"
    ${EndIf}
  ${Else}
    DetailPrint "Failed to download Ollama: $0"
    MessageBox MB_OK|MB_ICONEXCLAMATION "Failed to download Ollama automatically. Please install it manually from https://ollama.com/download"
  ${EndIf}
  
  Goto OllamaDone
  
  OllamaNotFound:
  DetailPrint "Could not find Ollama after installation"
  MessageBox MB_OK|MB_ICONEXCLAMATION "Could not locate Ollama installation. Please install it manually from https://ollama.com/download"
  
  OllamaDone:
SectionEnd

Section "Vosk Speech Model (Required)" SecVosk
  SectionIn RO
  
  ; Check if Vosk model already exists
  IfFileExists "$INSTDIR\vosk-model-en-us-0.22\*" VoskDone
  
  ; Download Vosk model
  DetailPrint "Downloading Vosk speech recognition model (approximately 1.8GB)..."
  InitPluginsDir
  inetc::get /SILENT "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip" "$PLUGINSDIR\vosk-model.zip" /END
  Pop $0
  ${If} $0 == "OK"
    DetailPrint "Extracting Vosk model..."
    nsisunz::Unzip "$PLUGINSDIR\vosk-model.zip" "$INSTDIR"
    Pop $0
    ${If} $0 == "success"
      DetailPrint "Vosk model extracted successfully"
      StrCpy $VoskModelDownloaded "1"
    ${Else}
      DetailPrint "Failed to extract Vosk model: $0"
      MessageBox MB_OK|MB_ICONEXCLAMATION "Failed to extract Vosk model. Please download vosk-model-en-us-0.22.zip from https://alphacephei.com/vosk/models and extract to the installation directory."
    ${EndIf}
  ${Else}
    DetailPrint "Failed to download Vosk model: $0"
    MessageBox MB_OK|MB_ICONEXCLAMATION "Failed to download Vosk model automatically. Please download vosk-model-en-us-0.22.zip from https://alphacephei.com/vosk/models and extract to the installation directory."
  ${EndIf}
  
  VoskDone:
SectionEnd

Section "Ollama AI Model (llama3.1:8b)" SecOllamaModel
  SectionIn RO
  
  ${If} $OllamaInstalled == "1"
    ; Pull the Ollama model after installation
    DetailPrint "Pulling Ollama AI model llama3.1:8b (this may take several minutes on first run)..."
    DetailPrint "The model will be downloaded automatically when you first use Voice Agent."
    
    ; Create a batch script to pull the model silently
    FileOpen $0 "$INSTDIR\pull_model.bat" w
    FileWrite $0 "@echo off$\r$\n"
    FileWrite $0 "echo Pulling Ollama model llama3.1:8b...$\r$\n"
    FileWrite $0 "echo This will take several minutes on first run...$\r$\n"
    FileWrite $0 "echo.$\r$\n"
    FileWrite $0 "REM Try to find ollama in common locations$\r$\n"
    FileWrite $0 "if exist $\\"$PROGRAMFILES64\Ollama\ollama.exe\\" ($\r$\n"
    FileWrite $0 "    cd /d $\\"$PROGRAMFILES64\Ollama\\"\r$\n"
    FileWrite $0 ") else if exist $\\"$LOCALAPPDATA\Programs\Ollama\ollama.exe\\" ($\r$\n"
    FileWrite $0 "    cd /d $\\"$LOCALAPPDATA\Programs\Ollama\\"\r$\n"
    FileWrite $0 ") else ($\r$\n"
    FileWrite $0 "    echo Ollama not found. Please install from https://ollama.com/download$\r$\n"
    FileWrite $0 "    pause$\r$\n"
    FileWrite $0 "    exit /b 1$\r$\n"
    FileWrite $0 ")$\r$\n"
    FileWrite $0 "echo.$\r$\n"
    FileWrite $0 "ollama pull llama3.1:8b$\r$\n"
    FileWrite $0 "if %ERRORLEVEL% EQU 0 ($\r$\n"
    FileWrite $0 "    echo.$\r$\n"
    FileWrite $0 "    echo Model pulled successfully!$\r$\n"
    FileWrite $0 "    echo You can now use Voice Agent with full AI features.$\r$\n"
    FileWrite $0 ") else ($\r$\n"
    FileWrite $0 "    echo.$\r$\n"
    FileWrite $0 "    echo Failed to pull model. Please run manually: ollama pull llama3.1:8b$\r$\n"
    FileWrite $0 ")$\r$\n"
    FileWrite $0 "echo.$\r$\n"
    FileWrite $0 "pause$\r$\n"
    FileClose $0
    
    ; Execute the model pull
    ExecWait '"$INSTDIR\pull_model.bat"' $0
    
    ; Don't delete the batch file - user might need it later
    ${If} $0 != 0
      DetailPrint "Model pull returned error code: $0 (may need to run manually)"
    ${EndIf}
  ${Else}
    DetailPrint "Skipping AI model pull - Ollama not installed"
  ${EndIf}
SectionEnd

Section "Start Ollama Service" SecStartOllama
  SectionIn RO
  
  ${If} $OllamaInstalled == "1"
    ; Start Ollama service in background
    DetailPrint "Starting Ollama service..."
    ExecShell "" "$OllamPath\ollama.exe" "serve" SW_HIDE
    Sleep 2000
    DetailPrint "Ollama service started"
  ${Else}
    DetailPrint "Skipping Ollama service start - Ollama not installed"
  ${EndIf}
SectionEnd

; Functions
Function .onInit
  ; Check Windows version
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_OK "Voice Agent requires Windows 10 or later."
    Abort
  ${EndIf}
  
  ; Check for 64-bit
  ${IfNot} ${IsNativeAMD64}
    MessageBox MB_OK "Voice Agent requires a 64-bit version of Windows."
    Abort
  ${EndIf}
  
  StrCpy $OllamaInstalled "0"
  StrCpy $VoskModelDownloaded "0"
FunctionEnd

; Uninstaller Section
Section "Uninstall"
  ; Stop Ollama service if running
  DetailPrint "Stopping Ollama service..."
  ExecWait 'taskkill /F /IM ollama.exe'
  
  ; Stop Voice Agent if running
  DetailPrint "Stopping Voice Agent..."
  ExecWait 'taskkill /F /IM VoiceAgent.exe'
  
  ; Remove files and directories
  DetailPrint "Removing application files..."
  RMDir /r "$INSTDIR"
  
  ; Remove shortcuts
  Delete "$DESKTOP\Voice Agent.lnk"
  Delete "$SMPROGRAMS\Voice Agent\*.*"
  RMDir "$SMPROGRAMS\Voice Agent"
  
  ; Remove registry keys
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\VoiceAgent"
  DeleteRegKey HKLM "Software\VoiceAgent"
  
  ; Remove user data directory (optional - comment out if you want to preserve data)
  ; RMDir /r "$APPDATA\VoiceAgent"
  
  DetailPrint "Uninstallation complete"
SectionEnd

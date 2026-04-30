; Voice Agent Setup Script for Inno Setup
; Download Inno Setup from: https://jrsoftware.org/isdl.php

[Setup]
AppName=Voice Agent
AppVersion=1.0.0
DefaultDirName={commonpf}\VoiceAgent
DefaultGroupName=Voice Agent
OutputBaseFilename=VoiceAgentSetup
Compression=lzma2
SolidCompression=yes
; Require admin privileges
PrivilegesRequired=admin
; Architectures
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Files]
; Executable and dependencies
Source: "dist\VoiceAgent\VoiceAgent.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\VoiceAgent\*.dll"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
Source: "dist\VoiceAgent\*.pyd"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

; Static files
Source: "dist\VoiceAgent\templates\*"; DestDir: "{app}\templates"; Flags: ignoreversion recursesubdirs
Source: "dist\VoiceAgent\static\*"; DestDir: "{app}\static"; Flags: ignoreversion recursesubdirs

; Vosk models (if present)
Source: "dist\VoiceAgent\vosk-model-*\*"; DestDir: "{app}\vosk-model-*"; Flags: ignoreversion recursesubdirs createallsubdirs

; Documentation
Source: "dist\VoiceAgent\README.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Voice Agent"; Filename: "{app}\VoiceAgent.exe"
Name: "{group}\Uninstall Voice Agent"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Voice Agent"; Filename: "{app}\VoiceAgent.exe"

[Run]
Filename: "{app}\VoiceAgent.exe"; Description: "Launch Voice Agent"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\*"

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  
  // Check for Ollama installation
  if not FileExists(ExpandConstant('{pf}\Ollama\ollama.exe')) and
     not FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe')) then
  begin
    if MsgBox('Voice Agent requires Ollama to be installed for AI features.' + #13#10 +
              'Would you like to download Ollama now?', mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open', 'https://ollama.com/download', '', '', SW_SHOW, ewNoWait, ResultCode);
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Create data directory
    if not DirExists(ExpandConstant('{userappdata}\VoiceAgent')) then
      CreateDir(ExpandConstant('{userappdata}\VoiceAgent'));
  end;
end;

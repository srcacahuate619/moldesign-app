; D:\moldesign-build\scripts\moldesign_setup.iss
; Inno Setup Compiler Script for MolDesign AI (Full Offline Setup)

[Setup]
AppId={{E1D3CA5D-079D-40F4-BF19-1E32A04BC48D}}
AppName=MolDesign AI
AppVersion=1.0.0
AppPublisher=MolDesign Team
AppPublisherURL=https://moldesign.ai/
DefaultDirName={commonpf}\MolDesign AI
DefaultGroupName=MolDesign AI
AllowNoIcons=yes
OutputDir=..\frontend\src-tauri\target\release\bundle\innosetup
OutputBaseFilename=MolDesign_AI_Full_Setup
Compression=lzma2/normal
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
DisableWelcomePage=no
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Compiled Tauri executable
Source: "D:\moldesign-build\frontend\src-tauri\target\release\moldesign.exe"; DestDir: "{app}"; Flags: ignoreversion

; Resources folder containing python-embed, backend, rescoring, tools, data (including full models + target library PDBs)
Source: "D:\moldesign-build\frontend\src-tauri\resources\*"; DestDir: "{app}\resources"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\MolDesign AI"; Filename: "{app}\moldesign.exe"
Name: "{autodesktop}\MolDesign AI"; Filename: "{app}\moldesign.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\moldesign.exe"; Description: "{cm:LaunchProgram,MolDesign AI}"; Flags: nowait postinstall skipifsilent

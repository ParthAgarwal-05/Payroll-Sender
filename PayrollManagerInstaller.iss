#define MyAppName "Payroll Manager"
#define MyAppVersion "1.0"
#define MyAppPublisher "Your Company"
#define MyAppExeName "Payroll Manager.exe"

[Setup]
AppId={{8E89D5A5-1E1A-4D66-9D4C-5F6F89C5B7A1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}

OutputDir=Output
OutputBaseFilename=PayrollManagerSetup_v1.0

Compression=lzma2
SolidCompression=yes
WizardStyle=modern

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

PrivilegesRequired=admin

DisableProgramGroupPage=yes

; SetupIconFile=
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]

; Change this path if your dist folder is elsewhere
Source: "dist\Payroll Manager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]

Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]

Filename: "{app}\{#MyAppExeName}";Description: "Launch Payroll Manager";Flags: nowait postinstall skipifsilent

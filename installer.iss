#define AppName "Actividad 3"
#define AppVersion "1.0.0"
#define AppExe "Actividad3.exe"

[Setup]
AppId={{B6435686-EF32-4053-A761-8062B174F572}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Actividad 3
DefaultDirName={localappdata}\Programs\Actividad 3
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
OutputDir=build\installer
OutputBaseFilename=Actividad3-Setup-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "build\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Iniciar {#AppName}"; Flags: postinstall nowait skipifsilent
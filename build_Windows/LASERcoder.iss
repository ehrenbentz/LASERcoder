; LASERcoder.iss - Inno Setup Script
; Run from build_Windows\ directory
; Expects compiled output in dist_Windows_x64_v#_#_#\LASERcoder.dist\
;
; Version and signing are passed from the command line by the build script:
;   ISCC /DAppVer=1.3.0 /DSignEnabled /Smysign=<signcmd> LASERcoder.iss
;
; If AppVer is not defined, version-specific fields are omitted.
; If SignEnabled is not defined, code signing directives are omitted.

#ifdef AppVer
  #define VerUnderscored StringChange(AppVer, ".", "_")
#endif

[Setup]
AppName=LASERcoder
AppId={{E8F1A3B7-4C2D-4F6E-9A1B-3D5E7F9C2A4B}
#ifdef AppVer
AppVersion={#AppVer}
VersionInfoVersion={#AppVer}
VersionInfoProductVersion={#AppVer}
#endif
AppPublisher=Ehren Bentz
AppPublisherURL=https://github.com/ehrenbentz/LASERcoder
AppSupportURL=https://github.com/ehrenbentz/LASERcoder/issues
DefaultDirName={autopf}\LASERcoder
DefaultGroupName=LASERcoder
#ifdef AppVer
OutputDir=dist_Windows_x64_v{#VerUnderscored}
OutputBaseFilename=LASERcoder_v{#AppVer}_windows_x64_setup
#else
OutputDir=dist_Windows_x64
OutputBaseFilename=LASERcoder_windows_x64_setup
#endif
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
Compression=lzma
SolidCompression=yes
SetupIconFile=..\icons\laser.ico
UninstallDisplayIcon={app}\laser.ico
UninstallDisplayName=LASERcoder
VersionInfoCompany=Ehren Bentz
VersionInfoCopyright=Copyright 2026 Ehren Bentz. Licensed under GNU GPL v3.
VersionInfoDescription=LASERcoder Setup
VersionInfoProductName=LASERcoder
#ifdef SignEnabled
SignTool=mysign
SignedUninstaller=yes
#endif

[Files]
#ifdef AppVer
Source: "dist_Windows_x64_v{#VerUnderscored}\LASERcoder.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#else
Source: "dist_Windows_x64\LASERcoder.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#endif
Source: "..\icons\laser.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\LASERcoder"; Filename: "{app}\LASERcoder.exe"; WorkingDir: "{app}"; IconFilename: "{app}\laser.ico"
Name: "{commondesktop}\LASERcoder"; Filename: "{app}\LASERcoder.exe"; WorkingDir: "{app}"; IconFilename: "{app}\laser.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

; NOTE: Earlier versions added {app} to the user's PATH in a [Code]
; section. That was removed in 1.7.4: a GUI app does not need to be on
; PATH, the installer runs elevated (so HKCU belonged to the elevating
; admin, not necessarily the installing user), and rewriting PATH as
; REG_SZ destroyed REG_EXPAND_SZ entries containing %VARIABLES%.
; Old uninstallers still remove the entry they added.

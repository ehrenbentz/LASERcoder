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
VersionInfoCopyright=Copyright 2025 Ehren Bentz. Licensed under GNU GPL v3.
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

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  Path: string;
  AppPath: string;
begin
  if CurStep = ssPostInstall then
  begin
    AppPath := ExpandConstant('{app}');
    if RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Path) then
    begin
      if Pos(Uppercase(AppPath), Uppercase(Path)) = 0 then
      begin
        if Length(Path) > 0 then
          Path := Path + ';';
        Path := Path + AppPath;
        RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Path);
      end;
    end
    else
    begin
      RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', AppPath);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Path: string;
  AppPath: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppPath := ExpandConstant('{app}');
    if RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Path) then
    begin
      StringChangeEx(Path, ';' + AppPath + ';', ';', True);
      StringChangeEx(Path, ';' + AppPath, '', True);
      StringChangeEx(Path, AppPath + ';', '', True);
      if Path = AppPath then
        Path := '';
      RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Path);
    end;
  end;
end;

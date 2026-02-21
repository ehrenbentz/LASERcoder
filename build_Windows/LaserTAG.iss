; LaserTAG.iss - Inno Setup Script
; Run from build_Windows\ directory
; Expects compiled output in output\LaserTAG.dist\

[Setup]
AppName=LaserTAG
AppVersion=1.2.0
AppPublisher=Ehren Bentz
DefaultDirName={autopf}\LaserTAG
DefaultGroupName=LaserTAG
OutputDir=output
OutputBaseFilename=LaserTAG_v1.2.0_windows_x64_setup
PrivilegesRequired=admin
Compression=lzma
SolidCompression=yes
UninstallDisplayIcon={app}\laser.ico
UninstallDisplayName=LaserTAG

[Files]
Source: "output\LaserTAG.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "laser.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\LaserTAG"; Filename: "{app}\LaserTAG.exe"; WorkingDir: "{app}"; IconFilename: "{app}\laser.ico"
Name: "{commondesktop}\LaserTAG"; Filename: "{app}\LaserTAG.exe"; WorkingDir: "{app}"; IconFilename: "{app}\laser.ico"; Tasks: desktopicon

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

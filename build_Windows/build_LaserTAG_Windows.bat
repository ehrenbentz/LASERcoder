@echo off
REM build_LaserTAG_Windows.bat
REM Run from inside LaserTAG\build_Windows\
REM
REM Directory structure:
REM   LaserTAG\
REM     CodeBase\              Python source files including LaserTAG.py
REM     build_Windows\         This script, libmpv-2.dll, laser.ico, LaserTAG.iss
REM       dist_Windows\        Created by this script
REM         LaserTAG.build\
REM         LaserTAG.dist\       Complete application folder
REM           LaserTAG.exe
REM           libmpv-2.dll
REM         version_info.txt
REM         LaserTAG_v{ver}_windows_x64_setup.exe    Installer
REM         LaserTAG_v{ver}_windows_x64_portable.zip Portable zip
REM
REM Prerequisites:
REM   pip install nuitka PySide6 python-mpv
REM
REM Usage:
REM   cd LaserTAG\build_Windows
REM   build_LaserTAG_Windows.bat

setlocal enabledelayedexpansion

set APP_NAME=LaserTAG
set APP_VERSION=1.3.0
set MAIN_SCRIPT=LaserTAG.py
set CODBASE_DIR=..\CodeBase
set OUTPUT_DIR=dist_Windows

set SETUP_NAME=%APP_NAME%_v%APP_VERSION%_windows_x64_setup.exe
set ZIP_NAME=%APP_NAME%_v%APP_VERSION%_windows_x64_portable.zip

REM Code signing — set these environment variables before running,
REM or leave unset to skip signing:
REM   set LASERTAG_CERT_FILE=C:\path\to\MyCert.pfx
REM   set LASERTAG_CERT_PASS=YourPassword
if defined LASERTAG_CERT_FILE (set CERT_FILE=%LASERTAG_CERT_FILE%) else (set CERT_FILE=)
if defined LASERTAG_CERT_PASS (set CERT_PASS=%LASERTAG_CERT_PASS%) else (set CERT_PASS=)

REM =====================================================================
REM Verify directory structure
REM =====================================================================
if not exist "%CODBASE_DIR%" (
    echo ERROR: CodeBase directory not found at %CODBASE_DIR%
    echo Run this script from inside LaserTAG\build_Windows\
    exit /b 1
)

if not exist "%CODBASE_DIR%\%MAIN_SCRIPT%" (
    echo ERROR: %MAIN_SCRIPT% not found in %CODBASE_DIR%\
    exit /b 1
)

if not exist "libmpv-2.dll" (
    echo ERROR: libmpv-2.dll not found in current directory.
    exit /b 1
)

if not exist "laser.ico" (
    echo ERROR: laser.ico not found in current directory.
    exit /b 1
)

REM =====================================================================
REM Parse version components from APP_VERSION (e.g. 1.3.0)
REM =====================================================================
for /f "tokens=1,2,3 delims=." %%a in ("%APP_VERSION%") do (
    set VER_MAJOR=%%a
    set VER_MINOR=%%b
    set VER_PATCH=%%c
)

REM =====================================================================
REM Prepare output directory
REM =====================================================================
echo Preparing output directory...

if exist "%OUTPUT_DIR%" (
    echo Removing previous output directory...
    rmdir /s /q "%OUTPUT_DIR%"
)
mkdir "%OUTPUT_DIR%"

REM =====================================================================
REM Generate version_info.txt in output directory
REM =====================================================================
echo Generating version_info.txt for v%APP_VERSION%...
(
echo # UTF-8
echo VSVersionInfo(
echo   ffi=FixedFileInfo(
echo     filevers=(%VER_MAJOR%, %VER_MINOR%, %VER_PATCH%^),
echo     prodvers=(%VER_MAJOR%, %VER_MINOR%, %VER_PATCH%^),
echo     mask=0x3f,
echo     flags=0x0,
echo     OS=0x40004,
echo     fileType=0x1,
echo     subtype=0x0,
echo     date=(0, 0^)
echo     ^),
echo   kids=[
echo     StringFileInfo(
echo       [
echo       StringTable(
echo         u'040904b0',
echo         [StringStruct(u'CompanyName', u'Cornell University'^),
echo         StringStruct(u'FileDescription', u'LaserTAG - Lightweight application for scoring ethology recordings and Tracking Animals Gooder'^),
echo         StringStruct(u'FileVersion', u'%APP_VERSION%'^),
echo         StringStruct(u'InternalName', u'LaserTAG'^),
echo         StringStruct(u'LegalCopyright', u'Copyright 2025 Ehren Bentz. Licensed under GNU GPL v3. See https://github.com/ehrenbentz/LaserTAG'^),
echo         StringStruct(u'OriginalFilename', u'LaserTAG.exe'^),
echo         StringStruct(u'ProductName', u'LaserTAG'^),
echo         StringStruct(u'ProductVersion', u'%APP_VERSION%'^)]^)
echo       ]^),
echo     VarFileInfo([VarStruct(u'Translation', [1033, 1200]^)^]^)
echo   ]
echo ^)
) > "%OUTPUT_DIR%\version_info.txt"

REM Copy Python source into output for Nuitka to compile
echo Copying source from %CODBASE_DIR%...
copy "%CODBASE_DIR%\*.py" "%OUTPUT_DIR%\" >nul

REM Copy build resources into output
copy "laser.ico" "%OUTPUT_DIR%\" >nul
copy "libmpv-2.dll" "%OUTPUT_DIR%\" >nul

REM =====================================================================
REM Compile with Nuitka
REM =====================================================================
echo.
echo Compiling with Nuitka...

pushd "%OUTPUT_DIR%"

python -m nuitka ^
    --standalone ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico=laser.ico ^
    --output-filename=%APP_NAME%.exe ^
    --enable-plugin=pyside6 ^
    --nofollow-import-to=PIL ^
    --include-data-files=libmpv-2.dll=libmpv-2.dll ^
    --include-data-files=laser.ico=laser.ico ^
    --windows-file-version=%APP_VERSION% ^
    --windows-product-version=%APP_VERSION% ^
    --windows-company-name="Cornell University" ^
    --windows-product-name=LaserTAG ^
    --windows-file-description="LaserTAG - Lightweight application for scoring ethology recordings and Tracking Animals Gooder" ^
    %MAIN_SCRIPT%

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Nuitka compilation failed.
    popd
    exit /b 1
)

popd

REM =====================================================================
REM Clean up staged source from output
REM =====================================================================
echo.
echo Cleaning up...

del "%OUTPUT_DIR%\*.py" >nul 2>&1
del "%OUTPUT_DIR%\laser.ico" >nul 2>&1
del "%OUTPUT_DIR%\libmpv-2.dll" >nul 2>&1

REM =====================================================================
REM Code signing
REM =====================================================================
echo.
if not defined CERT_FILE (
    echo "Skipping code signing (CERT_FILE not set)"
) else if not defined CERT_PASS (
    echo "Skipping code signing (CERT_PASS not set)"
) else if not exist "%CERT_FILE%" (
    echo "Skipping code signing (certificate not found at %CERT_FILE%)"
) else (
    echo "Signing executable"
    signtool.exe sign /f "%CERT_FILE%" /p %CERT_PASS% /fd sha256 /td sha256 /tr http://timestamp.digicert.com /a "%OUTPUT_DIR%\%APP_NAME%.dist\%APP_NAME%.exe"
    if %errorlevel% neq 0 (
        echo WARNING: Code signing failed. Continuing without signature.
    ) else (
        echo Signature applied successfully.
        signtool.exe verify /v /pa "%OUTPUT_DIR%\%APP_NAME%.dist\%APP_NAME%.exe"
    )
)

REM =====================================================================
REM Create installer with Inno Setup (if available)
REM =====================================================================
echo.
echo Creating installer...

set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
    if exist "LaserTAG.iss" (
        %ISCC% /DAppVer=%APP_VERSION% "LaserTAG.iss"
        if %errorlevel% neq 0 (
            echo WARNING: Inno Setup compilation failed.
        ) else (
            echo Installer created: %OUTPUT_DIR%\%SETUP_NAME%
        )
    ) else (
        echo WARNING: LaserTAG.iss not found. Skipping installer creation.
    )
) else (
    echo Inno Setup not found at %ISCC%. Skipping installer creation.
    echo Install from: https://jrsoftware.org/isinfo.php
)

REM =====================================================================
REM Create portable .zip for release upload
REM =====================================================================
echo.
echo Creating portable zip...

if exist "%OUTPUT_DIR%\%ZIP_NAME%" del "%OUTPUT_DIR%\%ZIP_NAME%"

powershell -NoProfile -Command ^
    "Compress-Archive -Path '%OUTPUT_DIR%\%APP_NAME%.dist\*' -DestinationPath '%OUTPUT_DIR%\%ZIP_NAME%'"

if %errorlevel% neq 0 (
    echo WARNING: Failed to create zip file.
) else (
    echo Zip created: %OUTPUT_DIR%\%ZIP_NAME%
)

REM =====================================================================
REM Summary
REM =====================================================================
echo.
echo ============================================
echo   Build Complete
echo ============================================
echo   Executable: %OUTPUT_DIR%\%APP_NAME%.dist\%APP_NAME%.exe
echo.
if exist "%OUTPUT_DIR%\%SETUP_NAME%" (
    echo   Installer:  %OUTPUT_DIR%\%SETUP_NAME%
    echo.
)
echo   --- Testing ---
echo   %OUTPUT_DIR%\%APP_NAME%.dist\%APP_NAME%.exe
echo.
echo   --- Distributing without installer ---
echo   The %APP_NAME%.dist folder is the complete application.
if exist "%OUTPUT_DIR%\%ZIP_NAME%" (
    echo   Portable zip: %OUTPUT_DIR%\%ZIP_NAME%
)
echo ============================================

endlocal
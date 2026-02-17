@echo off
REM build_LaserTAG_Windows.bat
REM Run from inside LaserTAG\build_Windows\
REM
REM Directory structure:
REM   LaserTAG\
REM     CodeBase\          Python source files including LaserTAG.py
REM     build_Windows\     This script, libmpv-2.dll, laser.ico, LaserTAG.iss
REM       output\          Created by this script
REM         LaserTAG.build\
REM         LaserTAG.dist\   Complete application folder
REM           LaserTAG.exe
REM           libmpv-2.dll
REM         LaserTAGSetup.exe  Installer (if Inno Setup is available)
REM
REM Prerequisites:
REM   pip install nuitka PySide6 python-mpv
REM
REM Usage:
REM   cd LaserTAG\build_Windows
REM   build_LaserTAG_Windows.bat

setlocal enabledelayedexpansion

set APP_NAME=LaserTAG
set MAIN_SCRIPT=LaserTAG.py
set CODBASE_DIR=..\CodeBase
set OUTPUT_DIR=output

REM Code signing (leave empty to skip)
set CERT_FILE=
set CERT_PASS=

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
REM STEP 1: Prepare output directory
REM =====================================================================
echo === Step 1: Preparing output directory ===

if exist "%OUTPUT_DIR%" (
    echo Removing previous output directory...
    rmdir /s /q "%OUTPUT_DIR%"
)
mkdir "%OUTPUT_DIR%"

REM Copy Python source into output for Nuitka to compile
echo Copying source from %CODBASE_DIR%...
copy "%CODBASE_DIR%\*.py" "%OUTPUT_DIR%\" >nul

REM Copy build resources into output
copy "laser.ico" "%OUTPUT_DIR%\" >nul
copy "libmpv-2.dll" "%OUTPUT_DIR%\" >nul

REM =====================================================================
REM STEP 2: Compile with Nuitka
REM =====================================================================
echo.
echo === Step 2: Compiling with Nuitka ===

pushd "%OUTPUT_DIR%"

python -m nuitka ^
    --standalone ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico=laser.ico ^
    --output-filename=%APP_NAME%.exe ^
    --enable-plugin=pyside6 ^
    --include-data-files=libmpv-2.dll=libmpv-2.dll ^
    --include-data-files=laser.ico=laser.ico ^
    --windows-file-version=1.0.0.0 ^
    --windows-product-version=1.0.0.0 ^
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
REM STEP 3: Clean up staged source from output
REM =====================================================================
echo.
echo === Step 3: Cleaning up ===

del "%OUTPUT_DIR%\*.py" >nul 2>&1
del "%OUTPUT_DIR%\laser.ico" >nul 2>&1
del "%OUTPUT_DIR%\libmpv-2.dll" >nul 2>&1

REM =====================================================================
REM STEP 4: Code signing
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
REM STEP 5: Create installer with Inno Setup (if available)
REM =====================================================================
echo.
echo === Step 5: Creating installer ===

set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
    if exist "LaserTAG.iss" (
        %ISCC% "LaserTAG.iss"
        if %errorlevel% neq 0 (
            echo WARNING: Inno Setup compilation failed.
        ) else (
            echo Installer created: %OUTPUT_DIR%\LaserTAGSetup.exe
        )
    ) else (
        echo WARNING: LaserTAG.iss not found. Skipping installer creation.
    )
) else (
    echo Inno Setup not found at %ISCC%. Skipping installer creation.
    echo Install from: https://jrsoftware.org/isinfo.php
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
if exist "%OUTPUT_DIR%\LaserTAGSetup.exe" (
    echo   Installer:  %OUTPUT_DIR%\LaserTAGSetup.exe
    echo.
)
echo   --- Testing ---
echo   %OUTPUT_DIR%\%APP_NAME%.dist\%APP_NAME%.exe
echo.
echo   --- Distributing without installer ---
echo   The %APP_NAME%.dist folder is the complete application.
echo   Rename it to %APP_NAME% and zip it for distribution.
echo ============================================

endlocal
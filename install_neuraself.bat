@echo off
setlocal enabledelayedexpansion
title NeuraSelf Installer
cd /d "%~dp0"
chcp 65001 >nul

set "INSTALL_DIR=%USERPROFILE%\Desktop\NeuraSelf"
set "REPO_URL=https://github.com/routo-loop/neura-self.git"
set "PYTHON_VER=3.10.11"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VER%/python-%PYTHON_VER%-amd64.exe"

color 0B
echo.
echo  [SYSTEM] NeuraSelf Installer
echo.

set "PY_CMD="
py -3.10 --version >nul 2>&1 && set "PY_CMD=py -3.10"
if not defined PY_CMD (
    python --version >nul 2>&1 && (
        for /f "tokens=2" %%v in ('python --version 2^>^&1') do (
            echo %%v | findstr /r "^3\.10\." >nul && set "PY_CMD=python"
        )
    )
)
if not defined PY_CMD (
    python3 --version >nul 2>&1 && (
        for /f "tokens=2" %%v in ('python3 --version 2^>^&1') do (
            echo %%v | findstr /r "^3\.10\." >nul && set "PY_CMD=python3"
        )
    )
)

if not defined PY_CMD (
    echo  [!] python 3.10 not found. starting auto-install...
    echo  [#] downloading python installer...
    curl -L -o "%TEMP%\py_inst.exe" %PYTHON_URL%
    if !errorlevel! neq 0 (
        echo  [X] download failed. please install python 3.10 manually.
        pause
        exit /b 1
    )
    echo  [#] installing python (may take a few minutes)...
    start /wait "%TEMP%\py_inst.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    if !errorlevel! neq 0 (
        echo  [X] installation failed or cancelled.
        del "%TEMP%\py_inst.exe"
        pause
        exit /b 1
    )
    del "%TEMP%\py_inst.exe"
    echo  [OK] python installed.
    set "PY_CMD=python"
) else (
    echo  [OK] found python: !PY_CMD!
)


where git >nul 2>&1
if errorlevel 1 (
    echo  [!] Git not found. attempting to install...
    where choco >nul 2>&1
    if not errorlevel 1 (
        choco install git -y
        echo  [OK] git installed via chocolatey
    ) else (
        where winget >nul 2>&1
        if not errorlevel 1 (
            winget install Git.Git
            echo  [OK] Git installed via winget
        ) else (
            echo  [X] no package manager found. please install git from https://git-scm.com/
            pause
            exit /b 1
        )
    )
) else (
    echo  [OK] git found
)


if exist "%INSTALL_DIR%" (
    echo  [#] updating existing installation...
    pushd "%INSTALL_DIR%"
    git pull
    popd
) else (
    echo  [#] cloning repository...
    git clone %REPO_URL% "%INSTALL_DIR%"
    if errorlevel 1 (
        echo  [X] clone failed. check network or url.
        pause
        exit /b 1
    )
    echo  [OK] repo cloned to %INSTALL_DIR%
)


echo  [#] launching neuraself setup...
pushd "%INSTALL_DIR%"
!PY_CMD! neura_setup.py --quick
if errorlevel 1 (
    echo  [X] setup exited with error.
    pause
    exit /b 1
)
popd

echo.
echo  [OK] neuraself installed and configured.
echo  you can now run the bot by going to %INSTALL_DIR% and running neura.py
pause
exit /b 0
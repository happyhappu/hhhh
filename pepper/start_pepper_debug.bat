@echo off
chcp 65001 >nul
setlocal EnableExtensions

:: ============================================================
::  Pepper real-device joint-debug one-click launcher (Windows)
::  What it does:
::    1. set pynaoqi SDK env (PYTHONPATH / PATH / PEPPER_QI_URL)
::    2. check Py2.7 can import qi & naoqi
::    3. launch suiyue-pepper main gateway (Py3) with --auto-bridge,
::       which itself spawns the Py2.7 naoqi_bridge subprocess
::  How to stop: press Ctrl+C in this window. The gateway's signal
::    handler sends stop_all first, then terminates the bridge child.
::
::  Override config via environment variables (all optional):
::    PEPPER_SDK_ENV    pynaoqi SDK directory
::    PEPPER_IP_ENV     Pepper LAN address (broker :9559)
::    SUIYUE_CLOUD_WS   cloud xiaozhi WS endpoint
::    PEPPER_PY2_EXE    Python 2.7 interpreter (runs the bridge)
::    PEPPER_PY3_EXE    Python 3 interpreter (runs the main gateway)
::    PEPPER_DEVICE_ID  device id reported to cloud
::    PEPPER_INSTALL_DEPS=1  pip install -r requirements.txt first
:: ============================================================

set "PEPPER_DIR=%~dp0"
set "WS_ROOT=%~dp0..\.."

:: --- config (env override) ---
set "PEPPER_SDK=%WS_ROOT%\pynaoqi-python2.7-2.5.7.1-win32-vs2013"
if defined PEPPER_SDK_ENV set "PEPPER_SDK=%PEPPER_SDK_ENV%"

set "PEPPER_IP=pepper.local"
if defined PEPPER_IP_ENV set "PEPPER_IP=%PEPPER_IP_ENV%"

set "CLOUD_WS=ws://192.168.31.10:8000/xiaozhi/v1"
if defined SUIYUE_CLOUD_WS set "CLOUD_WS=%SUIYUE_CLOUD_WS%"

set "PY2=python2.7"
if defined PEPPER_PY2_EXE set "PY2=%PEPPER_PY2_EXE%"

set "PY3=python"
if defined PEPPER_PY3_EXE set "PY3=%PEPPER_PY3_EXE%"

set "DEVICE_ID=pepper-01"
if defined PEPPER_DEVICE_ID set "DEVICE_ID=%PEPPER_DEVICE_ID%"

:: --- SDK runtime env ---
if not exist "%PEPPER_SDK%" (
    echo [ERROR] pynaoqi SDK not found: %PEPPER_SDK%
    echo         Set PEPPER_SDK_ENV to the correct directory.
    goto :eof
)
set "PYTHONPATH=%PEPPER_SDK%\lib;%PEPPER_DIR%"
set "PATH=%PEPPER_SDK%\bin;%PEPPER_SDK%\lib;%PATH%"
set "PEPPER_QI_URL=tcp://%PEPPER_IP%:9559"

echo ============================================================
echo  Pepper real-device debug launcher
echo  SDK      : %PEPPER_SDK%
echo  qi-url   : %PEPPER_QI_URL%
echo  cloud WS : %CLOUD_WS%
echo  device   : %DEVICE_ID%
echo ============================================================

:: --- step 1: verify Py2.7 import qi ---
echo [1/2] verify Py2.7 + pynaoqi ...
%PY2% -c "import qi, naoqi; print('qi+naoqi import OK')" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Py2.7 cannot import qi/naoqi.
    echo         Check PEPPER_SDK and PEPPER_PY2_EXE (needs 2.7 interpreter).
    goto :eof
)
echo        OK

:: --- optional: install Py3 deps ---
if defined PEPPER_INSTALL_DEPS (
    echo [opt] installing main gateway deps ...
    %PY3% -m pip install -r "%PEPPER_DIR%requirements.txt"
)

:: --- step 2: launch main gateway (--auto-bridge spawns the Py2.7 bridge) ---
echo [2/2] launch suiyue-pepper main gateway (auto-bridge on) ...
echo        Press Ctrl+C to stop (stop_all sent, bridge child ended).
echo.
pushd "%PEPPER_DIR%"
%PY3% gateway.py --auto-bridge --py2-exe "%PY2%" --cloud-ws "%CLOUD_WS%" --device-id "%DEVICE_ID%"
popd

echo.
echo [Pepper Debug] exited.
goto :eof

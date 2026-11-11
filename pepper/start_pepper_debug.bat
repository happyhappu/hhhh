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
::    PEPPER_PREFLIGHT_ONLY=1  validate this host, then exit
:: ============================================================

set "PEPPER_DIR=%~dp0"
set "WS_ROOT=%~dp0..\.."

:: --- config (env override) ---
set "PEPPER_SDK=%PEPPER_SDK_ENV%"
if not defined PEPPER_SDK (
    for /d %%D in ("%WS_ROOT%\pynaoqi-python2.7-*-win32-vs2013") do if not defined PEPPER_SDK set "PEPPER_SDK=%%~fD"
)

set "PEPPER_IP=192.168.0.93"
if defined PEPPER_IP_ENV set "PEPPER_IP=%PEPPER_IP_ENV%"

set "CLOUD_WS=ws://192.168.0.87:8000/xiaozhi/v1"
if defined SUIYUE_CLOUD_WS set "CLOUD_WS=%SUIYUE_CLOUD_WS%"

set "PY2=%PEPPER_PY2_EXE%"
if not defined PY2 if exist "%WS_ROOT%\.runtime\Python27\python.exe" set "PY2=%WS_ROOT%\.runtime\Python27\python.exe"
if not defined PY2 if exist "D:\Python27\python.exe" set "PY2=D:\Python27\python.exe"
if not defined PY2 if exist "C:\Python27\python.exe" set "PY2=C:\Python27\python.exe"
if not defined PY2 set "PY2=python2.7"

set "PY3=%PEPPER_PY3_EXE%"
if not defined PY3 if exist "D:\Python313\python.exe" set "PY3=D:\Python313\python.exe"
if not defined PY3 set "PY3=python"

set "DEVICE_ID=pepper-01"
if defined PEPPER_DEVICE_ID set "DEVICE_ID=%PEPPER_DEVICE_ID%"

set "OPUS_BIN=%PEPPER_OPUS_BIN%"
if not defined OPUS_BIN set "OPUS_BIN=%WS_ROOT%\.runtime\libopus\mingw32\bin"

:: --- SDK runtime env ---
if not exist "%PEPPER_SDK%" (
    echo [ERROR] pynaoqi SDK not found under: %WS_ROOT%
    echo         Set PEPPER_SDK_ENV to the SDK directory.
    goto :eof
)
set "PYTHONPATH=%PEPPER_SDK%\lib;%PEPPER_DIR%"
set "PATH=%PEPPER_SDK%\bin;%PEPPER_SDK%\lib;%PATH%"
if exist "%OPUS_BIN%\opus.dll" set "PATH=%OPUS_BIN%;%PATH%"
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
"%PY2%" -c "import platform,sys; assert sys.version_info[:2] == (2,7); assert platform.architecture()[0] == '32bit'; import qi, naoqi; print('qi+naoqi import OK')" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Py2.7 cannot import qi/naoqi.
    echo         Check PEPPER_SDK and PEPPER_PY2_EXE; a 32-bit 2.7 interpreter is required.
    goto :eof
)
echo        OK

:: --- optional: install Py3 deps ---
if defined PEPPER_INSTALL_DEPS (
    echo [opt] installing main gateway deps ...
    "%PY3%" -m pip install -r "%PEPPER_DIR%requirements.txt"
    if errorlevel 1 goto :eof
)

"%PY3%" "%PEPPER_DIR%gateway_doctor.py" --runtime-only
if errorlevel 1 (
    echo [ERROR] Gateway runtime preflight failed.
    goto :eof
)
if defined PEPPER_PREFLIGHT_ONLY (
    echo [OK] Gateway host preflight complete.
    goto :eof
)

:: --- step 2: launch main gateway (--auto-bridge spawns the Py2.7 bridge) ---
echo [2/2] launch suiyue-pepper main gateway (auto-bridge on) ...
echo        Press Ctrl+C to stop (stop_all sent, bridge child ended).
echo.
pushd "%PEPPER_DIR%"
"%PY3%" gateway.py --auto-bridge --py2-exe "%PY2%" --cloud-ws "%CLOUD_WS%" --device-id "%DEVICE_ID%"
popd

echo.
echo [Pepper Debug] exited.
goto :eof

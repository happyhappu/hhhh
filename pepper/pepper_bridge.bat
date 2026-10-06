@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Pepper Bridge
:: ------------------------------------------------------------
::  Launch ONLY the Py2.7 naoqi_bridge (for standalone debugging,
::  e.g. with test_bridge_client.py). The main gateway is NOT started.
::  Env overrides: PEPPER_SDK_ENV, PEPPER_IP_ENV, PEPPER_PY2_EXE
:: ------------------------------------------------------------
set "PEPPER_DIR=%~dp0"
set "WS_ROOT=%~dp0..\.."
set "PEPPER_SDK=%WS_ROOT%\pynaoqi-python2.7-2.5.7.1-win32-vs2013"
if defined PEPPER_SDK_ENV set "PEPPER_SDK=%PEPPER_SDK_ENV%"
set "PEPPER_IP=pepper.local"
if defined PEPPER_IP_ENV set "PEPPER_IP=%PEPPER_IP_ENV%"
set "PY2=python2.7"
if defined PEPPER_PY2_EXE set "PY2=%PEPPER_PY2_EXE%"
if not exist "%PEPPER_SDK%" (
    echo [ERROR] pynaoqi SDK not found: %PEPPER_SDK%
    goto :eof
)
set "PYTHONPATH=%PEPPER_SDK%\lib;%PEPPER_DIR%"
set "PATH=%PEPPER_SDK%\bin;%PEPPER_SDK%\lib;%PATH%"
set "PEPPER_QI_URL=tcp://%PEPPER_IP%:9559"
pushd "%PEPPER_DIR%"
echo Launching naoqi_bridge (Py2.7) -^> %PEPPER_QI_URL%
echo Listening on 127.0.0.1:9560 for the Py3 main gateway.
%PY2% naoqi_bridge\bridge.py --qi-url %PEPPER_QI_URL%
popd

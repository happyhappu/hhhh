@echo off
chcp 65001 >nul
setlocal EnableExtensions
title suiyue-pepper
:: ------------------------------------------------------------
::  Launch ONLY the Py3 main gateway. Assumes naoqi_bridge is
::  ALREADY listening on 127.0.0.1:9560 (run pepper_bridge.bat
::  in another window first). Does NOT auto-spawn the bridge.
::  Env overrides: SUIYUE_CLOUD_WS, PEPPER_PY3_EXE, PEPPER_DEVICE_ID
:: ------------------------------------------------------------
set "PEPPER_DIR=%~dp0"
set "WS_ROOT=%~dp0..\.."
set "CLOUD_WS=ws://192.168.0.87:8000/xiaozhi/v1"
if defined SUIYUE_CLOUD_WS set "CLOUD_WS=%SUIYUE_CLOUD_WS%"
set "PY3=%PEPPER_PY3_EXE%"
if not defined PY3 if exist "D:\Python313\python.exe" set "PY3=D:\Python313\python.exe"
if not defined PY3 set "PY3=python"
set "DEVICE_ID=pepper-01"
if defined PEPPER_DEVICE_ID set "DEVICE_ID=%PEPPER_DEVICE_ID%"
set "OPUS_BIN=%PEPPER_OPUS_BIN%"
if not defined OPUS_BIN set "OPUS_BIN=%WS_ROOT%\.runtime\libopus\mingw32\bin"
if exist "%OPUS_BIN%\opus.dll" set "PATH=%OPUS_BIN%;%PATH%"
pushd "%PEPPER_DIR%"
echo Launching suiyue-pepper main gateway (bridge must be up on :9560)...
"%PY3%" gateway.py --cloud-ws "%CLOUD_WS%" --device-id "%DEVICE_ID%"
popd

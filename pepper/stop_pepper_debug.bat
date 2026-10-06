@echo off
chcp 65001 >nul
:: ------------------------------------------------------------
::  Best-effort stop for the standalone debug windows.
::  For the one-click launcher (start_pepper_debug.bat) just press
::  Ctrl+C in its window - it shuts down gateway + bridge child cleanly.
:: ------------------------------------------------------------
echo Stopping Pepper debug processes ...
taskkill /FI "WINDOWTITLE eq Pepper Bridge*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq suiyue-pepper*" /T /F >nul 2>&1
echo Done. If anything lingers, press Ctrl+C in that window.

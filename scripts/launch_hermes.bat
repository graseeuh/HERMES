@echo off
cd /d "%~dp0.."
powershell -NoExit -Command "& .\venv\Scripts\Activate.ps1; claude"

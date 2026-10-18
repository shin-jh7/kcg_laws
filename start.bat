@echo off
title 해양경찰 법령정보센터
cd /d "%~dp0"
python run.py
if errorlevel 1 pause

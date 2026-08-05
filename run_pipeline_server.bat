@echo off
chcp 65001 >nul
cd /d %~dp0
echo Shorts 파이프라인 서버를 시작합니다...
python pipeline_server.py
pause

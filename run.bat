@echo off
title YouTube Transcript Summarizer
echo ===================================================
echo   YOUTUBE TRANSCRIPT SUMMARIZER - WINDOWS RUNNER
echo ===================================================
echo.
echo [1/2] Verifying and installing dependencies...
python -m pip install -r "%~dp0requirements.txt"
echo.
echo [2/2] Launching Streamlit web application...
python -m streamlit run "%~dp0app.py"
echo.
pause

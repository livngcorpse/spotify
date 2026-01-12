@echo off
echo Starting Telegram Music Bot...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH
    echo Please install Python 3.8+ and add it to PATH
    pause
    exit /b 1
)

REM Check if requirements are installed
echo Checking installed packages...
python -c "import telegram" >nul 2>&1
if errorlevel 1 (
    echo Installing requirements...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install requirements
        pause
        exit /b 1
    )
)

REM Check if .env file exists
if not exist ".env" (
    echo Creating .env file from template...
    copy .env.example .env
    echo Please edit .env file with your credentials
    echo Bot will now exit. Please configure .env and run again.
    pause
    exit /b 0
)

REM Check if FFmpeg is available
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo WARNING: FFmpeg not found!
    echo Audio processing will not work without FFmpeg
    echo Please install FFmpeg and add it to PATH
    echo Visit: https://ffmpeg.org/download.html
    pause
)

REM Start the bot
echo Starting bot...
python telegram_music_bot.py

pause
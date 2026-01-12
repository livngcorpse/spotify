Write-Host "Starting Telegram Music Bot..." -ForegroundColor Green
Write-Host ""

# Check if Python is available
try {
    $python_version = python --version 2>&1
    Write-Host "Python found: $python_version" -ForegroundColor Green
} catch {
    Write-Host "Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.8+ and add it to PATH" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if requirements are installed
try {
    python -c "import telegram" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing requirements..." -ForegroundColor Yellow
        python -m pip install --upgrade pip
        python -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Failed to install requirements" -ForegroundColor Red
            Read-Host "Press Enter to exit"
            exit 1
        }
    }
} catch {
    Write-Host "Error checking/installing requirements" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env file from template..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "Please edit .env file with your credentials" -ForegroundColor Yellow
    Write-Host "Bot will now exit. Please configure .env and run again." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 0
}

# Check if FFmpeg is available
try {
    $ffmpeg_version = ffmpeg -version 2>&1
    Write-Host "FFmpeg found" -ForegroundColor Green
} catch {
    Write-Host "WARNING: FFmpeg not found!" -ForegroundColor Red
    Write-Host "Audio processing will not work without FFmpeg" -ForegroundColor Red
    Write-Host "Please install FFmpeg and add it to PATH" -ForegroundColor Red
    Write-Host "Visit: https://ffmpeg.org/download.html" -ForegroundColor Red
    Read-Host "Press any key to continue anyway..."
}

# Start the bot
Write-Host "Starting bot..." -ForegroundColor Green
python telegram_music_bot.py

Read-Host "Press Enter to exit"
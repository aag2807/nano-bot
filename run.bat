@echo off
echo Starting NANO Banking AI...
echo.

REM Activate virtual environment if it exists
if exist env\Scripts\activate.bat (
    echo Activating virtual environment...
    call env\Scripts\activate.bat
)

REM Start the FastAPI server
echo Starting server on http://localhost:8000
echo API documentation available at http://localhost:8000/docs
echo.
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
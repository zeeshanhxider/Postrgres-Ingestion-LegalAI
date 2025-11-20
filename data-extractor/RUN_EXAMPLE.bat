@echo off
REM Run the example script on Windows

echo Running Example Usage inside Docker network...

docker run -it --rm --network container:legal_ai_postgres -v "%cd%":/app -w /app python:3.9 bash -c "pip install -q -r requirements.txt && python example_usage.py"

echo.
echo Done! Check extraction_results.csv for results.
pause


@echo off
REM Run this script from the data-extractor directory
REM It will execute the data extractor inside the Docker network

echo Running Data Extractor inside Docker network...

docker run -it --rm --network container:legal_ai_postgres -v "%cd%":/app -w /app python:3.9 bash -c "pip install -q -r requirements.txt && python data_extractor.py"

echo.
echo Done! Check extraction_results.csv for results.
pause


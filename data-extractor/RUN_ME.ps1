# PowerShell script to run data extractor
# Run this from the data-extractor directory

Write-Host "Running Data Extractor inside Docker network..." -ForegroundColor Green

docker run -it --rm `
  --network container:legal_ai_postgres `
  -v "${PWD}:/app" `
  -w /app `
  python:3.9 bash -c "pip install -q -r requirements.txt && python data_extractor.py"

Write-Host ""
Write-Host "Done! Check extraction_results.csv for results." -ForegroundColor Green


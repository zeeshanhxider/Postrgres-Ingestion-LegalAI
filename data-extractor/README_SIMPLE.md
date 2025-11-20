# Simple Guide to Run Data Extractor

## Quick Start

### On Windows (CMD or PowerShell)

1. **Navigate to this directory:**
   ```cmd
   cd data-extractor
   ```

2. **Double-click `RUN_ME.bat`**
   
   OR run from command line:
   ```cmd
   RUN_ME.bat
   ```

### On Linux/Mac/WSL

1. **Navigate to this directory:**
   ```bash
   cd data-extractor
   ```

2. **Make the script executable:**
   ```bash
   chmod +x RUN_ME.sh
   ```

3. **Run it:**
   ```bash
   ./RUN_ME.sh
   ```

Done! Results will be saved to `extraction_results.csv` in this folder.

---

## Or Run Manually (One Command)

### On Windows (CMD)

```cmd
docker run -it --rm --network container:legal_ai_postgres -v "%cd%":/app -w /app python:3.9 bash -c "pip install -q -r requirements.txt && python data_extractor.py"
```

### On Linux/Mac/WSL

```bash
docker run -it --rm \
  --network container:legal_ai_postgres \
  -v $(pwd):/app \
  -w /app \
  python:3.9 bash -c "pip install -q -r requirements.txt && python data_extractor.py"
```

---

## To Run the Example Instead

### Windows
```cmd
RUN_EXAMPLE.bat
```

### Linux/Mac/WSL
```bash
docker run -it --rm \
  --network container:legal_ai_postgres \
  -v $(pwd):/app \
  -w /app \
  python:3.9 bash -c "pip install -q -r requirements.txt && python example_usage.py"
```

---

## What This Does

- ✅ Connects to your postgres database automatically (no config needed)
- ✅ Installs dependencies
- ✅ Runs the extractor
- ✅ Saves results to current folder
- ✅ Cleans up when done

## Notes

- Make sure `legal_ai_postgres` container is running first
- Your CSV file should be named `sample_data.csv` in this folder
- Results appear in `extraction_results.csv`


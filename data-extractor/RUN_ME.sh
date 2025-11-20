#!/bin/bash
# Run this script from the data-extractor directory
# It will execute the data extractor inside the Docker network

docker run -it --rm \
  --network container:legal_ai_postgres \
  -v "$(pwd)":/app \
  -w /app \
  python:3.9 bash -c "pip install -q -r requirements.txt && python data_extractor.py"


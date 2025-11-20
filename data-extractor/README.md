# Data Extractor

A Python application that extracts data from CSV files and performs fuzzy string matching against PostgreSQL databases to find related case information.

## Features

- **CSV Data Processing**: Reads and processes CSV files with legal case data
- **Fuzzy String Matching**: Uses fuzzy matching with configurable thresholds (default 80%)
- **Generic Database Search**: Automatically discovers all tables and text columns in PostgreSQL
- **Multi-column Search**: Searches across citation text and relationship columns
- **Results Export**: Exports matching results to CSV format
- **Comprehensive Logging**: Detailed logging for debugging and monitoring

## Installation

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your database configuration:
```bash
cp config.env.example .env
# Edit .env with your database credentials
```

## Usage

### Basic Usage

```python
from data_extractor import DataExtractor

# Database configuration
db_config = {
    'host': 'localhost',
    'database': 'your_database',
    'user': 'your_username',
    'password': 'your_password',
    'port': '5432'
}

# Initialize extractor
extractor = DataExtractor(db_config)

# Connect and process data
extractor.connect_to_database()
df = extractor.load_csv_data('your_data.csv')
results = extractor.process_csv_data(df, threshold=80)
extractor.save_results_to_csv(results, 'output.csv')
extractor.disconnect_from_database()
```

### Running the Example

1. Update the database configuration in `example_usage.py`
2. Run the example:
```bash
python example_usage.py
```

### Running the Main Application

1. Update the database configuration in `data_extractor.py` (main function)
2. Place your CSV file in the project directory
3. Run:
```bash
python data_extractor.py
```

## CSV Format

The application expects CSV files with the following columns:
- `precedent_id`: Unique identifier for the precedent
- `case_id`: Case identifier
- `issue_id`: Issue identifier
- `precedent_case`: Name of the precedent case
- `citation`: Citation information
- `relationship`: Relationship description
- `citation_text`: Text content to search for matches

## Configuration

### Database Configuration

Update the database configuration in your script or environment variables:
- `DB_HOST`: Database host (default: localhost)
- `DB_NAME`: Database name
- `DB_USER`: Username
- `DB_PASSWORD`: Password
- `DB_PORT`: Port (default: 5432)

### Fuzzy Matching Threshold

The application uses fuzzy string matching with a configurable threshold:
- **Default**: 80% similarity
- **Range**: 0-100%
- **Adjustment**: Modify the `threshold` parameter in `process_csv_data()`

## Output

The application generates a CSV file with the following columns:
- `csv_row_index`: Index of the original CSV row
- `case_id`: Case identifier from original data
- `citation_text`: Original citation text
- `relationship_text`: Original relationship text
- `total_matches`: Total number of matches found
- `match_type`: Type of match (citation/relationship/none)
- `match_index`: Index of the match within the type
- `table_name`: Database table where match was found
- `column_name`: Database column where match was found
- `similarity_score`: Fuzzy matching score (0-100)
- `matched_text`: Actual text that matched

## How It Works

1. **Database Discovery**: Automatically discovers all tables in the PostgreSQL database
2. **Column Analysis**: Identifies text columns suitable for fuzzy matching
3. **CSV Processing**: Reads and processes each row in the CSV file
4. **Fuzzy Matching**: Performs fuzzy string matching on citation and relationship text
5. **Results Aggregation**: Collects and sorts matches by similarity score
6. **Export**: Saves results to CSV format for further analysis

## Error Handling

The application includes comprehensive error handling:
- Database connection errors
- CSV file reading errors
- SQL query execution errors
- File I/O errors

All errors are logged with detailed information for debugging.

## Dependencies

- `pandas`: CSV data processing
- `psycopg2-binary`: PostgreSQL database connection
- `fuzzywuzzy`: Fuzzy string matching
- `python-Levenshtein`: Optimized string matching
- `python-dotenv`: Environment variable management
- `sqlalchemy`: Database abstraction layer

## License

This project is open source and available under the MIT License.

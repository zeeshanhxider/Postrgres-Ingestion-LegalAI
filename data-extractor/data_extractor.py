import pandas as pd
import psycopg2
from psycopg2 import sql
from fuzzywuzzy import fuzz
import os
from typing import List, Dict, Tuple, Optional
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataExtractor:
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize the data extractor with database configuration
        
        Args:
            db_config: Dictionary containing database connection parameters
        """
        self.db_config = db_config
        self.connection = None
        self.cursor = None
        
    def connect_to_database(self):
        """Establish connection to PostgreSQL database"""
        try:
            self.connection = psycopg2.connect(
                host=self.db_config['host'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                port=self.db_config.get('port', 5432)
            )
            self.cursor = self.connection.cursor()
            logger.info("Successfully connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def disconnect_from_database(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("Disconnected from database")
    
    def get_all_tables(self) -> List[str]:
        """Get all table names from the database"""
        try:
            query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
            """
            self.cursor.execute(query)
            tables = [row[0] for row in self.cursor.fetchall()]
            logger.info(f"Found {len(tables)} tables: {tables}")
            return tables
        except Exception as e:
            logger.error(f"Error getting tables: {e}")
            raise
    
    def get_table_columns(self, table_name: str) -> List[str]:
        """Get all column names for a specific table"""
        try:
            query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s 
            AND table_schema = 'public'
            ORDER BY ordinal_position;
            """
            self.cursor.execute(query, (table_name,))
            columns = [row[0] for row in self.cursor.fetchall()]
            return columns
        except Exception as e:
            logger.error(f"Error getting columns for table {table_name}: {e}")
            return []
    
    def find_text_columns(self, table_name: str) -> List[str]:
        """Find columns that likely contain text data"""
        try:
            query = """
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = %s 
            AND table_schema = 'public'
            AND data_type IN ('text', 'character varying', 'varchar', 'character', 'char');
            """
            self.cursor.execute(query, (table_name,))
            text_columns = [row[0] for row in self.cursor.fetchall()]
            logger.info(f"Found text columns in {table_name}: {text_columns}")
            return text_columns
        except Exception as e:
            logger.error(f"Error finding text columns for table {table_name}: {e}")
            return []
    
    def search_in_table(self, table_name: str, search_text: str, 
                       text_columns: List[str], threshold: int = 80) -> List[Dict]:
        """
        Search for fuzzy matches in a specific table
        
        Args:
            table_name: Name of the table to search
            search_text: Text to search for
            text_columns: List of text columns to search in
            threshold: Fuzzy matching threshold (0-100)
            
        Returns:
            List of matching records with similarity scores
        """
        matches = []
        
        try:
            # Get all data from the table
            query = f"SELECT * FROM {table_name}"
            self.cursor.execute(query)
            rows = self.cursor.fetchall()
            
            # Get column names
            columns = self.get_table_columns(table_name)
            
            for row in rows:
                row_dict = dict(zip(columns, row))
                
                # Check each text column for fuzzy matches
                for col in text_columns:
                    if col in row_dict and row_dict[col] is not None:
                        text_value = str(row_dict[col]).strip()
                        if text_value:
                            # Calculate fuzzy match score
                            similarity = fuzz.partial_ratio(search_text.lower(), text_value.lower())
                            
                            if similarity >= threshold:
                                match_info = {
                                    'table_name': table_name,
                                    'column_name': col,
                                    'similarity_score': similarity,
                                    'matched_text': text_value,
                                    'search_text': search_text,
                                    'record_data': row_dict
                                }
                                matches.append(match_info)
                                logger.info(f"Found match in {table_name}.{col} with {similarity}% similarity")
            
        except Exception as e:
            logger.error(f"Error searching in table {table_name}: {e}")
        
        return matches
    
    def search_all_tables(self, search_text: str, threshold: int = 80) -> List[Dict]:
        """
        Search for fuzzy matches across all tables in the database
        
        Args:
            search_text: Text to search for
            threshold: Fuzzy matching threshold (0-100)
            
        Returns:
            List of all matches across all tables
        """
        all_matches = []
        tables = self.get_all_tables()
        
        logger.info(f"Starting search across {len(tables)} tables for: '{search_text}'")
        
        for table in tables:
            text_columns = self.find_text_columns(table)
            if text_columns:
                matches = self.search_in_table(table, search_text, text_columns, threshold)
                all_matches.extend(matches)
        
        # Sort by similarity score (highest first)
        all_matches.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        logger.info(f"Found {len(all_matches)} total matches")
        return all_matches
    
    def load_csv_data(self, csv_file_path: str) -> pd.DataFrame:
        """
        Load CSV data into a pandas DataFrame
        
        Args:
            csv_file_path: Path to the CSV file
            
        Returns:
            pandas DataFrame
        """
        try:
            df = pd.read_csv(csv_file_path)
            logger.info(f"Loaded CSV with {len(df)} rows and {len(df.columns)} columns")
            return df
        except Exception as e:
            logger.error(f"Error loading CSV file: {e}")
            raise
    
    def process_csv_data(self, df: pd.DataFrame, 
                        citation_text_col: str = 'citation_text',
                        relationship_col: str = 'relationship',
                        case_id_col: str = 'case_id',
                        threshold: int = 80) -> List[Dict]:
        """
        Process CSV data and find matches in the database
        
        Args:
            df: pandas DataFrame containing the CSV data
            citation_text_col: Name of the column containing citation text
            relationship_col: Name of the column containing relationship text
            case_id_col: Name of the column containing case IDs
            threshold: Fuzzy matching threshold
            
        Returns:
            List of processing results
        """
        results = []
        
        for index, row in df.iterrows():
            citation_text = str(row.get(citation_text_col, '')).strip()
            relationship_text = str(row.get(relationship_col, '')).strip()
            case_id = row.get(case_id_col, '')
            
            # Search for citation text matches
            citation_matches = []
            if citation_text and citation_text != 'nan':
                citation_matches = self.search_all_tables(citation_text, threshold)
            
            # Search for relationship text matches
            relationship_matches = []
            if relationship_text and relationship_text != 'nan':
                relationship_matches = self.search_all_tables(relationship_text, threshold)
            
            result = {
                'csv_row_index': index,
                'case_id': case_id,
                'citation_text': citation_text,
                'relationship_text': relationship_text,
                'citation_matches': citation_matches,
                'relationship_matches': relationship_matches,
                'total_matches': len(citation_matches) + len(relationship_matches)
            }
            
            results.append(result)
            
            logger.info(f"Processed row {index} (Case ID: {case_id}) - "
                       f"Found {len(citation_matches)} citation matches, "
                       f"{len(relationship_matches)} relationship matches")
        
        return results
    
    def save_results_to_csv(self, results: List[Dict], output_file: str):
        """
        Save processing results to a CSV file
        
        Args:
            results: List of processing results
            output_file: Path to output CSV file
        """
        try:
            # Flatten results for CSV export
            flattened_results = []
            
            for result in results:
                base_data = {
                    'csv_row_index': result['csv_row_index'],
                    'case_id': result['case_id'],
                    'citation_text': result['citation_text'],
                    'relationship_text': result['relationship_text'],
                    'total_matches': result['total_matches']
                }
                
                # Add citation matches
                for i, match in enumerate(result['citation_matches']):
                    match_data = base_data.copy()
                    match_data.update({
                        'match_type': 'citation',
                        'match_index': i,
                        'table_name': match['table_name'],
                        'column_name': match['column_name'],
                        'similarity_score': match['similarity_score'],
                        'matched_text': match['matched_text']
                    })
                    flattened_results.append(match_data)
                
                # Add relationship matches
                for i, match in enumerate(result['relationship_matches']):
                    match_data = base_data.copy()
                    match_data.update({
                        'match_type': 'relationship',
                        'match_index': i,
                        'table_name': match['table_name'],
                        'column_name': match['column_name'],
                        'similarity_score': match['similarity_score'],
                        'matched_text': match['matched_text']
                    })
                    flattened_results.append(match_data)
                
                # If no matches, add a row with just the base data
                if result['total_matches'] == 0:
                    match_data = base_data.copy()
                    match_data.update({
                        'match_type': 'none',
                        'match_index': 0,
                        'table_name': '',
                        'column_name': '',
                        'similarity_score': 0,
                        'matched_text': ''
                    })
                    flattened_results.append(match_data)
            
            # Create DataFrame and save to CSV
            df_results = pd.DataFrame(flattened_results)
            df_results.to_csv(output_file, index=False)
            logger.info(f"Results saved to {output_file}")
            
        except Exception as e:
            logger.error(f"Error saving results to CSV: {e}")
            raise


def main():
    """Main function to run the data extractor"""
    
    # Database configuration
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'your_database'),
        'user': os.getenv('DB_USER', 'your_username'),
        'password': os.getenv('DB_PASSWORD', 'your_password'),
        'port': os.getenv('DB_PORT', '5432')
    }
    
    # File paths
    csv_file_path = 'sample_data.csv'  # Change this to your CSV file path
    output_file_path = 'extraction_results.csv'
    
    # Initialize extractor
    extractor = DataExtractor(db_config)
    
    try:
        # Connect to database
        extractor.connect_to_database()
        
        # Load CSV data
        df = extractor.load_csv_data(csv_file_path)
        
        # Process the data
        results = extractor.process_csv_data(df, threshold=80)
        
        # Save results
        extractor.save_results_to_csv(results, output_file_path)
        
        # Print summary
        total_matches = sum(result['total_matches'] for result in results)
        print(f"\nProcessing complete!")
        print(f"Processed {len(results)} rows from CSV")
        print(f"Found {total_matches} total matches")
        print(f"Results saved to: {output_file_path}")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
    finally:
        extractor.disconnect_from_database()


if __name__ == "__main__":
    main()

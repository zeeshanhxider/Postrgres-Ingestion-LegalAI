"""
Example usage of the DataExtractor class
"""

from data_extractor import DataExtractor
import pandas as pd
import os

def main():
    # Database configuration - Update these with your actual database credentials
    db_config = {
        'host': 'localhost',  # or your database host
        'database': 'your_database_name',
        'user': 'your_username',
        'password': 'your_password',
        'port': '5432'
    }
    
    # Initialize the extractor
    extractor = DataExtractor(db_config)
    
    try:
        # Connect to database
        extractor.connect_to_database()
        
        # Load your CSV file
        csv_file_path = 'sample_data.csv'  # Change this to your actual CSV file
        df = extractor.load_csv_data(csv_file_path)
        
        # Print the loaded data
        print("Loaded CSV data:")
        print(df.head())
        print(f"\nColumns: {list(df.columns)}")
        
        # Process the data with 80% fuzzy matching threshold
        results = extractor.process_csv_data(
            df, 
            citation_text_col='citation_text',
            relationship_col='relationship', 
            case_id_col='case_id',
            threshold=80
        )
        
        # Print results summary
        print(f"\nProcessing Results:")
        print(f"Total rows processed: {len(results)}")
        
        total_matches = 0
        for result in results:
            print(f"\nRow {result['csv_row_index']} (Case ID: {result['case_id']}):")
            print(f"  Citation matches: {len(result['citation_matches'])}")
            print(f"  Relationship matches: {len(result['relationship_matches'])}")
            
            # Show top matches
            all_matches = result['citation_matches'] + result['relationship_matches']
            if all_matches:
                top_match = all_matches[0]  # Already sorted by similarity
                print(f"  Top match: {top_match['table_name']}.{top_match['column_name']} "
                      f"(similarity: {top_match['similarity_score']}%)")
            
            total_matches += result['total_matches']
        
        print(f"\nTotal matches found: {total_matches}")
        
        # Save results to CSV
        output_file = 'extraction_results.csv'
        extractor.save_results_to_csv(results, output_file)
        print(f"\nResults saved to: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        extractor.disconnect_from_database()

if __name__ == "__main__":
    main()

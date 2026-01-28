"""
Generate SQLite database with multiple data sources.
Run this script to populate MyDataBase.db with various datasets.
"""
import argparse
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from db.database_manager import DatabaseManager  # noqa: E402
from db.data_loaders.iris_loader import load_iris_data  # noqa: E402
from db.data_loaders.postal_code_loader import (  # noqa: E402
    load_postal_code_data,
    load_postal_code_apartment_m2_data,
)


def main():
    """Main function to load data sources into the database."""
    parser = argparse.ArgumentParser(description="Load data sources into MyDataBase.db")
    parser.add_argument(
        "--iris",
        action="store_true",
        help="Load Iris dataset"
    )
    parser.add_argument(
        "--postal-code",
        action="store_true",
        help="Load postal code income data"
    )
    parser.add_argument(
        "--postal-code-apartment",
        action="store_true",
        help="Load postal code apartment average m2 data"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Load all available data sources"
    )
    
    args = parser.parse_args()
    
    # If no specific source is selected, load all
    load_all = args.all or (not args.iris and not args.postal_code and not args.postal_code_apartment)
    
    # Initialize database manager
    db_manager = DatabaseManager()
    print(f"Using database: {db_manager.db_path}")
    print()
    
    errors = []
    
    # Load Iris data
    if load_all or args.iris:
        try:
            load_iris_data(db_manager)
            print()
        except Exception as e:
            error_msg = f"Error loading Iris data: {e}"
            print(f"ERROR: {error_msg}")
            errors.append(error_msg)
            print()
    
    # Load postal code income data
    if load_all or args.postal_code:
        try:
            load_postal_code_data(db_manager)
            print()
        except Exception as e:
            error_msg = f"Error loading postal code income data: {e}"
            print(f"ERROR: {error_msg}")
            errors.append(error_msg)
            print()
    
    # Load postal code apartment m2 data
    if load_all or args.postal_code_apartment:
        try:
            load_postal_code_apartment_m2_data(db_manager)
            print()
        except Exception as e:
            error_msg = f"Error loading postal code apartment m2 data: {e}"
            print(f"ERROR: {error_msg}")
            errors.append(error_msg)
            print()
    
    # Summary
    if errors:
        print("Some data sources failed to load:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("All selected data sources loaded successfully!")


if __name__ == "__main__":
    main()


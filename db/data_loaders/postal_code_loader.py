"""Loader for postal code data from PxWeb API."""
import json
import sys
import requests  # type: ignore
import numpy as np  # type: ignore
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from db.database_manager import DatabaseManager  # noqa: E402


def load_pxweb_postal_code_dataset(
    db_manager: DatabaseManager,
    table_name: str,
    api_url: str,
    query_file: Path,
    dataset_description: str,
    value_column_name: str = "value"
) -> None:
    """
    Generic function to load postal code datasets from PxWeb API.
    
    This function handles the common logic for loading postal code data from PxWeb API,
    including fetching data, parsing dimensions, and storing in long format.
    
    Args:
        db_manager: DatabaseManager instance to use for database operations
        table_name: Name of the table to create/update
        api_url: Full URL to the PxWeb API endpoint
        query_file: Path to the JSON query file
        dataset_description: Human-readable description of the dataset (for logging)
        value_column_name: Name of the value column in the schema (default: "value")
    """
    print(f"Loading {dataset_description} from PxWeb API...")
    
    # Check if table already exists
    if db_manager.table_exists(table_name):
        print(f"{dataset_description} table '{table_name}' already exists. Skipping creation.")
        return
    
    # Load query JSON
    if not query_file.exists():
        raise FileNotFoundError(f"Query file not found: {query_file}")
    
    with open(query_file, "r", encoding="utf-8") as f:
        query_json = json.load(f)
    
    # Handle different JSON structures (some may be wrapped in queryObj)
    if "queryObj" in query_json:
        query_json = query_json["queryObj"]
    
    # Make POST request
    print(f"Fetching {dataset_description} from PxWeb API...")
    try:
        response = requests.post(api_url, json=query_json, timeout=60)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
        raise
    
    # Extract dimensions (matching notebook approach)
    postal_labels = data['dimension']['Postinumeroalue']['category']['label']
    postal_index = data['dimension']['Postinumeroalue']['category']['index']
    year_index = data['dimension']['Vuosi']['category']['index']
    
    # Get postal codes and area names in order (matching notebook: idx.keys() and idx.values())
    postal_codes = sorted(postal_index.keys(), key=lambda x: postal_index[x])
    postal_areas = [postal_labels[code] for code in postal_codes]
    years = sorted(year_index.keys(), key=lambda x: year_index[x])
    
    print(f"Found {len(postal_codes)} postal codes and {len(years)} years")
    
    # Reshape values into matrix (row first: postal_code x year)
    vals = np.array(data['value']).reshape(len(postal_codes), len(years))
    
    # Create long format table
    print(f"Creating {table_name} table...")
    
    long_schema = f"""(
    postal_code TEXT,
    postal_area TEXT,
    year TEXT,
    {value_column_name} REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (postal_code, year)
)"""
    db_manager.create_table(table_name, long_schema)
    
    # Insert data in long format
    print(f"Inserting {dataset_description} (long format)...")
    conn, cursor = db_manager.get_cursor()
    
    for i, postal_code in enumerate(postal_codes):
        for j, year in enumerate(years):
            val = vals[i, j]
            # Handle null/missing values
            if val is None or (isinstance(val, float) and np.isnan(val)):
                value = None
            else:
                value = float(val)
            
            query = f"""
                INSERT INTO {table_name} (postal_code, postal_area, year, {value_column_name})
                VALUES (?, ?, ?, ?)
            """
            cursor.execute(query, (postal_code, postal_areas[i], year, value))
    
    conn.commit()
    conn.close()
    
    total_records = len(postal_codes) * len(years)
    print(f"{dataset_description} loaded successfully. Total records: {total_records}")


def load_postal_code_data(db_manager: DatabaseManager) -> None:
    """
    Load postal code income data from PxWeb API into the database.
    
    Args:
        db_manager: DatabaseManager instance to use for database operations
    """
    query_file = Path(__file__).parent.parent / "sq-api_table_paavo_pxt_12f1.px.json"
    api_url = "https://pxdata.stat.fi/PxWeb/api/v1/fi/Postinumeroalueittainen_avoin_tieto/uusin/paavo_pxt_12f1.px"
    
    load_pxweb_postal_code_dataset(
        db_manager=db_manager,
        table_name="postal_code_income",
        api_url=api_url,
        query_file=query_file,
        dataset_description="postal code income data"
    )


def load_postal_code_apartment_m2_data(db_manager: DatabaseManager) -> None:
    """
    Load postal code apartment average m2 data from PxWeb API into the database.
    
    Args:
        db_manager: DatabaseManager instance to use for database operations
    """
    query_file = Path(__file__).parent.parent / "sq-api_table_paavo_pxt_12f4.px.json"
    api_url = "https://pxdata.stat.fi/PxWeb/api/v1/fi/Postinumeroalueittainen_avoin_tieto/uusin/paavo_pxt_12f4.px"
    
    load_pxweb_postal_code_dataset(
        db_manager=db_manager,
        table_name="postal_code_apartment_m2",
        api_url=api_url,
        query_file=query_file,
        dataset_description="postal code apartment average m2 data",
        value_column_name="avg_m2"
    )




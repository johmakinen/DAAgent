"""Loader for Iris dataset."""
import sys
from pathlib import Path
from sklearn.datasets import load_iris
import pandas as pd

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from db.database_manager import DatabaseManager  # noqa: E402


def load_iris_data(db_manager: DatabaseManager) -> None:
    """
    Load Iris dataset into the database.
    
    Args:
        db_manager: DatabaseManager instance to use for database operations
    """
    print("Loading Iris dataset...")
    
    # Load Iris dataset
    iris = load_iris()
    
    # Create DataFrame
    df = pd.DataFrame(
        data=iris.data,
        columns=iris.feature_names
    )
    df['species'] = [iris.target_names[i] for i in iris.target]
    
    # Check if table already exists
    if db_manager.table_exists("iris"):
        print("Iris table already exists. Skipping creation.")
        return
    
    # Create table
    print("Creating iris table...")
    db_manager.create_table(
        "iris",
        """
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sepal_length REAL,
            sepal_width REAL,
            petal_length REAL,
            petal_width REAL,
            species TEXT
        )
        """
    )
    
    # Insert data
    print("Inserting Iris data...")
    conn, cursor = db_manager.get_cursor()
    
    for _, row in df.iterrows():
        cursor.execute("""
            INSERT INTO iris (sepal_length, sepal_width, petal_length, petal_width, species)
            VALUES (?, ?, ?, ?, ?)
        """, (
            row['sepal length (cm)'],
            row['sepal width (cm)'],
            row['petal length (cm)'],
            row['petal width (cm)'],
            row['species']
        ))
    
    conn.commit()
    conn.close()
    
    print(f"Iris data loaded successfully. Total records: {len(df)}")
    print("\nSample data:")
    print(df.head())

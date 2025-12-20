"""
Generate SQLite database with Iris dataset.
Run this script to create a SQLite database with numerical and categorical data.
"""
import sqlite3
from pathlib import Path
from sklearn.datasets import load_iris
import pandas as pd


def create_database():
    """Create SQLite database with Iris dataset."""
    # Get the db folder path
    db_folder = Path(__file__).parent
    db_path = db_folder / "iris_data.db"
    
    # Remove existing database if it exists
    if db_path.exists():
        db_path.unlink()
        print(f"Removed existing database at {db_path}")
    
    # Load Iris dataset
    print("Loading Iris dataset...")
    iris = load_iris()
    
    # Create DataFrame
    df = pd.DataFrame(
        data=iris.data,
        columns=iris.feature_names
    )
    df['species'] = [iris.target_names[i] for i in iris.target]
    
    # Create SQLite connection
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create table
    print("Creating table...")
    cursor.execute("""
        CREATE TABLE iris (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sepal_length REAL,
            sepal_width REAL,
            petal_length REAL,
            petal_width REAL,
            species TEXT
        )
    """)
    
    # Insert data
    print("Inserting data...")
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
    
    # Commit and close
    conn.commit()
    conn.close()
    
    print(f"Database created successfully at {db_path}")
    print(f"Total records: {len(df)}")
    print("\nSample data:")
    print(df.head())


if __name__ == "__main__":
    create_database()


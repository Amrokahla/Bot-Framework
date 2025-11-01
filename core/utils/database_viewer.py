import sqlite3
import os
from tabulate import tabulate

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "databases")


def list_tables(conn):
    """Return a list of table names in the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    return [row[0] for row in cursor.fetchall()]


def view_table(conn, table_name, limit=10):
    """Return rows and headers for a given table."""
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit};")
    rows = cursor.fetchall()
    headers = [desc[0] for desc in cursor.description]
    return headers, rows


def inspect_database(db_path):
    """Print all tables and their sample content."""
    print(f"\n📂 Inspecting database: {os.path.basename(db_path)}")

    conn = sqlite3.connect(db_path)
    tables = list_tables(conn)

    if not tables:
        print("   ⚠️  No tables found in this database.")
        conn.close()
        return

    for table in tables:
        print(f"\n📊 Table: {table}")
        try:
            headers, rows = view_table(conn, table)
            if rows:
                print(tabulate(rows, headers=headers, tablefmt="fancy_grid"))
            else:
                print("   (empty table)")
        except Exception as e:
            print(f"   ⚠️  Error reading table '{table}': {e}")

    conn.close()


def main():
    if not os.path.exists(DB_DIR):
        print(f"❌ Database directory not found: {DB_DIR}")
        return

    db_files = [f for f in os.listdir(DB_DIR) if f.endswith(".db")]
    if not db_files:
        print(f"⚠️ No .db files found in {DB_DIR}")
        return

    for db_file in db_files:
        db_path = os.path.join(DB_DIR, db_file)
        inspect_database(db_path)


if __name__ == "__main__":
    main()

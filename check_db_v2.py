import os
import sys

# Add the current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text, inspect
from database import engine

def check_db():
    inspector = inspect(engine)
    report = []
    
    report.append(f"Database URL: {engine.url}")
    
    tables = inspector.get_table_names()
    for table_name in tables:
        report.append(f"\nTable: {table_name}")
        # if not inspector.has_table(table_name):
        #     report.append(f"  ERROR: Table '{table_name}' does not exist!")
        #     continue
            
        columns = inspector.get_columns(table_name)
        col_names = [col['name'] for col in columns]
        for col in columns:
            report.append(f"  - {col['name']} ({col['type']})")
            
        # Specific check for missing columns
        expected_cols = {
            "events": ["is_registration_enabled", "registration_fee", "child_registration_fee", "child_age_limit", "max_attendees", "external_registration_url"],
            "event_registrations": ["child_ticket_count"]
        }
        
        if table_name in expected_cols:
            for exp in expected_cols[table_name]:
                if exp not in col_names:
                    report.append(f"  !!! MISSING: {exp}")
                else:
                    report.append(f"  [OK] {exp} exists")

    with open("db_report.txt", "w") as f:
        f.write("\n".join(report))
    print("Report generated in db_report.txt")

if __name__ == "__main__":
    check_db()

import psycopg2
import os

COMMON_PASSWORDS = ['password', 'admin', 'root', '1234', 'postgres', '']
USER = 'postgres'
HOST = 'localhost'
PORT = '5432'
DBNAME = 'postgres' # Connect to default db first

def check_password(pwd):
    try:
        conn = psycopg2.connect(
            dbname=DBNAME,
            user=USER,
            password=pwd,
            host=HOST,
            port=PORT
        )
        conn.close()
        return True
    except psycopg2.OperationalError:
        return False

def main():
    print(f"Checking common passwords for user '{USER}'...")
    
    for pwd in COMMON_PASSWORDS:
        print(f"Testing password: '{pwd}' ... ", end='')
        if check_password(pwd):
            print("SUCCESS!")
            print(f"\nFound working password: '{pwd}'")
            
            # Update .env file
            env_path = os.path.join(os.path.dirname(__file__), '.env')
            new_url = f"DATABASE_URL=postgresql://{USER}:{pwd}@{HOST}/fortunecity"
            
            # Read existing .env
            lines = []
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    lines = f.readlines()
            
            # Update or append DATABASE_URL
            updated = False
            with open(env_path, 'w') as f:
                for line in lines:
                    if line.startswith("DATABASE_URL="):
                        f.write(new_url + "\n")
                        updated = True
                    else:
                        f.write(line)
                if not updated:
                    f.write(new_url + "\n")
            
            print(f"Updated .env with the correct password.")
            return
            
        print("Failed.")

    print("\nCould not find the correct password from common defaults.")
    print("Please manually update the .env file with your PostgreSQL password.")

if __name__ == "__main__":
    main()

import mysql.connector
from mysql.connector import errorcode

DB_CONFIG = {
    "user": "adminuser",
    "password": "Pavan.kalyan",
    "host": "medsecurehealth.mysql.database.azure.com",
    "port": 3306,
    "database": "centraldb",
    "ssl_ca": "DigiCertGlobalRootG2.crt.pem",
    "ssl_disabled": False
}

# Create Tables
TABLES = {}

TABLES["users"] = (
    """
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) NOT NULL UNIQUE,
        role ENUM('admin', 'auditor', 'app_user') NOT NULL,
        hashed_password VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

TABLES["logs"] = (
    """
    CREATE TABLE IF NOT EXISTS logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        prompt TEXT NOT NULL,
        response TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """
)

def create_schema(cursor):
    for table_name, table_sql in TABLES.items():
        try:
            print(f"Creating table {table_name}...", end=" ")
            cursor.execute(table_sql)
            print("OK")
        except mysql.connector.Error as err:
            print(f"Error creating {table_name}: {err}")

def insert_test_user(cursor):
    try:
        cursor.execute(
            """
            INSERT INTO users (username, role, hashed_password)
            VALUES (%s, %s, %s)
            """,
            ("test", "app_user", "test")
        )
        print("Test user added.")
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_DUP_ENTRY:
            print("Test user already exists.")
        else:
            print(f"Error inserting test user: {err}")

def main():
    try:
        cnx = mysql.connector.connect(**DB_CONFIG)
        cursor = cnx.cursor()

        # Create tables
        create_schema(cursor)

        # Insert test user
        insert_test_user(cursor)

        cnx.commit()
        cursor.close()
        cnx.close()
        print("Setup completed successfully.")

    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")

if __name__ == "__main__":
    main()

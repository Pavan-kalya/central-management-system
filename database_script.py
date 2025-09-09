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

TABLES["departments"] = (
    """
    CREATE TABLE IF NOT EXISTS departments (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL UNIQUE,
        description TEXT
    )
    """
)

TABLES["doctors"] = (
    """
    CREATE TABLE IF NOT EXISTS doctors (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        specialization VARCHAR(100),
        department_id INT,
        email VARCHAR(100),
        phone VARCHAR(20),
        FOREIGN KEY (department_id) REFERENCES departments(id)
    )
    """
)

TABLES["patients"] = (
    """
    CREATE TABLE IF NOT EXISTS patients (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        dob DATE,
        gender ENUM('Male','Female','Other'),
        contact_number VARCHAR(20),
        email VARCHAR(100),
        address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

TABLES["patient_records"] = (
    """
    CREATE TABLE IF NOT EXISTS patient_records (
        id INT AUTO_INCREMENT PRIMARY KEY,
        patient_id INT NOT NULL,
        record_type VARCHAR(50),
        blob_url VARCHAR(255) NOT NULL,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients(id)
    )
    """
)

TABLES["appointments"] = (
    """
    CREATE TABLE appointments (
        id INT AUTO_INCREMENT PRIMARY KEY,
        patient_id INT NOT NULL,
        department_id INT NOT NULL,
        doctor_id INT NOT NULL,
        appointment_date DATE NOT NULL,
        appointment_time TIME NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
        FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE,
        FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE
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

def insert_test_departments_and_doctors(cursor):
    try:
        # Insert sample departments
        departments = [
            ("Cardiology", "Heart-related treatments and diagnostics."),
            ("Neurology", "Brain and nervous system care."),
            ("Pediatrics", "Healthcare for infants and children."),
            ("Orthopedics", "Bone and joint care."),
        ]
        for name, desc in departments:
            try:
                cursor.execute(
                    """
                    INSERT INTO departments (name, description)
                    VALUES (%s, %s)
                    """,
                    (name, desc),
                )
                print(f"Department '{name}' added.")
            except mysql.connector.Error as err:
                if err.errno == errorcode.ER_DUP_ENTRY:
                    print(f"Department '{name}' already exists.")
                else:
                    print(f"Error inserting department '{name}': {err}")

        # Insert sample doctors (assigning them to departments by ID)
        doctors = [
            ("Dr. A Kumar", "Cardiologist", 1, "a.kumar@example.com", "9876543210"),
            ("Dr. B Sharma", "Neurologist", 2, "b.sharma@example.com", "9876501234"),
            ("Dr. C Patel", "Pediatrician", 3, "c.patel@example.com", "9876505678"),
            ("Dr. D Singh", "Orthopedic Surgeon", 4, "d.singh@example.com", "9876509999"),
        ]
        for name, specialization, dept_id, email, phone in doctors:
            try:
                cursor.execute(
                    """
                    INSERT INTO doctors (name, specialization, department_id, email, phone)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (name, specialization, dept_id, email, phone),
                )
                print(f"Doctor '{name}' added.")
            except mysql.connector.Error as err:
                if err.errno == errorcode.ER_DUP_ENTRY:
                    print(f"Doctor '{name}' already exists.")
                else:
                    print(f"Error inserting doctor '{name}': {err}")

    except Exception as e:
        print(f"Unexpected error: {e}")

def main():
    try:
        cnx = mysql.connector.connect(**DB_CONFIG)
        cursor = cnx.cursor()

        # Create tables
        create_schema(cursor)

        # Insert test user
        insert_test_user(cursor)

        # Insert test dept and doctors
        insert_test_departments_and_doctors(cursor)

        cnx.commit()
        cursor.close()
        cnx.close()
        print("Setup completed successfully.")

    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")

if __name__ == "__main__":
    main()

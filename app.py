import re, json, mysql.connector
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from azure.storage.blob import BlobServiceClient
from openai import OpenAI
import mysql.connector
import uuid
from support import *
import os

app = Flask(__name__)
app.secret_key = 'yoursecret'

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
# ------------------- LOGIN MANAGER -------------------
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

DB_CONFIG = {
    "user": "adminuser",
    "password": "Pavan.kalyan",
    "host": "medsecurehealth.mysql.database.azure.com",
    "port": 3306,
    "database": "centraldb",
    "ssl_ca": "DigiCertGlobalRootG2.crt.pem",
    "ssl_disabled": False
}

cnx = mysql.connector.connect(**DB_CONFIG)
cursor = cnx.cursor()

AZURE_STORAGE_CONNECTION_STRING = os.environ.get("AZURE_BLOB_CONNECTION_STRING", "")
CONTAINER_NAME = "patient-records"
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)


class User(UserMixin):
    def __init__(self, id, username, role, hashed_password):
        self.id = id
        self.username = username
        self.role = role
        self.hashed_password = hashed_password

@login_manager.user_loader
def load_user(user_id):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return User(row[0], row[1], row[2], row[3])
    return None

# ---- 1. Extract PHI using GPT-4 ----
def extract_phi(text):
    prompt = f"""
    Identify all PHI entities (like name, date of birth, address, SSN) in this text.
    Return as JSON with keys: name, dob, address, ssn.
    Text: {text}
    """
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role":"system","content":"You are a PHI extraction assistant."},
            {"role":"user","content":prompt}
        ],
        temperature=0
    )
    return response.choices[0].message.content

# ---- 2. Anonymize PHI in text ----
def anonymize_text(text, phi_json):
    try:
        phi_dict = json.loads(phi_json)
    except:
        phi_dict = {}
    for key, value in phi_dict.items():
        if value:
            text = re.sub(re.escape(value), f"<{key.upper()}>", text)
    return text

# ---- 3. Validate anonymization ----
def validate_anonymization(text):
    prompt = f"""
    Check if the following text contains any PHI such as names, addresses, dates of birth, SSN.
    Respond with 'COMPLIANT' or 'NOT COMPLIANT'. If not compliant, explain why. 
    If the data is masked then consider it to be COMPLIANT.
    Return output as JSON with keys: 'status' and 'reason'.
    Text: {text}
    """
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role":"system","content":"You are a compliance validation assistant."},
            {"role":"user","content":prompt}
        ],
        temperature=0
    )
    return response.choices[0].message.content

# ---- 4. Routes ----
@app.route("/")
def home():
    if current_user.is_authenticated:
        return render_template("index.html", user=current_user)
    return redirect(url_for("login"))

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=%s AND hashed_password=%s", (username, password))
        user_row = cursor.fetchone()
        print(user_row)
        if user_row:
            user = User(user_row[0], user_row[1], user_row[2], user_row[3])
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password", "danger")
    
    return render_template("login.html")

# ---------- LOGOUT ----------
@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/chat")
def chat():
    return render_template("chat.html")

@app.route("/ask", methods=["POST"])
def ask():
    user_input = request.json.get("prompt", "").strip()

    # -------- Validation --------
    if not user_input:
        return jsonify({"error": "Prompt cannot be empty"}), 400
    if len(user_input) > 2000:
        return jsonify({"error": "Prompt too long (max 2000 chars)"}), 400

    try:
        # -------- Call OpenAI --------
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": user_input}],
            temperature=0.7
        )
        answer = response.choices[0].message.content

        # -------- Save to logs table --------
        cursor.execute(
                """
                INSERT INTO logs (user_id, prompt, response) 
                VALUES (%s, %s, %s)
                """,
                (current_user.id, user_input, answer)
            )
        
        cnx.commit()
        cursor.close()
        cnx.close()

        # -------- Return JSON response --------
        return jsonify({"response": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/agent_chat")
def agent_chat():
    return render_template("agent_chat.html")

@app.route("/agent_ask", methods=["POST"])
def agent_ask():
    user_input = request.json.get("prompt", "")
    if not user_input:
        return jsonify({"error": "Prompt required"}), 400

    try:
        cnx = mysql.connector.connect(**DB_CONFIG)
        response = agentic_query(client, cnx, user_input)
        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/anonymize_data", methods=["GET", "POST"])
def anonymize_data():
    original_text = anonymized_text = compliance_result = ""
    if request.method == "POST":
        original_text = request.form["patient_text"]

        # Step 1: Extract PHI
        phi_data = extract_phi(original_text)

        # Step 2: Anonymize
        anonymized_text = anonymize_text(original_text, phi_data)

        # Step 3: Validate
        compliance_result = validate_anonymization(anonymized_text)

    return render_template("anonymize_data.html",
                           original_text=original_text,
                           anonymized_text=anonymized_text,
                           compliance_result=compliance_result)

@app.route("/patients")
def patients():
    return render_template("patients.html")

@app.route("/register_patient", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        dob = request.form["dob"]
        gender = request.form["gender"]
        contact_number = request.form["contact_number"]
        email = request.form["email"]
        address = request.form["address"]

        try:
            cnx = mysql.connector.connect(**DB_CONFIG)
            cursor = cnx.cursor()
            query = """INSERT INTO patients (name, dob, gender, contact_number, email, address)
                       VALUES (%s, %s, %s, %s, %s, %s)"""
            cursor.execute(query, (name, dob, gender, contact_number, email, address))
            cnx.commit()

            patient_id = cursor.lastrowid
        except mysql.connector.Error as err:
            return render_template("register_patient.html", error=str(err))
        finally:
            cursor.close()
            cnx.close()

        return render_template("register_patient.html", success=True, patient_id=patient_id)

    return render_template("register_patient.html")


@app.route("/view_patient", methods=["GET", "POST"])
def view():
    patient_data = None
    if request.method == "POST":
        patient_id = request.form.get("patient_id")
        name = request.form.get("name")
        dob = request.form.get("dob")

        try:
            cnx = mysql.connector.connect(**DB_CONFIG)
            cursor = cnx.cursor(dictionary=True)

            if patient_id:  # search by ID
                query = "SELECT * FROM patients WHERE id = %s"
                cursor.execute(query, (patient_id,))
                patient_data = cursor.fetchone()

            elif name and dob:  # search by name + DOB
                query = "SELECT * FROM patients WHERE name = %s AND dob = %s"
                cursor.execute(query, (name, dob))
                patient_data = cursor.fetchone()

        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "danger")
        finally:
            cursor.close()
            cnx.close()

    return render_template("view_patient.html", patient=patient_data)


@app.route("/book_appointment", methods=["GET", "POST"])
def book_appointment():
    try:
        cnx = mysql.connector.connect(**DB_CONFIG)
        cursor = cnx.cursor(dictionary=True)

        # Fetch departments and doctors
        cursor.execute("SELECT id, name FROM departments")
        departments = cursor.fetchall()

        cursor.execute("SELECT id, name FROM doctors")
        doctors = cursor.fetchall()

        cursor.close()
        cnx.close()
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")
        departments, doctors = [], []

    if request.method == "POST":
        patient_id = request.form["patient_id"]
        department_id = request.form["department_id"]
        doctor_id = request.form["doctor_id"]
        appointment_date = request.form["appointment_date"]
        appointment_time = request.form["appointment_time"]

        try:
            cnx = mysql.connector.connect(**DB_CONFIG)
            cursor = cnx.cursor()
            query = """INSERT INTO appointments 
                       (patient_id, department_id, doctor_id, appointment_date, appointment_time) 
                       VALUES (%s, %s, %s, %s, %s)"""
            cursor.execute(query, (patient_id, department_id, doctor_id, appointment_date, appointment_time))
            cnx.commit()
            flash("Appointment booked successfully!", "success")
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "danger")
        finally:
            cursor.close()
            cnx.close()

        return redirect(url_for("book_appointment"))

    return render_template("book_appointment.html", departments=departments, doctors=doctors)

@app.route("/view_appointments/<int:patient_id>")
def view_appointments(patient_id):
    try:
        cnx = mysql.connector.connect(**DB_CONFIG)
        cursor = cnx.cursor(dictionary=True)
        cursor.execute(
            "SELECT a.id, a.appointment_date, a.appointment_time, d.name as doctor_name, dept.name as department_name "
            "FROM appointments a "
            "JOIN doctors d ON a.doctor_id = d.id "
            "JOIN departments dept ON a.department_id = dept.id "
            "WHERE a.patient_id = %s", (patient_id,)
        )
        appointments = cursor.fetchall()
    except mysql.connector.Error as err:
        appointments = []
        flash(f"Database error: {err}", "danger")
    finally:
        cursor.close()
        cnx.close()

    return render_template("appointments.html", appointments=appointments, patient_id=patient_id)

@app.route("/upload_record", methods=["GET", "POST"])
def upload_record():
    if request.method == "POST":
        patient_id = request.form["patient_id"]
        record_type = request.form["record_type"]
        file = request.files["file"]

        if not file:
            flash("Please select a file to upload", "danger")
            return redirect(request.url)

        cnx = mysql.connector.connect(**DB_CONFIG)
        cursor = cnx.cursor()

        try:
            # Upload file to Azure Blob
            blob_name = f"{patient_id}_{uuid.uuid4()}_{file.filename}"
            blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
            blob_client.upload_blob(file, overwrite=True)

            # Generate blob URL
            blob_url = blob_client.url

            # Insert into DB
            
            query = """INSERT INTO patient_records (patient_id, record_type, blob_url) 
                       VALUES (%s, %s, %s)"""
            cursor.execute(query, (patient_id, record_type, blob_url))
            cnx.commit()

            flash("Record uploaded successfully!", "success")

        except Exception as e:
            print(f"Error uploading record: {e}", "danger")
        finally:
            cursor.close()
            cnx.close()

        return redirect(url_for("upload_record"))

    return render_template("upload_record.html")

@app.route("/view_records/<int:patient_id>")
def view_records(patient_id):
    try:
        cnx = mysql.connector.connect(**DB_CONFIG)
        cursor = cnx.cursor(dictionary=True)

        # Fetch patient details
        cursor.execute("SELECT * FROM patients WHERE id = %s", (patient_id,))
        patient = cursor.fetchone()

        # Fetch patient records
        cursor.execute(
            "SELECT id, record_type, blob_url, uploaded_at FROM patient_records WHERE patient_id = %s ORDER BY uploaded_at DESC",
            (patient_id,),
        )
        records = cursor.fetchall()

        cursor.close()
        cnx.close()
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")
        patient, records = None, []

    return render_template("view_records.html", patient=patient, records=records)

if __name__ == "__main__":
    app.run(debug=True)
import os, re, json, logging, mysql.connector
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from openai import OpenAI
import mysql.connector
import config

app = Flask(__name__)
app.secret_key = 'yoursecret'

client = OpenAI(api_key=config.OPENAI_API_KEY)

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

if __name__ == "__main__":
    app.run(debug=True)
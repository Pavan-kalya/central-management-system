import os, re, json
from flask import Flask, render_template, request, jsonify
from openai import OpenAI
import config 

app = Flask(__name__)

client = OpenAI(api_key=config.OPENAI_API_KEY)

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
    Respond with 'COMPLIANT' or 'NOT COMPLIANT'. If not compliant, explain why. If the data is masked then consider it to be COMPLIANT.
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
    return render_template("index.html")

@app.route("/chat")
def chat():
    return render_template("chat.html")

@app.route("/anonymize_data")
def anonymize_data():
    return render_template("anonymize_data.html")

@app.route("/ask", methods=["POST"])
def ask():
    user_input = request.json.get("prompt")

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", 
            messages=[{"role": "user", "content": user_input}]
        )

        answer = response.choices[0].message.content
        return jsonify({"response": answer})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/anonymize_data", methods=["GET", "POST"])
def index():
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

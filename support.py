import json

def agentic_query(client, conn, user_input):
    """
    Process natural language, query DB, and summarize results.
    """
    # Step 1: Use GPT to decide intent
    prompt = f"""
    You are an assistant that converts natural language into SQL instructions.
    Database has tables: patients, appointments, doctors, departments, patient_records.
    User asked: "{user_input}"
    Return JSON with keys:
    - intent: (patients, appointments, records, all)
    - patient_id (if mentioned, else null)
    """
    intent_resp = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role":"user","content":prompt}],
        temperature=0
    )
    intent_json = json.loads(intent_resp.choices[0].message.content)

    patient_id = intent_json.get("patient_id")
    intent = intent_json.get("intent")

    # Step 2: Query DB
    cursor = conn.cursor(dictionary=True)

    patient, appointments, records = None, [], []

    if patient_id:
        cursor.execute("SELECT * FROM patients WHERE id = %s", (patient_id,))
        patient = cursor.fetchone()

        cursor.execute("""
            SELECT a.appointment_date, a.appointment_time, d.name AS doctor, dept.name AS department
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.id
            JOIN departments dept ON a.department_id = dept.id
            WHERE a.patient_id = %s
        """, (patient_id,))
        appointments = cursor.fetchall()

        cursor.execute("SELECT record_type, blob_url, uploaded_at FROM patient_records WHERE patient_id = %s", (patient_id,))
        records = cursor.fetchall()

    cursor.close()
    conn.close()

    # Step 3: Summarize results with GPT
    summary_prompt = f"""
    Summarize the following patient data in a human-readable way:

    Patient: {json.dumps(patient, default=str)}
    Appointments: {json.dumps(appointments, default=str)}
    Records: {json.dumps(records, default=str)}

    Make it conversational and concise.
    - If there are any 'blob_url' values, render them as HTML clickable links (<a href="...">...<a>).
    - Only use safe HTML (no scripts).
    """
    summary_resp = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role":"user","content":summary_prompt}],
        temperature=0.5
    )
    return summary_resp.choices[0].message.content

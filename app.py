from flask import Flask, request, jsonify, render_template_string, Response
from datetime import datetime
import pandas as pd
import pypdf
import os
import io
import json
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# --- Google Sheets Setup ---
try:
    creds_json = json.loads(os.environ.get("GOOGLE_CREDENTIALS_JSON"))
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("Faculty Passing Records").sheet1
except Exception as e:
    print(f"Google Sheet Connection Error: {e}")
    sheet = None

def load_records():
    if sheet is None:
        return []
    try:
        all_rows = sheet.get_all_records()
        formatted_records = []
        for r in all_rows:
            formatted_records.append({
                "name": r.get("Who Passed", "Unknown User"),
                "office": r.get("Office", "Unknown Office"),
                "month": r.get("Month Submitted", ""),
                "filename": r.get("Source File Checked", "")
            })
        return formatted_records
    except Exception:
        return []

def save_record(name, office, month, filename):
    if sheet is None:
        return
    try:
        sheet.append_row([name, office, month, filename])
    except Exception as e:
        print(f"Failed to save row to Google Sheets: {e}")

def extract_info_from_pdf(file_bytes):
    try:
        pdf_file = io.BytesIO(file_bytes)
        reader = pypdf.PdfReader(pdf_file)
        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
        
        person_name = "Unknown User"
        office_name = "Unknown Office"
        
        for line in full_text.split('\n'):
            clean_line = line.strip().lower()
            if 'name' in clean_line:
                if ':' in line:
                    person_name = line.split(':', 1)[1].strip()
                else:
                    idx = clean_line.find('name') + 4
                    person_name = line[idx:].strip()
            if 'office' in clean_line:
                if ':' in line:
                    office_name = line.split(':', 1)[1].strip()
                else:
                    idx = clean_line.find('office') + 6
                    office_name = line[idx:].strip()
        return person_name, office_name
    except Exception:
        return "Unknown User", "Unknown Office"

@app.route('/records', methods=['GET'])
def get_records():
    return jsonify(load_records())

@app.route('/upload', methods=['POST'])
def process_file():
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file part"})
            
        file = request.files['file']
        filename = file.filename
        filename_lower = filename.lower()
        file_bytes = file.read()
        current_month = datetime.now().strftime("%B %Y")
        
        if filename_lower.endswith('.pdf'):
            person_name, office_name = extract_info_from_pdf(file_bytes)
        elif filename_lower.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_bytes))
            df.columns = [str(c).strip().lower() for c in df.columns]
            person_name = df['name'].iloc[0] if 'name' in df.columns else "Unknown User"
            office_name = df['office'].iloc[0] if 'office' in df.columns else "Unknown Office"
        else:
            df = pd.read_excel(io.BytesIO(file_bytes))
            df.columns = [str(c).strip().lower() for c in df.columns]
            person_name = df['name'].iloc[0] if 'name' in df.columns else "Unknown User"
            office_name = df['office'].iloc[0] if 'office' in df.columns else "Unknown Office"
        
        if person_name == "": person_name = "Unknown User"
        if office_name == "": office_name = "Unknown Office"
        person_name = str(person_name).title()
        office_name = str(office_name).upper()
        
        existing = load_records()
        if any(r['filename'] == filename for r in existing):
            return jsonify({"status": "exists", "message": f"{filename} already scanned."})

        save_record(person_name, office_name, current_month, filename)
        
        return jsonify({
            "status": "success",
            "name": person_name,
            "office": office_name,
            "month": current_month
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/')
def main_page():
    secret_password = "facultyboard2026"
    auth = request.authorization
    if not auth or auth.username != "faculty" or auth.password != secret_password:
        return Response(
            "Login required to access the Passing Records Board.", 
            401, 
            {"WWW-Authenticate": 'Basic realm="Login Required"'}
        )
    try:
        with open("index.html", "r") as f:
            return render_template_string(f.read())
    except Exception:
        return "Error: index.html file not found."

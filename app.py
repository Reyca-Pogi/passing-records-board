from flask import Flask, request, jsonify, render_template_string
from datetime import datetime
import pandas as pd
import pypdf
import os
import io

app = Flask(__name__)

DATA_FILE = "/home/REYCA/mysite/passed_list.csv"

def load_records():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        df = pd.read_csv(DATA_FILE)
        return df.to_dict(orient="records")
    except Exception:
        return []

def save_record(name, office, month, filename):
    new_data = pd.DataFrame([{
        "name": name,
        "office": office,
        "month": month,
        "filename": filename
    }])
    if not os.path.exists(DATA_FILE):
        new_data.to_csv(DATA_FILE, index=False)
    else:
        new_data.to_csv(DATA_FILE, mode='a', header=False, index=False)

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
            
            # Smarter matching for Name
            if 'name' in clean_line:
                if ':' in line:
                    person_name = line.split(':', 1)[1].strip()
                else:
                    # If there's no colon, look for text right after the word 'name'
                    idx = clean_line.find('name') + 4
                    person_name = line[idx:].strip()
            
            # Smarter matching for Office
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
        
        # Clean clean layout formatting
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
    try:
        with open("/home/REYCA/mysite/index.html", "r") as f:
            return render_template_string(f.read())
    except Exception:
        return "Error: index.html file not found in mysite folder."

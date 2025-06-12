from flask import Flask, request, render_template, redirect, url_for, make_response
import re
import math
import os
from werkzeug.utils import secure_filename
import datetime
import json
import csv
from io import StringIO

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'doc', 'docx', 'pdf'}
RESULTS_FILE = 'results.json'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create uploads folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_file(file_path):
    # For simplicity, we'll just read text files directly
    # In a production app, you'd use libraries like PyPDF2, python-docx, etc.
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
        return file.read()

def calculate_similarity(text1, text2):
    # Convert texts to lowercase
    text1 = text1.lower()
    text2 = text2.lower()
    
    # Create word lists and universal set
    universalSetOfUniqueWords = []
    text1_words = re.sub(r"[^\w]", " ", text1).split()
    text2_words = re.sub(r"[^\w]", " ", text2).split()
    
    # Build universal set of unique words
    for word in text1_words:
        if word not in universalSetOfUniqueWords:
            universalSetOfUniqueWords.append(word)
    
    for word in text2_words:
        if word not in universalSetOfUniqueWords:
            universalSetOfUniqueWords.append(word)
    
    # Calculate TF vectors
    text1_tf = []
    text2_tf = []
    
    for word in universalSetOfUniqueWords:
        text1_count = 0
        text2_count = 0
        
        for word2 in text1_words:
            if word == word2:
                text1_count += 1
        text1_tf.append(text1_count)
        
        for word2 in text2_words:
            if word == word2:
                text2_count += 1
        text2_tf.append(text2_count)
    
    # Calculate cosine similarity
    dotProduct = 0
    for i in range(len(text1_tf)):
        dotProduct += text1_tf[i] * text2_tf[i]
    
    text1_magnitude = 0
    for i in range(len(text1_tf)):
        text1_magnitude += text1_tf[i]**2
    text1_magnitude = math.sqrt(text1_magnitude)
    
    text2_magnitude = 0
    for i in range(len(text2_tf)):
        text2_magnitude += text2_tf[i]**2
    text2_magnitude = math.sqrt(text2_magnitude)
    
    # Handle division by zero
    if text1_magnitude * text2_magnitude != 0:
        similarity = (float)(dotProduct / (text1_magnitude * text2_magnitude)) * 100
    else:
        similarity = 0
    
    return similarity

def save_result(input_type, content, similarity):
    # Create results file if it doesn't exist
    if not os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'w') as f:
            json.dump([], f)
    
    # Read existing results
    with open(RESULTS_FILE, 'r') as f:
        results = json.load(f)
    
    # Add new result
    result = {
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'input_type': input_type,
        'content_preview': content[:100] + '...' if len(content) > 100 else content,
        'similarity': similarity
    }
    
    results.append(result)
    
    # Save updated results
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f)

@app.route("/")
def loadPage():
    return render_template('index.html', query="", output="")

@app.route("/", methods=['POST'])
def check_plagiarism():
    try:
        database_text = ""
        input_text = ""
        input_type = "text"
        
        # Read database content
        with open("database1.txt", "r") as fd:
            database_text = fd.read().lower()
        
        # Check if this is a file upload or text input
        if 'file' in request.files and request.files['file'].filename != '':
            file = request.files['file']
            
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                # Extract text from file
                input_text = extract_text_from_file(file_path)
                input_type = "file"
            else:
                return render_template('index.html', query="", 
                                      output="Error: Invalid file type. Please upload a .txt, .doc, .docx, or .pdf file.")
        else:
            # Process text input
            input_text = request.form['query']
        
        # Calculate similarity
        similarity = calculate_similarity(input_text, database_text)
        
        # Save result
        save_result(input_type, input_text, similarity)
        
        # Generate output message
        output = f"Input {input_type} matches {similarity:.2f}% with database."
        
        return render_template('index.html', query=input_text, output=output)
    
    except Exception as e:
        output = f"Error: {str(e)}"
        return render_template('index.html', query=request.form.get('query', ''), output=output)

@app.route("/history")
def view_history():
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'r') as f:
            results = json.load(f)
            
            # Add ID to each result for reference
            for i, result in enumerate(results):
                result['id'] = i
    else:
        results = []
    
    return render_template('history.html', results=results)

@app.route("/export-history")
def export_history():
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'r') as f:
            results = json.load(f)
    else:
        results = []
    
    # Create a CSV in memory
    si = StringIO()
    csv_writer = csv.writer(si)
    
    # Write header
    csv_writer.writerow(['Date & Time', 'Type', 'Content Preview', 'Similarity (%)'])
    
    # Write data
    for result in results:
        csv_writer.writerow([
            result['timestamp'],
            result['input_type'],
            result['content_preview'],
            f"{result['similarity']:.2f}"
        ])
    
    # Create response
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=plagiarism_history.csv"
    output.headers["Content-type"] = "text/csv"
    
    return output

@app.route("/report/<int:result_id>")
def view_report(result_id):
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'r') as f:
            results = json.load(f)
            
            if 0 <= result_id < len(results):
                result = results[result_id]
                return render_template('report.html', result=result)
    
    # If result not found, redirect to history
    return redirect(url_for('view_history'))

if __name__ == "__main__":
    app.run(debug=True)

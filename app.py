
import os
import sqlite3
import logging
import requests

from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

app.logger.setLevel(logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "students.db")

# Yvonne's deployed student API.
PARTNER_API_URL = os.environ.get(
    "PARTNER_API_URL",
    "https://yvonne-mahilum.onrender.com/api/students"
)

REQUEST_TIMEOUT = 30


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    conn = get_db()

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                name TEXT NOT NULL,
                program TEXT NOT NULL,
                year INTEGER NOT NULL,
                section TEXT NOT NULL,
                source TEXT DEFAULT 'Local'
            )
        """)

        columns = [
            column["name"]
            for column in conn.execute(
                "PRAGMA table_info(students)"
            ).fetchall()
        ]

        if "source" not in columns:
            conn.execute("""
                ALTER TABLE students
                ADD COLUMN source TEXT DEFAULT 'Local'
            """)

        conn.commit()

    finally:
        conn.close()


initialize_database()


# ==========================================
# VALIDATE STUDENT DATA
# ==========================================

def validate_student(data):

    if not isinstance(data, dict):
        return None, "Valid JSON student data is required."

    required_fields = [
        "student_id",
        "name",
        "program",
        "year",
        "section"
    ]

    for field in required_fields:
        value = data.get(field)

        if value is None or str(value).strip() == "":
            return None, f"{field.replace('_', ' ').title()} is required."

    try:
        year = int(data["year"])

        if year < 1 or year > 10:
            raise ValueError

    except (TypeError, ValueError):
        return None, "Year must be a number from 1 to 10."

    student = {
        "student_id": str(data["student_id"]).strip(),
        "name": str(data["name"]).strip(),
        "program": str(data["program"]).strip(),
        "year": year,
        "section": str(data["section"]).strip().upper()
    }

    return student, None


# ==========================================
# NORMALIZE PARTNER API RESPONSE
# ==========================================

def normalize_student_records(records):

    if isinstance(records, dict):
        records = (
            records.get("students")
            or records.get("records")
            or records.get("data")
            or records.get("results")
        )

    if not isinstance(records, list):
        return None

    return records


# ==========================================
# VALIDATE PARTNER BASE URL
# ==========================================

def validate_partner_base_url(base_url):

    if not base_url:
        return None

    parsed = urlparse(base_url)

    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        return None

    return base_url.rstrip("/")


# ==========================================
# MAIN PAGE
# ==========================================

@app.route("/")
def home():
    return render_template("index.html")


# ==========================================
# BASIC API
# ==========================================

@app.route("/api")
def api():
    return jsonify({
        "message": "Welcome to Neca's Student API!"
    })


# ==========================================
# STUDENT INFORMATION
# ==========================================

@app.route("/student", methods=["GET"])
def student_information():

    conn = get_db()

    try:
        student = conn.execute("""
            SELECT student_id, name, program, year, section
            FROM students
            ORDER BY id ASC
            LIMIT 1
        """).fetchone()

    finally:
        conn.close()

    if student is None:
        return jsonify({
            "error": "No student information found. Add a student first."
        }), 404

    return jsonify(dict(student))


# ==========================================
# SKILLS API
# ==========================================

@app.route("/skills", methods=["GET"])
def get_skills():

    return jsonify({
        "skills": [
            "Python",
            "Flask",
            "HTML",
            "CSS",
            "JavaScript",
            "SQLite",
            "API Integration",
            "Database Management"
        ]
    })


# ==========================================
# GREETING API
# ==========================================

@app.route("/hello", methods=["GET"])
def hello():

    name = request.args.get("name", "Student").strip()

    if not name:
        name = "Student"

    return jsonify({
        "message": f"Hello, {name}! Welcome to Neca's Student API."
    })


# ==========================================
# GET ALL STUDENTS
# ==========================================

@app.route("/students", methods=["GET"])
@app.route("/api/students", methods=["GET"])
def get_students():

    conn = get_db()

    try:
        students = conn.execute("""
            SELECT *
            FROM students
            ORDER BY id DESC
        """).fetchall()

        return jsonify([
            dict(student)
            for student in students
        ])

    except sqlite3.Error:
        app.logger.exception("Unable to retrieve students")

        return jsonify({
            "error": "Database error while retrieving students."
        }), 500

    finally:
        conn.close()


# ==========================================
# GET STUDENT BY DATABASE ID
# ==========================================

@app.route("/students/<int:student_id>", methods=["GET"])
@app.route("/api/students/<int:student_id>", methods=["GET"])
def get_student_by_id(student_id):

    conn = get_db()

    try:
        student = conn.execute("""
            SELECT *
            FROM students
            WHERE id = ?
        """, (student_id,)).fetchone()

    finally:
        conn.close()

    if student is None:
        return jsonify({
            "error": "Student record not found."
        }), 404

    return jsonify(dict(student))


# ==========================================
# GET STUDENTS BY SECTION
# ==========================================

@app.route("/students/section/<section_name>", methods=["GET"])
def get_students_by_section(section_name):

    conn = get_db()

    try:
        students = conn.execute("""
            SELECT *
            FROM students
            WHERE UPPER(section) = ?
            ORDER BY id DESC
        """, (section_name.upper(),)).fetchall()

        return jsonify([
            dict(student)
            for student in students
        ])

    finally:
        conn.close()


# ==========================================
# ADD STUDENT
# POST /api/students
#
# Source defaults to External API when
# another system sends a record without it.
# Local form sends source = Local.
# ==========================================

@app.route("/api/students", methods=["POST"])
def add_student():

    data = request.get_json(silent=True)
    student, error = validate_student(data)

    if error:
        return jsonify({"error": error}), 400

    source = "External API"

    if isinstance(data, dict):
        supplied_source = data.get("source")

        if supplied_source is not None and str(supplied_source).strip():
            source = str(supplied_source).strip()[:100]

    conn = get_db()

    try:
        conn.execute("""
            INSERT INTO students
                (student_id, name, program, year, section, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            student["student_id"],
            student["name"],
            student["program"],
            student["year"],
            student["section"],
            source
        ))

        conn.commit()

        return jsonify({
            "message": "Student added successfully.",
            "source": source
        }), 201

    except sqlite3.Error:
        conn.rollback()
        app.logger.exception("Unable to add student")

        return jsonify({
            "error": "Database error while adding student."
        }), 500

    finally:
        conn.close()


# ==========================================
# STEP 5: IMPORT CLASSMATE/PARTNER RECORD
# POST /import-student
# ==========================================

@app.route("/import-student", methods=["POST"])
def import_student():

    data = request.get_json(silent=True)
    student, error = validate_student(data)

    if error:
        return jsonify({"error": error}), 400

    conn = get_db()

    try:
        existing = conn.execute("""
            SELECT id
            FROM students
            WHERE student_id = ?
            LIMIT 1
        """, (student["student_id"],)).fetchone()

        if existing:
            return jsonify({
                "error": "This Student ID already exists in your database."
            }), 409

        conn.execute("""
            INSERT INTO students
                (student_id, name, program, year, section, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            student["student_id"],
            student["name"],
            student["program"],
            student["year"],
            student["section"],
            "Classmate API"
        ))

        conn.commit()

        return jsonify({
            "message": "Remote record saved successfully!",
            "source": "Classmate API"
        }), 201

    except sqlite3.Error:
        conn.rollback()
        app.logger.exception("Unable to import student")

        return jsonify({
            "error": "Database error while importing student."
        }), 500

    finally:
        conn.close()


# ==========================================
# UPDATE STUDENT
# ==========================================

@app.route("/api/students/<int:student_id>", methods=["PUT"])
def update_student(student_id):

    data = request.get_json(silent=True)
    student, error = validate_student(data)

    if error:
        return jsonify({"error": error}), 400

    conn = get_db()

    try:
        existing = conn.execute("""
            SELECT id
            FROM students
            WHERE id = ?
        """, (student_id,)).fetchone()

        if existing is None:
            return jsonify({
                "error": "Student record not found."
            }), 404

        conn.execute("""
            UPDATE students
            SET student_id = ?,
                name = ?,
                program = ?,
                year = ?,
                section = ?
            WHERE id = ?
        """, (
            student["student_id"],
            student["name"],
            student["program"],
            student["year"],
            student["section"],
            student_id
        ))

        conn.commit()

        return jsonify({
            "message": "Student updated successfully."
        })

    except sqlite3.Error:
        conn.rollback()
        app.logger.exception("Unable to update student")

        return jsonify({
            "error": "Database error while updating student."
        }), 500

    finally:
        conn.close()


# ==========================================
# DELETE STUDENT
# ==========================================

@app.route("/api/students/<int:student_id>", methods=["DELETE"])
def delete_student(student_id):

    conn = get_db()

    try:
        result = conn.execute("""
            DELETE FROM students
            WHERE id = ?
        """, (student_id,))

        if result.rowcount == 0:
            return jsonify({
                "error": "Student record not found."
            }), 404

        conn.commit()

        return jsonify({
            "message": "Student deleted successfully."
        })

    except sqlite3.Error:
        conn.rollback()
        app.logger.exception("Unable to delete student")

        return jsonify({
            "error": "Database error while deleting student."
        }), 500

    finally:
        conn.close()


# ==========================================
# CLASSMATE RECORDS
# GET /api/classmate?url=...
# ==========================================

@app.route("/api/classmate", methods=["GET"])
def get_classmate_records():

    base_url = request.args.get("url", "").strip().rstrip("/")
    base_url = validate_partner_base_url(base_url)

    if not base_url:
        return jsonify({
            "error": "Please provide a valid HTTPS classmate API base URL."
        }), 400

    api_url = base_url + "/students"

    try:
        response = requests.get(
            api_url,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        records = normalize_student_records(response.json())

        if records is None:
            return jsonify({
                "error": "Classmate API did not return a student list."
            }), 502

        return jsonify(records)

    except requests.exceptions.Timeout:
        return jsonify({
            "error": "Classmate API request timed out."
        }), 504

    except requests.exceptions.RequestException:
        app.logger.exception("Classmate API connection failed")

        return jsonify({
            "error": "Unable to connect to Classmate API."
        }), 502

    except ValueError:
        return jsonify({
            "error": "Classmate API returned invalid JSON."
        }), 502


# ==========================================
# AUTOMATIC PARTNER RECORDS
# GET /partner-records
# ==========================================

@app.route("/partner-records", methods=["GET"])
def get_partner_records():

    try:
        response = requests.get(
            PARTNER_API_URL,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        records = normalize_student_records(response.json())

        if records is None:
            return jsonify({
                "error": "Partner API did not return a student list."
            }), 502

        return jsonify({
            "message": f"Successfully loaded {len(records)} partner record(s).",
            "students": records
        })

    except requests.exceptions.Timeout:
        return jsonify({
            "error": "Partner API request timed out. Please try again."
        }), 504

    except requests.exceptions.RequestException:
        app.logger.exception("Partner API connection failed")

        return jsonify({
            "error": (
                "Unable to connect to Partner API. "
                "The partner server may be unavailable."
            )
        }), 502

    except ValueError:
        app.logger.exception("Partner API returned invalid JSON")

        return jsonify({
            "error": "Partner API returned invalid JSON."
        }), 502


# ==========================================
# STEP 9: SEND PRACTICE RECORD TO PARTNER
# POST /send-practice-record
# ==========================================

@app.route("/send-practice-record", methods=["POST"])
def send_practice_record():

    data = request.get_json(silent=True) or {}

    base_url = validate_partner_base_url(
        str(data.get("partner_url", "")).strip().rstrip("/")
    )

    if not base_url:
        return jsonify({
            "error": "Please provide a valid HTTPS partner base URL."
        }), 400

    partner_url = base_url + "/api/students"

    practice_record = {
        "student_id": "EXT-001",
        "name": "Sample Exchange Record",
        "program": "BSIT",
        "year": 1,
        "section": "A",
        "source": "Partner API"
    }

    try:
        response = requests.post(
            partner_url,
            json=practice_record,
            headers={"Accept": "application/json"},
            timeout=15
        )

        try:
            partner_response = response.json()
        except ValueError:
            partner_response = response.text

        if not response.ok:
            return jsonify({
                "error": "Partner API rejected the practice record.",
                "partner_status": response.status_code,
                "partner_response": partner_response
            }), 502

        return jsonify({
            "message": "Practice record successfully sent to your partner!",
            "partner_status": response.status_code,
            "record": practice_record,
            "partner_response": partner_response
        }), 200

    except requests.exceptions.Timeout:
        return jsonify({
            "error": "Sending the practice record timed out."
        }), 504

    except requests.exceptions.RequestException:
        app.logger.exception("Unable to send practice record")

        return jsonify({
            "error": "Unable to connect to your partner's POST endpoint."
        }), 502


# ==========================================
# RUN FLASK APPLICATION
# ==========================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )

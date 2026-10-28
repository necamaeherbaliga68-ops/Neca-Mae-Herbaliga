
import os
import sqlite3
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError

from flask import Flask, jsonify, request, render_template

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "students.db")


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def student_data(data):
    fields = ["student_id", "name", "program", "year", "section"]

    if not isinstance(data, dict):
        return None, "Send student data as JSON."

    if any(not str(data.get(f, "")).strip() for f in fields):
        return None, "All student fields are required."

    try:
        year = int(data["year"])
        if year < 1:
            raise ValueError
    except (ValueError, TypeError):
        return None, "Year must be a positive number."

    return {
        "student_id": str(data["student_id"]).strip(),
        "name": str(data["name"]).strip(),
        "program": str(data["program"]).strip(),
        "year": year,
        "section": str(data["section"]).strip().upper()
    }, None


@app.route("/")
def home():
    return render_template("index.html")


# Sample student endpoint
@app.route("/student")
def get_student():
    return jsonify({
        "student_id": "24-00251",
        "name": "Neca Mae Herbaliga",
        "program": "BSIT",
        "year": 3,
        "section": "B"
    })


# List all records from your existing database
@app.route("/students")
def get_students():
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM students ORDER BY id"
        ).fetchall()
        return jsonify([dict(row) for row in rows])
    finally:
        conn.close()


@app.route("/students/section/<section_name>")
def get_students_by_section(section_name):
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM students WHERE UPPER(section) = ? ORDER BY id",
            (section_name.upper(),)
        ).fetchall()
        return jsonify([dict(row) for row in rows])
    finally:
        conn.close()


@app.route("/students/<int:id>")
def get_student_by_database_id(id):
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM students WHERE id = ?", (id,)
        ).fetchone()

        if row is None:
            return jsonify({"error": "Student not found"}), 404

        return jsonify(dict(row))
    finally:
        conn.close()


@app.route("/students/id/<student_id>")
def get_student_by_id(student_id):
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM students WHERE student_id = ?",
            (student_id,)
        ).fetchone()

        if row is None:
            return jsonify({"error": "Student not found"}), 404

        return jsonify(dict(row))
    finally:
        conn.close()


# CRUD API: list students
@app.route("/api/students", methods=["GET"])
def api_get_students():
    return get_students()


# CRUD API: add a student
@app.route("/api/students", methods=["POST"])
def add_student():
    data, error = student_data(request.get_json(silent=True))

    if error:
        return jsonify({"error": error}), 400

    conn = get_db_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO students
               (student_id, name, program, year, section)
               VALUES (?, ?, ?, ?, ?)""",
            (data["student_id"], data["name"], data["program"],
             data["year"], data["section"])
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM students WHERE id = ?",
            (cursor.lastrowid,)
        ).fetchone()

        return jsonify({
            "message": "Student added successfully.",
            "student": dict(row)
        }), 201

    except sqlite3.IntegrityError:
        return jsonify({"error": "Student ID already exists."}), 409
    finally:
        conn.close()


# CRUD API: get one student
@app.route("/api/students/<int:id>", methods=["GET"])
def api_get_student(id):
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM students WHERE id = ?", (id,)
        ).fetchone()

        if row is None:
            return jsonify({"error": "Student not found"}), 404

        return jsonify(dict(row))
    finally:
        conn.close()


# CRUD API: update a student
@app.route("/api/students/<int:id>", methods=["PUT"])
def update_student(id):
    data, error = student_data(request.get_json(silent=True))

    if error:
        return jsonify({"error": error}), 400

    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM students WHERE id = ?", (id,)
        ).fetchone()

        if existing is None:
            return jsonify({"error": "Student not found"}), 404

        conn.execute(
            """UPDATE students
               SET student_id = ?, name = ?, program = ?,
                   year = ?, section = ?
               WHERE id = ?""",
            (data["student_id"], data["name"], data["program"],
             data["year"], data["section"], id)
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM students WHERE id = ?", (id,)
        ).fetchone()

        return jsonify({
            "message": "Student updated successfully.",
            "student": dict(row)
        })

    except sqlite3.IntegrityError:
        return jsonify({"error": "Student ID already exists."}), 409
    finally:
        conn.close()


# CRUD API: delete a student
@app.route("/api/students/<int:id>", methods=["DELETE"])
def delete_student(id):
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM students WHERE id = ?", (id,)
        )
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "Student not found"}), 404

        return jsonify({"message": "Student deleted successfully."})
    finally:
        conn.close()


# Read-only proxy for a classmate's deployed API.
# The classmate's database is never modified.
@app.route("/api/classmate")
def get_classmate_records():
    base_url = request.args.get("url", "").strip().rstrip("/")

    try:
        parsed = urlparse(base_url)

        if parsed.scheme != "https" or not parsed.hostname:
            return jsonify({
                "error": "Enter a valid HTTPS deployed API URL."
            }), 400

        if parsed.username or parsed.password:
            return jsonify({"error": "Credentials in URLs are not allowed."}), 400

        if parsed.port not in (None, 443):
            return jsonify({"error": "Only standard HTTPS URLs are allowed."}), 400

        # Only allow the classmate's read-only student list endpoint.
        endpoint = base_url + "/api/students"

        req = Request(
            endpoint,
            headers={"Accept": "application/json",
                     "User-Agent": "Student-API-Interface"}
        )

        with urlopen(req, timeout=10) as response:
            if response.status != 200:
                return jsonify({"error": "Classmate API request failed."}), 502

            import json
            data = json.loads(response.read().decode("utf-8"))

        if isinstance(data, list):
            return jsonify(data)

        if isinstance(data, dict) and isinstance(data.get("students"), list):
            return jsonify(data["students"])

        return jsonify({
            "error": "The classmate API did not return a student list."
        }), 502

    except HTTPError as error:
        return jsonify({
            "error": "Classmate API returned HTTP " + str(error.code)
        }), 502
    except (URLError, TimeoutError, ValueError, OSError):
        return jsonify({
            "error": "Unable to connect to the classmate API."
        }), 502


@app.route("/hello")
def say_hello():
    name = request.args.get("name", "Student")
    return jsonify({"message": f"Hello, {name}!"})


@app.route("/skills")
def skills():
    return jsonify({
        "skills": [
            "HTML", "CSS", "JavaScript", "Python",
            "Flask", "Database Management"
        ]
    })


if __name__ == "__main__":
    app.run(debug=True)

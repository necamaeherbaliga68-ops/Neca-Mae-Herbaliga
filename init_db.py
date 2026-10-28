
import sqlite3

conn = sqlite3.connect("students.db")
cursor = conn.cursor()

# Create students table
cursor.execute("""
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    name TEXT NOT NULL,
    program TEXT NOT NULL,
    year INTEGER NOT NULL,
    section TEXT NOT NULL
)
""")

# Insert sample records only if the table is empty
count = cursor.execute(
    "SELECT COUNT(*) FROM students"
).fetchone()[0]

if count == 0:
    students = [
        ("24-00251", "Neca Mae Herbaliga", "BSIT", 3, "B"),
        ("24-00347", "Kate Ashley Distura", "BSIT", 3, "B"),
        ("24-00194", "Raveen Emmanuel Celo", "BSIT", 3, "A"),
        ("24-0087", "KC Jane Marie Ladoing", "BSIT", 3, "B"),
        ("24-0146", "Gwyneth Joy Laud", "BSIT", 3, "B")
    ]

    cursor.executemany("""
    INSERT INTO students
    (student_id, name, program, year, section)
    VALUES (?, ?, ?, ?, ?)
    """, students)

    conn.commit()
    print("Five student records inserted.")
else:
    print("Student records already exist.")

conn.close()
print("Database initialized successfully.")

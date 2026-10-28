
import sqlite3

conn = sqlite3.connect("students.db")

conn.execute("""
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    program TEXT NOT NULL,
    year INTEGER NOT NULL,
    section TEXT NOT NULL
)
""")

students = [
    ("24-00251", "Neca Mae Herbaliga", "BSIT", 3, "B"),
    ("24-00347", "Kate Ashley Distura", "BSIT", 3, "B"),
    ("24-00194", "Raveen Emmanuel Celo", "BSIT", 3, "A"),
    ("24-0087", "KC Jane Marie Ladoing", "BSIT", 3, "B"),
    ("24-00146", "Gwyneth Joy Laud", "BSIT", 3, "B")
]

conn.executemany("""
INSERT OR IGNORE INTO students
(student_id, name, program, year, section)
VALUES (?, ?, ?, ?, ?)
""", students)

conn.commit()
conn.close()

print("Database initialized successfully!")

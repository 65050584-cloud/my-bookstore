import sqlite3

conn = sqlite3.connect("books.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS books(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    author TEXT,
    price INTEGER,
    description TEXT
)
""")

books = [
    ("Python 101", "John Doe", 250, "พื้นฐาน Python"),
    ("Flask Web", "Jane Smith", 300, "สร้างเว็บด้วย Flask")
]

c.executemany(
    "INSERT INTO books(title,author,price,description) VALUES(?,?,?,?)",
    books
)

conn.commit()
conn.close()

print("สร้างฐานข้อมูลเสร็จแล้ว")

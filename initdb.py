import sqlite3

db = sqlite3.connect("forum1.db")
sql = """
        CREATE TABLE users (
            id  INTEGER PRIMARY KEY AUTOINCREMENT,
            login varchar(32),
            password varchar(32),
            administrator boolean
        );
        """
cursor = db.cursor()
cursor.execute(sql)

sql = """
        CREATE TABLE threads (
            id  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            date INTEGER
        );
    """
cursor = db.cursor()
cursor.execute(sql)

sql = """
        CREATE TABLE posts (
            id  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            thread_id INTEGER,
            text TEXT,
            date INTEGER
        );
    """
cursor = db.cursor()
cursor.execute(sql)

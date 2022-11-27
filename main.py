import flask
from flask import Flask, jsonify, request, session
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.secret_key = "HELLO, IT IS A BIG SECRET"


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kws):
        if ("user" not in session) or (session["user"] is None) or ("login" not in session["user"]):
            return jsonify({"result": "error", "message": "access denied"}), 403

        login = session["user"]["login"]
        return f(login, *args, **kws)
    return decorated_function


def get_db():
    return sqlite3.connect("forum.db")


def get_cursor():
    db = get_db()
    return db.cursor()


@app.route("/")
def send_default():
    return flask.send_file('html/index.html')


@app.route("/users/", methods=["POST"])
def create_user():
    db = get_db()
    login = request.form.get("login")
    password = request.form.get("password")
    if login is None or password is None or login.strip() == "" or password.strip() == "":
        return jsonify({"result": "error", "message": "invalid login or password"}), 422

    cursor = db.cursor()
    cursor.execute("SELECT login FROM users WHERE login=?", (login,))
    result = cursor.fetchone()
    cursor.close()
    if result:
        return jsonify({"result": "error", "message": "already exists"}), 409

    pwd_hash = generate_password_hash(password)
    cursor = db.cursor()
    cursor.execute("INSERT INTO users (login, password) VALUES(?, ?)", (login, pwd_hash))
    cursor.close()
    db.commit()
    return jsonify({
        "result": "ok",
        "message": "user created",
    })


@app.route("/users/me")
@login_required
def userinfo(login):
    return jsonify(session["user"])


@app.route("/users/<user_id>")
def get_user(user_id):
    cursor = get_cursor()
    cursor.execute("SELECT id, login FROM users WHERE id=?", (user_id,))
    result = cursor.fetchone()
    cursor.close()
    if result is None:
        return jsonify({"result": "error", "message": "user not found"}), 404

    return jsonify({"result": "ok", "user": {
        "id": result[0],
        "login": result[1],
    }})


def get_users(user_ids):
    sql = "SELECT id, login FROM users WHERE id IN ({seq})".format(seq=",".join(['?'] * len(user_ids)))
    cursor = get_cursor()
    cursor.execute(sql, user_ids)
    users = []
    for r in cursor.fetchall():
        users.append({
            "id": r[0],
            "login": r[1],
        })
    cursor.close()
    return users


@app.route("/login", methods=["POST"])
def login():
    login = request.form.get("login")
    password = request.form.get("password")

    cursor = get_cursor()
    cursor.execute("SELECT id, login, password FROM users WHERE login=?", (login,))
    result = cursor.fetchone()
    cursor.close()

    if not result or not check_password_hash(result[2], password):
        return jsonify({"result": "error", "message": "invalid login or password"}), 401

    session["user"] = {
        "id": result[0],
        "login": result[1],
    }
    return jsonify({"result": "ok", "message": "user authorized"})


@app.route("/logout")
def logout():
    session["user"] = None
    return jsonify({"result": "ok", "message": "logged out"})


@app.route("/threads/")
def list_threads():
    cursor = get_cursor()
    cursor.execute("SELECT id, user_id, title, date FROM threads ORDER BY date desc")
    result = cursor.fetchall()
    cursor.close()
    threads = []
    user_ids = []
    for r in result:
        threads.append({
            'id': r[0],
            'user_id': r[1],
            'title': r[2],
            'date': r[3]
        })
        if r[1] not in user_ids:
            user_ids.append(r[1])
    return jsonify({"result": "ok", "threads": threads, "users": get_users(user_ids)})


@app.route("/threads/", methods=["POST"])
@login_required
def create_thread(login):
    title = request.form.get("title")
    text = request.form.get("text")

    if title is None or title.strip() == "":
        return jsonify({"result": "error", "message": "title is required"}), 422

    if text is None or text.strip() == "":
        return jsonify({"result": "error", "message": "text is required"}), 422

    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO threads (user_id, title, date) VALUES (?, ?, CURRENT_TIMESTAMP)",
                   (session["user"]["id"], title))
    thread_id = cursor.lastrowid
    cursor.execute("INSERT INTO posts (user_id, thread_id, text, date) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                   (session["user"]["id"], thread_id, text))
    cursor.close()
    db.commit()
    db.close()
    return get_thread(thread_id)


@app.route("/threads/<thread_id>")
def get_thread(thread_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, user_id, title, date FROM threads WHERE id = ?", (thread_id, ))
    thread = cursor.fetchone()
    if thread is None:
        return jsonify({"result": "error", "message": "thread not found"}), 404

    cursor.execute("SELECT id, user_id, thread_id, text, date FROM posts WHERE thread_id = ? ORDER BY date",
                   (thread_id,))
    posts_raw = cursor.fetchall()
    response = {
        "result": "ok",
        "thread": {
            "id": thread[0],
            "user_id": thread[1],
            "title": thread[2],
            "date": thread[3],
        },
        "posts": [],
        "users": [],
    }
    user_ids = [thread[1]]
    for post in posts_raw:
        response["posts"].append({
            "id": post[0],
            "user_id": post[1],
            "thread_id": post[2],
            "text": post[3],
            "date": post[4],
        })
        if post[1] not in user_ids:
            user_ids.append(post[1])

    response["users"] = get_users(user_ids)
    return response


@app.route("/posts/", methods=["POST"])
@login_required
def create_post(login):
    thread_id = request.form.get("thread_id")
    text = request.form.get("text")
    if text is None or text.strip() == "":
        return jsonify({"result": "error", "message": "text is required"}), 422

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM threads WHERE id=?", (thread_id, ))
    result = cursor.fetchone()
    if result is None:
        return jsonify({"result": "error", "message": "thread not found"}), 404

    cursor.execute("INSERT INTO posts (user_id, thread_id, text, date) VALUES(?, ?, ?, current_timestamp)",
                   (session["user"]["id"], thread_id, text))
    # post_id = cursor.lastrowid
    cursor.close()
    db.commit()
    db.close()

    return get_thread(thread_id)

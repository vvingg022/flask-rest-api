import json
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, url_for
from werkzeug.exceptions import HTTPException

app = Flask(__name__)

# Refuse request bodies over 1 MiB (Flask answers 413 by itself).
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

RECEIVED_FILE = Path(__file__).parent / "received.bin"

USERS = {1: "john", 2: "steve", 3: "bill"}


# ---------------- STEP 1: routes ----------------

@app.route("/")
def api_root():
    return "Welcome\n"


@app.route("/articles")
def api_articles():
    return "List of " + url_for("api_articles") + "\n"


@app.route("/articles/<int:articleid>")
def api_article(articleid):
    return f"You are reading {articleid}\n"


# ---------------- STEP 2: query parameters and verbs ----------------

@app.route("/hello")
def api_hello():
    name = request.args.get("name", "John Doe")
    return f"Hello {name}\n"


@app.route("/echo", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
def api_echo():
    return f"ECHO: {request.method}\n"


# ---------------- STEP 3: request data and headers ----------------

@app.route("/headers")
def api_headers():
    return jsonify(dict(request.headers))


@app.route("/messages", methods=["POST"])
def api_message():
    if request.mimetype == "text/plain":
        return "Text Message: " + request.get_data(as_text=True) + "\n"

    if request.mimetype == "application/json":
        data = request.get_json()
        return "JSON Message: " + json.dumps(data) + "\n"

    if request.mimetype == "application/octet-stream":
        data = request.get_data()
        RECEIVED_FILE.write_bytes(data)
        return f"Binary message written! ({len(data)} bytes)\n"

    abort(415)   # STEP 4 change: a real 415 error, handled below


# ---------------- STEP 4: responses, status codes, errors ----------------

@app.route("/hello-manual")
def api_hello_manual():
    """Build the response by hand, the long way."""
    data = {"hello": "world", "number": 3}
    resp = Response(json.dumps(data), status=200, mimetype="application/json")
    resp.headers["Link"] = '</articles>; rel="related"'
    return resp


@app.route("/hello-json")
def api_hello_json():
    """The same response using jsonify, the short way."""
    resp = jsonify({"hello": "world", "number": 3})
    resp.status_code = 200
    resp.headers["Link"] = '</articles>; rel="related"'
    return resp


@app.route("/users/<int:userid>")
def api_user(userid):
    if userid not in USERS:
        abort(404, description=f"No user with id {userid}")
    return jsonify({"id": userid, "name": USERS[userid]})


@app.errorhandler(HTTPException)
def handle_http_error(error):
    """Turn every HTTP error (404, 405, 413, 415, ...) into JSON."""
    response = error.get_response()   # keeps headers such as Allow on a 405
    response.data = json.dumps({
        "status": error.code,
        "error": error.name,
        "message": error.description,
        "path": request.path,
    })
    response.content_type = "application/json"
    return response


if __name__ == "__main__":
    app.run(debug=True, port=8000)
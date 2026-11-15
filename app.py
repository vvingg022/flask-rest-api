import hmac
import json
import logging
import os
from functools import wraps
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, url_for
from werkzeug.exceptions import HTTPException

app = Flask(__name__)

# Refuse request bodies over 1 MiB (Flask answers 413 by itself).
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

RECEIVED_FILE = Path(__file__).parent / "received.bin"
LOG_FILE = Path(__file__).parent / "app.log"

USERS = {1: "john", 2: "steve", 3: "bill"}

# Demo credentials. Real ones come from environment variables if set.
AUTH_USERNAME = os.environ.get("API_USERNAME", "admin")
AUTH_PASSWORD = os.environ.get("API_PASSWORD", "secret")


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

    abort(415)


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


# ---------------- STEP 5: basic authentication ----------------

def check_auth(username, password):
    """Compare credentials in constant time, so response timing
    doesn't leak how many characters were correct."""
    user_ok = hmac.compare_digest(username.encode("utf-8"), AUTH_USERNAME.encode("utf-8"))
    pass_ok = hmac.compare_digest(password.encode("utf-8"), AUTH_PASSWORD.encode("utf-8"))
    return user_ok and pass_ok


def authenticate():
    """A 401 reply that tells the client how to log in."""
    resp = jsonify({
        "status": 401,
        "error": "Unauthorized",
        "message": "Authenticate.",
        "path": request.path,
    })
    resp.status_code = 401
    resp.headers["WWW-Authenticate"] = 'Basic realm="Example"'
    return resp


def requires_auth(f):
    """Decorator: only run the route function if valid Basic credentials came in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if (
            auth is None
            or auth.type != "basic"
            or not check_auth(auth.username or "", auth.password or "")
        ):
            # STEP 6: log the failure, but never the password itself.
            app.logger.warning("Rejected auth attempt on %s from %s", request.path, request.remote_addr)
            return authenticate()

        return f(*args, **kwargs)

    return decorated


@app.route("/secrets")
@requires_auth
def api_secrets():
    return "Shhh this is top secret spy stuff!\n"


# ---------------- STEP 6: logging ----------------

def configure_logging(flask_app):
    """Log to the console and to app.log."""
    flask_app.logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    flask_app.logger.addHandler(file_handler)


@app.after_request
def log_request(response):
    app.logger.info("%s %s -> %s", request.method, request.path, response.status_code)
    return response


@app.route("/logging-demo")
def api_logging_demo():
    app.logger.info("informing")
    app.logger.warning("warning")
    app.logger.error("screaming bloody murder!")
    return "check your logs\n"


if __name__ == "__main__":
    configure_logging(app)
    app.run(debug=True, port=8000)
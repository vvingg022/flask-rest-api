import base64

import pytest

import app as app_module


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client


def basic_auth(username, password):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


# ---------- Step 1: routes ----------

def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Welcome" in r.data


def test_article_with_number(client):
    r = client.get("/articles/123")
    assert r.status_code == 200
    assert b"123" in r.data


def test_article_with_text_is_404(client):
    assert client.get("/articles/abc").status_code == 404


# ---------- Step 2: query parameters and verbs ----------

def test_hello_default(client):
    assert client.get("/hello").get_data(as_text=True) == "Hello John Doe\n"


def test_hello_with_name(client):
    assert client.get("/hello?name=Luis").get_data(as_text=True) == "Hello Luis\n"


@pytest.mark.parametrize("method", ["get", "post", "put", "patch", "delete"])
def test_echo_verbs(client, method):
    r = getattr(client, method)("/echo")
    assert r.get_data(as_text=True) == f"ECHO: {method.upper()}\n"


def test_wrong_method_is_405_json(client):
    r = client.post("/hello")
    assert r.status_code == 405
    assert "GET" in r.headers["Allow"]
    assert r.get_json()["status"] == 405


# ---------- Step 3: request data and headers ----------

def test_headers_route_shows_custom_header(client):
    r = client.get("/headers", headers={"X-Tag": "hello"})
    assert r.get_json()["X-Tag"] == "hello"


def test_text_message(client):
    r = client.post("/messages", data="Hello Text", content_type="text/plain")
    assert r.get_data(as_text=True) == "Text Message: Hello Text\n"


def test_json_message(client):
    r = client.post("/messages", json={"message": "Hello Data"})
    assert r.get_data(as_text=True) == 'JSON Message: {"message": "Hello Data"}\n'


def test_broken_json_is_400(client):
    r = client.post("/messages", data="{oops", content_type="application/json")
    assert r.status_code == 400
    assert r.get_json()["status"] == 400


def test_binary_message_is_saved(client, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "RECEIVED_FILE", tmp_path / "received.bin")
    payload = bytes(range(256))
    r = client.post("/messages", data=payload, content_type="application/octet-stream")
    assert r.status_code == 200
    assert (tmp_path / "received.bin").read_bytes() == payload


def test_unsupported_content_type_is_415(client):
    r = client.post("/messages", data={"a": "b"})
    assert r.status_code == 415


def test_oversized_body_is_413(client):
    big = b"a" * (1024 * 1024 + 1)
    r = client.post("/messages", data=big, content_type="application/octet-stream")
    assert r.status_code == 413


# ---------- Step 4: responses and errors ----------

@pytest.mark.parametrize("path", ["/hello-manual", "/hello-json"])
def test_hello_json_routes_match(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert r.get_json() == {"hello": "world", "number": 3}
    assert r.headers["Link"] == '</articles>; rel="related"'


def test_existing_user(client):
    assert client.get("/users/2").get_json() == {"id": 2, "name": "steve"}


def test_missing_user_is_json_404(client):
    r = client.get("/users/4")
    assert r.status_code == 404
    assert r.get_json()["message"] == "No user with id 4"


def test_unknown_url_returns_json(client):
    r = client.get("/nothing")
    assert r.status_code == 404
    assert r.content_type.startswith("application/json")


# ---------- Step 5: authentication ----------

def test_secrets_without_login_is_401(client):
    r = client.get("/secrets")
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == 'Basic realm="Example"'


def test_secrets_with_right_login(client):
    headers = basic_auth(app_module.AUTH_USERNAME, app_module.AUTH_PASSWORD)
    r = client.get("/secrets", headers=headers)
    assert r.status_code == 200
    assert b"top secret" in r.data


def test_secrets_with_wrong_password(client):
    r = client.get("/secrets", headers=basic_auth(app_module.AUTH_USERNAME, "wrong"))
    assert r.status_code == 401


def test_secrets_with_bearer_token_is_401(client):
    r = client.get("/secrets", headers={"Authorization": "Bearer abc123"})
    assert r.status_code == 401


# ---------- Step 6: logging ----------

def test_logging_demo_route(client):
    r = client.get("/logging-demo")
    assert r.status_code == 200
    assert b"check your logs" in r.data
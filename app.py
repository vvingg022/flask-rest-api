from flask import Flask, url_for

app = Flask(__name__)


@app.route("/")
def api_root():
    return "Welcome\n"


@app.route("/articles")
def api_articles():
    return "List of " + url_for("api_articles") + "\n"


@app.route("/articles/<int:articleid>")
def api_article(articleid):
    return f"You are reading {articleid}\n"


if __name__ == "__main__":
    app.run(debug=True, port=8000)
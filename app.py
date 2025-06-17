from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("form.html")

@app.route("/submit", methods=["POST"])
def submit():
    data = request.form.to_dict()
    print("✅ Received data from form:", data)
    return "Thanks!", 200

if __name__ == "__main__":
    app.run(port=8000)

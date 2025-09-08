from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_cors import CORS
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import bcrypt
import pickle

app = Flask(__name__)
app.secret_key = "your_secret_key"  # needed for sessions
CORS(app)

# ---------------- MongoDB Connection ---------------- #
client = MongoClient("mongodb://localhost:27017/")
db = client["fraud_news_db"]
users_collection = db["users"]
history_collection = db["history"]

# ---------------- Load ML Model ---------------- #
with open("kb.pkl", "rb") as model_file:
    model, vectorizer = pickle.load(model_file)

# ---------------- Routes ---------------- #

@app.route("/")
def home():
    return render_template("home.html")

# -------- Register -------- #
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]
        print(username,password)

        if users_collection.find_one({"username": username}):
            flash("Email already exists! Try login.")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password)
        users_collection.insert_one({
            "name": name,
            "email": email,
            "username":username,
            "password": hashed_pw
        })
        flash("Registration successful! Please login.")
        return redirect(url_for("login"))

    return render_template("register.html")

# -------- Login -------- #
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = users_collection.find_one({"username": username})
        if user and check_password_hash(user["password"], password):
            session["username"] = username
            flash("Login successful!")
            return redirect("/news")
        else:
            flash("Invalid email or password!")

    return render_template("login.html")

# -------- Dashboard -------- #
@app.route("/")
def dashboard():
    return render_template("home.html")
@app.route("/about")
def about():
    return render_template("about.html")
@app.route("/contact")
def contact():
    return render_template("contact.html")

# -------- Detect News -------- #
@app.route("/news", methods=["GET", "POST"])
def detect():
    if "username" not in session:
        return redirect(url_for("login"))

    result = None
    confidence = None

    if request.method == "POST":
        news_text = request.form["news"]

        vectorized_text = vectorizer.transform([news_text])
        prediction = model.predict(vectorized_text)[0]
        confidence = max(model.predict_proba(vectorized_text)[0]) * 100
        result = "Fake" if prediction == 1 else "Real"

        history_collection.insert_one({
            "username": session["username"],   # ✅ Save who submitted
            "news": news_text,
            "result": result,
            "confidence": round(confidence, 2)
        })
        history = list(
        history_collection.find({"username": session["username"]})
        .sort("_id", -1)  # newest first
        .limit(5)
        )

        # ⚡ Don’t redirect — return template with result
        return render_template("news.html", result=result, confidance=round(confidence, 2))

    return render_template("news.html", result=result, confidance=confidence)
from datetime import datetime

# Contact + Dashboard view
@app.route("/contact", methods=["GET"])
def contact_dashboard():
    if "username" not in session:
        return redirect(url_for("login"))

    # Fetch comments
    comments = list(db["comments"].find({"username": session["username"]}).sort("date", -1))
    comments = [{"text": c["text"], "date": c["date"].strftime("%d %b %Y, %H:%M")} for c in comments]

    # Fetch news check history
    history = list(db["history"].find({"username": session["username"]}).sort("date", -1))
    history = [{"news": h["news"], "result": h["result"], "confidence": h["confidence"]} for h in history]

    return render_template("contact.html", comments=comments, history=history)

# Save comment from contact dashboard
@app.route("/contact/comment", methods=["POST"])
def contact_comment():
    if "username" not in session:
        return redirect(url_for("login"))

    comment_text = request.form["comment"]
    db["comments"].insert_one({
        "username": session["username"],
        "text": comment_text,
        "date": datetime.now()
    })
    flash("Comment added successfully!")
    return redirect(url_for("contact_dashboard"))


# -------- Logout -------- #
@app.route("/logout")
def logout():
    session.pop("email", None)
    flash("You have been logged out.")
    return redirect(url_for("login"))

# ---------------- Run Flask ---------------- #
if __name__ == "__main__":
    app.run(debug=True)

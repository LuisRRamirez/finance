import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    rows = db.execute("SELECT * FROM Data WHERE User_id =:User_id", User_id = user_id)
    rows1 = len(rows)
    cashstock = 0
    for i in range(rows1):
        symbol = rows[i]["Symbol"]
        quotes = lookup(symbol)

        stock = {"price": usd(quotes["price"])}
        cashstock = cashstock + ( float(stock["price"].replace('$','')) * rows[i]["Shares"] )

        db.execute("UPDATE Data SET Prices=:newprice WHERE (User_id=:user_id AND Symbol=:symbol) ", newprice=stock["price"], user_id = session["user_id"] , symbol=symbol)

    rows2 = db.execute("SELECT * FROM users WHERE id = :id", id = user_id)
    cash = round(rows2[0]["cash"], 2)
    cashstocks = round(cashstock + cash, 2)

    return render_template("index.html", rows=rows, cash=cash, cashstocks = cashstocks)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("must provide a number", 400)

        if shares < 0:
            return apology("must provide positive integer", 400)

        symbol = request.form.get("symbol").upper()
        quotes = lookup(symbol)

        if quotes is None:
            return apology("invalid symbol", 400)

        stock = {"name": quotes["name"],
            "symbol": quotes["symbol"],
            "price": usd(quotes["price"])}

        cost = quotes["price"]
        total = round(cost * shares, 2)
        user_id = session["user_id"]

        rows = db.execute("SELECT * FROM users WHERE id = :id", id = user_id)
        cash = round(rows[0]["cash"], 2)
        if total > cash:
            return apology("insufficent funds", 400)

        remainder = round(cash - total, 2)
        trade = 'Bought'

        rows1 = db.execute("SELECT * FROM Data WHERE User_Id=:id AND Symbol=:symbol", id = user_id, symbol = symbol)

        if len(rows1) == 1:
            newshares = int(rows1[0]['Shares']) + int(shares)
            db.execute("UPDATE Data SET Shares=:newshares WHERE User_Id=:id AND Symbol=:symbol", id = user_id, symbol = symbol, newshares=newshares)

        else:
            db.execute("INSERT INTO Data (User_Id, Remaining, Shares, Symbol, Names, Prices, PWP) VALUES (:user_id, :remainder, :shares, :symbols, :names, :prices, :pwp)", user_id = session["user_id"], remainder=remainder, shares=shares, pwp=total, names=stock["name"], symbols=stock["symbol"], prices=stock["price"])

        db.execute("INSERT INTO History (Symbol, Shares , Price, User_Id, Trade) VALUES (  :symbols, :shares, :prices, :user_id, :trade)", user_id = session["user_id"], shares=shares, prices=stock["price"], symbols=stock["symbol"], trade=trade)
        db.execute("UPDATE users SET cash=:remainder WHERE id=:user_id", remainder=remainder, user_id = session["user_id"])

        return render_template("bought.html", names=stock["name"],
                                            symbols=stock["symbol"],
                                            prices=stock["price"],
                                            shares=shares,
                                            total=total,
                                            remainder=remainder)

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():

    user_id = session["user_id"]
    rows = db.execute("SELECT * FROM History WHERE User_Id =:User_id", User_id = user_id)

    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        symbol = request.form.get("symbol").upper()
        quotes = lookup(symbol)

        if quotes is None:
            return apology("invalid symbol", 400)

        stock = {"name": quotes["name"],
            "symbol": quotes["symbol"],
            "price": usd(quotes["price"])}

        return render_template("quoted.html", names=stock["name"], symbols=stock["symbol"], prices=stock["price"])

    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        if not request.form.get("username"):
            return apology("must provide username", 400)

        elif not request.form.get("password"):
            return apology("must provide password", 400)

        elif request.form['password'] != request.form['confirmation']:
            return apology("password and confirmation password do not match", 400)

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        if len(rows) != 0:
            return apology("username already exists", 400)

        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",username=request.form.get("username"), hash=generate_password_hash(request.form.get("password")))

        return redirect("/login")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")




@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    user_id = session["user_id"]
    rows = db.execute("SELECT * FROM Data WHERE User_id =:User_id", User_id = user_id)
    rows1 = db.execute("SELECT * FROM users WHERE id=:User_id", User_id = user_id)
    rows2 = len(rows)

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        try:
            requestshares = int(request.form.get("shares"))
        except ValueError:
            return apology("must provide a number", 400)

        if requestshares < 0:
            return apology("Must insert a positive integer", 400)


        for i in range(rows2):

            shares = rows[i]["Shares"]
            symbol = rows[i]["Symbol"]
            PWP = rows[i]["PWP"]

            if symbol == (request.form.get("symbol")):

                quotes = lookup(symbol)
                stock = {"symbol": quotes["symbol"],
                    "price": usd(quotes["price"])}

                if requestshares > shares:
                    return apology("Insufficent Shares", 400)

                sharesworth = requestshares * float(stock["price"].replace('$',''))
                cash = round(rows1[0]["cash"], 2)
                cash = cash + sharesworth
                PWP  = round(PWP - sharesworth, 2)
                shares = shares - requestshares
                trade = 'Sold'

                db.execute("INSERT INTO History (Symbol, Shares , Price, User_Id, Trade) VALUES (  :symbols, :shares, :prices, :user_id, :trade)", user_id = session["user_id"], shares=requestshares, prices=stock["price"], symbols=stock["symbol"], trade=trade)
                db.execute("DELETE FROM Data WHERE Shares = 0 AND User_id = :userid", userid=session["user_id"] )
                db.execute("UPDATE Data SET Shares=:shares WHERE (User_id=:user_id AND Symbol=:symbol) ", shares=shares, symbol=symbol, user_id = session["user_id"])
                db.execute("UPDATE users SET cash=:cash WHERE id=:user_id", cash=cash, user_id = session["user_id"])
                db.execute("UPDATE Data SET PWP=:PWP WHERE (User_id=:user_id AND Symbol=:symbol) ", PWP=PWP, symbol=symbol, user_id = session["user_id"])

                return redirect("/")
    else:
        return render_template("sell.html", rows=rows)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

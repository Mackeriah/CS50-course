import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

# might not need this
import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # get user id
    user_id = session["user_id"]

    # get user transaction information (history?)
    transactions_db = db.execute("SELECT symbol, SUM(shares) AS shares, price FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)

    # get user current cash amount
    cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    # get cash amount from dictionary
    cash = cash_db[0]["cash"]

    return render_template("index.html", database = transactions_db, cash = cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")

    else:
        symbol = request.form.get("symbol")

        shares = request.form.get("shares")
        if not shares.isdigit():
            return apology("You cannot purchase partial shares.")


        # cast to int otherwise it'll be handled as text?
        shares = int(request.form.get("shares"))

        # check that user entered a symbol
        if not symbol:
            return apology("No symbol entered")

        # store in variable
        stock = lookup(symbol.upper())

        # check API to see if symbol exists
        if stock == None:
            return apology("Symbol not found")

        # check that share is a positive int
        if shares <= 0:
            return apology("Share cannot be zero or negative")

        # check if user cannot afford shares at current price
        # store transaction value
        transaction_value = shares * stock["price"]

        # get currently signed in user id
        user_id = session["user_id"]

        # store users current cash balance
        # :id can be changed to ?
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = :id", id=user_id)
        user_cash = user_cash_db[0]["cash"]

        # check if user has enough!
        if user_cash < transaction_value:
            return apology("Insufficient funds")

        # update tables with user's purchase
        update_user_balance = user_cash - transaction_value
        # update user table
        db.execute("UPDATE users SET cash = ? WHERE id = ?", update_user_balance, user_id)
        # update transaction table

        # get date and time of stock purchase
        date = datetime.datetime.now()
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date) VALUES (?, ?, ?, ?, ?)", user_id, stock["symbol"], shares, stock["price"], date)

        # let user know successful transfer
        flash("Share purchased!")

        # return user to home
        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # get user id
    user_id = session["user_id"]
    transactions_db = db.execute("SELECT * FROM transactions WHERE user_id = :id", id=user_id)
    return render_template("history.html", transactions = transactions_db)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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
    """Get stock quote."""
    # return quote.html on GET
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")

        # check that user entered a symbol
        if not symbol:
            return apology("No symbol entered")

        # store in variable
        stock = lookup(symbol.upper())

        # check API to see if symbol exists
        if stock == None:
            return apology("Symbol not found")

        # if it is found include in quoted
        return render_template("quoted.html", name = stock["name"], price = stock["price"], symbol = stock["symbol"])

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # If request via GET
    if request.method == "GET":
        return render_template("register.html")

    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # handle blank username
        if not username:
            return apology("Username required")

        # handle blank password
        if not password:
            return apology("Password cannot be blank")

        # if confirmation password blank
        if not confirmation:
            return apology("Confirmation password cannot be blank")

        # check if passwords don't match
        if password != confirmation:
            return apology("Passwords must match")

        # hash password for registration
        passwordHash = generate_password_hash(password)

        # add user to DB as per https://docs.python.org/3/tutorial/errors.html
        try:
            new_user = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, passwordHash)
            return redirect("/")

        # check if username already exists in DB
        except:
            return apology("User already registered!")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        user_id = session["user_id"]
        symbols_user = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0", user_id)
        return render_template("sell.html", symbols = [row["symbol"] for row in symbols_user])

    else:
        symbol = request.form.get("symbol")
        # cast to int otherwise it'll be handled as text?
        shares = int(request.form.get("shares"))

        # check that user entered a symbol
        if not symbol:
            return apology("No symbol entered")

        # store in variable
        stock = lookup(symbol.upper())

        # check API to see if symbol exists
        if stock == None:
            return apology("Symbol not found")

        # check that share is a positive int
        if shares < 0:
            return apology("Share cannot be zero or negative")

        # check if user cannot afford shares at current price
        # store transaction value
        transaction_value = shares * stock["price"]

        # get currently signed in user id
        user_id = session["user_id"]

        # store users current cash balance
        # :id can be changed to ?
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = :id", id=user_id)
        user_cash = user_cash_db[0]["cash"]

        # retrive shares user owns
        # getUserOwnedShares = db.execute("SELECT shares FROM transactions WHERE user_id=:id AND symbol = :symbol GROUP BY symbol", id=user_id, symbol=symbol)
        getUserOwnedShares = db.execute("SELECT SUM(shares) AS shares FROM transactions WHERE user_id=:id AND symbol = :symbol GROUP BY symbol", id=user_id, symbol=symbol)
        userOwnedShares = getUserOwnedShares[0]["shares"]

        if shares > userOwnedShares:
            return apology("Insufficent number of shares owned")

        # update tables with user's purchase
        update_user_balance = user_cash + transaction_value

        # update user table
        db.execute("UPDATE users SET cash = ? WHERE id = ?", update_user_balance, user_id)
        # update transaction table

        # get date and time of stock purchase
        date = datetime.datetime.now()
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date) VALUES (?, ?, ?, ?, ?)", user_id, stock["symbol"], (-1)*shares, stock["price"], date)

        # let user know successful transfer
        flash("Share sold!")

        # return user to home
        return redirect("/")
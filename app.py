import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

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
    # collect current user's id
    user_id = session["user_id"]

    # queries to collect user's cash and information about all stocks owned
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
    stocks = db.execute(
        "SELECT symbol, price, name, SUM(shares) as shares FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)

    # calculating total cash owned for each stock
    total = cash

    for stock in stocks:
        total += stock["shares"] * stock["price"]
    # rendering index template, passing through certain variables
    return render_template("index.html", cash=cash, stocks=stocks, total=total, usd=usd)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # checking whether method is POST or GET
    if request.method == "GET":
        # rendering buy template
        return render_template("buy.html")
    else:
        # collecting text input from buy template
        symbol = request.form.get("symbol").upper()
        # looking up the symbol using lookup function
        stock = lookup(symbol)

        # if no symbol is entered
        if not symbol:
            return apology("No symbol was entered")
        # if symbol is invalid
        elif not stock:
            return apology("Invalid symbol")
        # trying to get the shares from buy template
        try:
            share = int(request.form.get("shares"))
        except:
            # if shares weren't entered
            return apology("Enter a number")

        # check if chare is 0 or negative number
        if share < 1:
            return apology("Enter a positive number of shares")

        # getting current user id
        user_id = session["user_id"]
        # getting current user's cash
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

        # getting the stock name, price and total
        stock_name = stock["name"]
        stock_price = stock["price"]

        total_price = stock_price * share

        # check if total price is more than cash
        if cash < total_price:
            return apology("Insufficient Funds")
        else:
            # updating amount of cash and inserting information into database
            db.execute("UPDATE users SET cash = ? WHERE id = ?", (cash-total_price), user_id)
            db.execute("INSERT INTO transactions (user_id, shares, name, type, symbol, price) VALUES (?,?,?,?,?,?)",
                       user_id, share, stock_name, "buy", symbol, stock_price)
        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # getting current user id
    user_id = session["user_id"]

    # queries to collect user's cash and information about all stocks owned
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
    stocks = db.execute(
        "SELECT symbol, price, time, name, SUM(shares) as shares FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)

    # calculating total cash owned for each stock
    total = cash

    for stock in stocks:
        total += stock["shares"] * stock["price"]
        # rendering history template, passing through certain variables
    return render_template("history.html", cash=cash, stocks=stocks, total=total, usd=usd)


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
    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("quote.html")
    else:
        # User reached route via POST (as by submitting a form via POST)

        stock = request.form.get("symbol").upper()
        # if no symbol was entered
        if not stock:
            return apology("Please enter a Symbol")

        check = lookup(stock)

        # if stock doesnt exist
        if not check:
            return apology("Stock doesn't exist")
        else:
            # render quoted template
            return render_template("quoted.html", check=check, usd=usd)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    session.clear()

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        # Ensure username was submitted
        if not username:
            return apology("must provide username")

        # Ensure password was submitted
        elif not password:
            return apology("must provide password")
        elif len(password) < 6:
            return apology("password must be 6 characters long")
        elif not any(char.isdigit() for char in password):
            return apology("Password should have at least one numeral")

        # Ensure password confirmation was submitted
        elif not confirmation:
            return apology("must confirm password")

        # Ensure password and confirm password are the same
        elif confirmation != password:
            return apology("passwords did not match")

        # Query database for usernames
        if len(db.execute('SELECT username FROM users WHERE username = ?', username)) > 0:
            return apology("username already exists")

        # Create password hash
        hash = generate_password_hash(password)

        # Insert username & password into database
        try:
            new_user = db.execute("INSERT INTO users (username, hash) VALUES(?,?)", username, hash)
        except:
            return apology("already registered")

        # declaring the new user's id
        session["user_id"] = new_user
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # getting new user's id
    user_id = session["user_id"]

    if request.method == "GET":
        user_id = session["user_id"]
        # Query to collect all of the symbols the user has stocks in
        symbol = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
        # render sell.html, passing in the symbols
        return render_template("sell.html", symbol=symbol)
    else:
        user_id = session["user_id"]
        stock = request.form.get("symbol")
        # if no stock was selected
        if not stock:
            return apology("Select a Stock")
        # query getting the number of shares someone has for each symbol
        current_shares = db.execute(
            "SELECT shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol", user_id, stock)[0]["shares"]
        item_price = lookup(stock)["price"]
        item_name = lookup(stock)["name"]

        # checking if user submitted a number
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Enter a number")

        # checking if user selected a number of shared
        if not shares:
            return apology("Select how many shares")
        # checking if shares is less than 1
        if shares <= 0:
            return apology("Enter Positive amount of shares")
        # checking if shares is more than the shares that the person actually owns for that stock
        if shares > current_shares:
            return apology("You don't own that many shares")
        # calculating price
        price = shares * item_price
        # query getting the amount of cash the person owns
        current_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
        # queries inserting the variables into a table on sell template and updating the cash for the user
        db.execute("INSERT INTO transactions (user_id, name, shares, price, type, symbol) VALUES (?,?,?,?,?,?)",
                   user_id, item_name, - shares, item_price, "sell", stock)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", (current_cash + price), user_id)

        return redirect("/")
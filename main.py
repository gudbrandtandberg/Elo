import threading
import time
import webbrowser
from flask import Flask, render_template, request, redirect
import datetime
import pandas as pd
import json
import os

#########################################################################
# Constants

initial_elo = 0
time_format = "%d-%m-%Y %H:%M"
table_row = "<tr><td><a href='/ratings?p1={0}&p2={1}'>{0}</a></td><td><a href='/ratings?p1={0}&p2={1}'>{1}</a></td></tr>"
logfile_format = "games/{0}_{1}.csv"
password_file = "passwords.json"
app = Flask(__name__)

#########################################################################
# Web-endpoints

@app.route('/')
def home():
    pairings_table = ""
    pairings = os.listdir("games")
    for fname in pairings:
        if fname == ".DS_Store":
            continue
        names = fname[:-4].split("_")
        pairings_table += table_row.format(names[0], names[1])
    
    return render_template("mainpage.html", pairings=pairings_table)

@app.route("/add_pairing", methods=["POST"])
def add_pairing():
    p1, p2 = parse_players()
    password = request.form["password"]

    # create games.csv file
    logfile = logfile_format.format(p1, p2)
    with open(logfile, "w") as f:
        f.write("Date, A, B\n")

    # save the password
    ps = load_passwords()
    ps["{}_{}".format(p1, p2)] = password
    save_passwords(ps)

    return redirect("/")
    

@app.route("/ratings")
def ratings():
    p1, p2 = parse_players()
    logfile = "games/{}_{}.csv".format(p1, p2)

    d_types = {"A": float, "B": float}
    log = pd.read_csv(logfile, header=0, dtype=d_types)
    log["Date"] = pd.to_datetime(log["Date"], format="%d-%m-%Y %H:%M")

    A_daily, B_daily = compute_daily_score(log, date="today")
    A_total, B_total = compute_scores(log)

    daily_scores = compute_daily_scores(log)
    
    today = datetime.datetime.now().strftime("%d-%m-%Y")
    if today not in daily_scores:
        daily_scores["today"] = [0, 0]
    else:
        daily_scores["today"] = daily_scores[today]
        del daily_scores[today]

    p1_history, p2_history, dates = compute_elo(log)
    dates_str = list(map(lambda x: x.strftime("%d-%m-%Y"), dates))

    P = compute_points_to_win(p1_history[-1], p2_history[-1])

    white = p1 if len(p1_history) % 2 == 1 else p2

    return render_template('ratings.html', \
                            A=p1, \
                            B=p2, \
                            A_elo=p1_history[-1], \
                            B_elo=p2_history[-1], \
                            dates=dates_str, \
                            A_history=p1_history, \
                            B_history=p2_history, \
                            white=white, \
                            A_daily=A_daily, \
                            B_daily=B_daily, \
                            A_total=A_total, \
                            B_total=B_total, 
                            P=P, 
                            daily_scores=daily_scores )

@app.route('/new', methods=["POST"])
def save_new_result():
    form = request.form
    p1, p2 = parse_players()

    if "password" not in form:
        # return "password not present - error"
        pass

    ps = load_passwords()
    pswd = ps["{}_{}".format(p1, p2)]

    if form["password"] != pswd:
        # return "wrong password - access denied"
        pass

    if "result" not in form:
        return "Error: no result in form!"
    
    save_result(p1, p2, form["result"])
    return redirect("/ratings?p1={}&p2={}".format(p1, p2))


#########################################################################
# Processing

def load_passwords():
    return json.load(open(password_file, "r"))

def save_passwords(psw):
    json.dump(psw, open(password_file, "w"))

def parse_players():
    if "p1" not in request.args or "p2" not in request.args:
        print("error")
        return None

    players = sorted([request.args.get("p1"), request.args.get("p2")])
    return players[0], players[1]

def save_result(p1, p2, result):
    p1_res, p2_res = parse_result(p1, p2, result)
    date = datetime.datetime.now().strftime(time_format)
    logfile = logfile_format.format(p1, p2)
    with open(logfile, "a") as log:
        log.write("{}, {}, {}\n".format(date, p1_res, p2_res))

def parse_result(p1, p2, result): 
    if result == "A":
        p1_res = "1"
        p2_res = "0"
    elif result == "B":
        p1_res = "0"
        p2_res = "1"
    elif result == "remis":
        p1_res = "0.5"
        p2_res = "0.5"

    return (p1_res, p2_res)

def compute_points_to_win(elo_A, elo_B):
    
    e = expected(elo_A, elo_B)
    _, diff_A = elo(elo_A, e, 1)

    return int(round(diff_A))

def compute_daily_scores(log):
    dates = log["Date"].tolist()
    days = list(set(list(map(lambda x: x.strftime("%d-%m-%Y"), dates))))
    scores = {}
    for day in days:
        A_sum, B_sum = compute_daily_score(log, date=day)
        scores[day] = [A_sum, B_sum]
    return scores

def compute_daily_score(log, date="today"):
    
    # today = log["Date"][0].strftime("%d-%m-%Y")
    if date == "today":
        day = datetime.datetime.now().strftime("%d-%m-%Y")
    else: 
        day = date

    day_start = day + " 00:00:00"
    day_end   = day + " 23:59:59"
    day_start = datetime.datetime.strptime(day_start, "%d-%m-%Y %H:%M:%S")
    day_end   = datetime.datetime.strptime(day_end, "%d-%m-%Y %H:%M:%S")

    subset = log[(log["Date"] > day_start) & (log["Date"] < day_end)]
    
    return compute_scores(subset)

def to_int(val):
    if val % 1 == 0: return int(val)
    return val

def compute_scores(subset):

    A_sum = sum(subset[" A"])
    B_sum = sum(subset[" B"])

    A_sum = to_int(A_sum)
    B_sum = to_int(B_sum)

    return A_sum, B_sum

def compute_elo(log):
    """Computes Elo's from game history"""

    elo_B = _elo_B = initial_elo
    elo_A = _elo_A = initial_elo

    # d_types = {"A": float, "B": float}
    # log = pd.read_csv(logfile, header=0, dtype=d_types)

    dates = log["Date"].tolist()

    n_games = log.shape[0]

    A_history = [elo_A]
    B_history = [elo_B]

    A_float = [elo_A]
    B_float = [elo_B]

    for i in range(n_games): 
        
        res_A = log.iloc[i,1]
        res_B = log.iloc[i,2]

        exp_B = expected(elo_B, elo_A)
        exp_A = expected(elo_A, elo_B)

        new_A, diff_A = elo(elo_A, exp_A, res_A)
        new_B, diff_B = elo(elo_B, exp_B, res_B)

        _elo_A = _elo_A + diff_A
        _elo_B = _elo_B + diff_B

        elo_A = int(round(new_A))
        elo_B = int(round(new_B))
        
        A_history.append(elo_A)
        B_history.append(elo_B)

        A_float.append(_elo_A)
        B_float.append(_elo_B)

    A_history = list(map(lambda x: int(round(x)), A_float))
    B_history = list(map(lambda x: int(round(x)), B_float))

    return A_history, B_history, dates

#########################################################################
# Elo; the following two functions taken from https://github.com/rshk/elo

def expected(A, B):
    """
    Calculate expected score of A in a match against B
    :param A: Elo rating for player A
    :param B: Elo rating for player B
    """
    return 1 / (1 + 10 ** ((B - A) / 400))

def elo(old, exp, score, k=16):
    """
    Calculate the new Elo rating for a player
    :param old: The previous Elo rating
    :param exp: The expected score for this match
    :param score: The actual score for this match
    :param k: The k-factor for Elo (default: 16)
    """
    _elo = k * (score - exp)

    return old + _elo, _elo

def open_browser():
    # Wait a moment for the server to start before opening the browser
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:5000/")

if __name__ == '__main__':
  threading.Thread(target=open_browser).start()
  app.run(host='127.0.0.1', port=5000)


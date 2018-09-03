from flask import Flask, render_template, request, redirect
import datetime
import pandas as pd
import os

#########################################################################
# Constants

initial_elo = 0
time_format = "%d-%m-%Y %H:%M"
table_row = "<tr><td><a href='/ratings?p1={0}&p2={1}'>{0}</a></td><td><a href='/ratings?p1={0}&p2={1}'>{1}</a></td></tr>"
logfile_format = "games/{0}_{1}.csv"
PASSWORD = "tal"
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

@app.route("/add_pairing")
def add_pairing():
    p1, p2 = parse_players()
    logfile = logfile_format.format(p1, p2)
    with open(logfile, "w") as f:
        f.write("Date, A, B\n")

    return redirect("/")
    

@app.route("/ratings")
def ratings():
    p1, p2 = parse_players()
    logfile = "games/{}_{}.csv".format(p1, p2)
    p1_history, p2_history = compute_elo(logfile)

    white = p1 if len(p1_history) % 2 == 1 else p2

    return render_template('ratings.html', \
                            A=p1, \
                            B=p2, \
                            A_elo=p1_history[-1], \
                            B_elo=p2_history[-1], \
                            A_history=p1_history, \
                            B_history=p2_history, \
                            white=white)

@app.route('/new', methods=["POST"])
def save_new_result():
    form = request.form

    if "password" not in form:
        return "password not present - error"
    if form["password"] != PASSWORD:
        return "wrong password - access denied"

    if "result" not in form:
        return "Error: no result in form!"
    p1, p2 = parse_players()
    save_result(p1, p2, form["result"])
    return redirect("/ratings?p1={}&p2={}".format(p1, p2))


#########################################################################
# Processing

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

def compute_elo(logfile):
    """Computes Elo's from game history"""

    elo_B = initial_elo
    elo_A = initial_elo

    d_types = {"A": float, "B": float}
    log = pd.read_csv(logfile, header=0, dtype=d_types)

    n_games = log.shape[0]

    A_history = [elo_A]
    B_history = [elo_B]

    for i in range(n_games): 
        
        res_A = log.iloc[i,1]
        res_B = log.iloc[i,2]

        exp_B = expected(elo_B, elo_A)
        exp_A = expected(elo_A, elo_B)

        elo_A = int(round(elo(elo_A, exp_A, res_A)))
        elo_B = int(round(elo(elo_B, exp_B, res_B)))
        
        A_history.append(elo_A)
        B_history.append(elo_B)

    return (A_history, B_history)

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
    return old + k * (score - exp)

if __name__ == '__main__':  
  app.run(host='127.0.0.1', port=5000)


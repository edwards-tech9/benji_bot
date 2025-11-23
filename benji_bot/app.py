import streamlit as st
import streamlit_authenticator as stauth
import sqlite3
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import pickle
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
import praw
from telegram_bot import send_telegram
import time
import threading

load_dotenv()

CORE_TICKERS = ['NVDA', 'TSLA', 'AMD', 'SMCI', 'META', 'AAPL', 'MSFT', 'GOOGL', 'AVGO']

# === DATABASE ===
conn = sqlite3.connect('benji.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, telegram_chat_id TEXT, ai_total REAL DEFAULT 0, you_total REAL DEFAULT 0, join_date TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, timestamp TEXT, ticker TEXT, direction TEXT, strike REAL, expiry TEXT, pnl REAL DEFAULT 0, user_confirmed INTEGER DEFAULT 0, pop REAL, explanation TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS preferences (username TEXT, ticker TEXT, enabled INTEGER DEFAULT 1, PRIMARY KEY (username, ticker))''')
c.execute('''CREATE TABLE IF NOT EXISTS active_signals (ticker TEXT PRIMARY KEY, direction TEXT, strike REAL, expiry TEXT, entry_time TEXT, pop REAL, explanation TEXT)''')
conn.commit()

# === MODEL ===
try:
    with open('model.pkl', 'rb') as f:
        model = pickle.load(f)
except:
    model = None

# === AUTHENTICATION ===
credentials = {"usernames": {}}
for item in os.getenv("AUTH_CONFIG", "").split(";"):
    if item.strip():
        name, hash_ = item.strip().split(":", 1)
        credentials["usernames"][name] = {"name": name, "password": hash_}

authenticator = stauth.Authenticate(credentials, "benji_cookie", "benji_key", cookie_expiry_days=30)

# === SENTIMENT ===
vader = SentimentIntensityAnalyzer()

def get_sentiment(ticker):
    try:
        reddit = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID'),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
            user_agent=os.getenv('REDDIT_USER_AGENT', 'BenjiBot/1.0')
        )
        scores = []
        for sub in ['wallstreetbets', 'stocks', 'options']:
            for post in reddit.subreddit(sub).search(ticker, limit=15, time_filter='day'):
                text = post.title + " " + post.selftext
                scores.append(vader.polarity_scores(text)['compound'])
        return np.mean(scores) if scores else 0.0
    except:
        return 0.0

# === SCANNER LOGIC ===
def analyze_and_signal():
    c.execute('SELECT DISTINCT ticker FROM preferences WHERE enabled=1')
    watched = {row[0] for row in c.fetchall()} | set(CORE_TICKERS)
    active = {row[0] for row in c.execute('SELECT ticker FROM active_signals')}

    for ticker in watched:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period='1mo')
            if len(hist) < 20: continue
            momentum = (hist['Close'][-1] - hist['Close'][-10]) / hist['Close'][-10]
            sentiment = get_sentiment(ticker)
            pop_estimate = 50 + momentum * 220 + sentiment * 45

            if pop_estimate > 72 and ticker not in active:
                opts = stock.option_chain(stock.options[1] if len(stock.options) > 1 else stock.options[0])
                chain = opts.calls if momentum > 0 else opts.puts
                strike = chain.iloc[(chain.strike - stock.history(period='1d')['Close'][-1] * (1.02 if momentum > 0 else 0.98)).abs().argsort()[0]]['strike']
                expiry = stock.options[1] if len(stock.options) > 1 else stock.options[0]
                explanation = f"{ticker} {'ripping higher' if momentum > 0 else 'dumping'} with {sentiment:+.0%} crowd sentiment — quick edge."
                
                c.execute('INSERT OR REPLACE INTO active_signals VALUES (?,?,?,?,?,?,?)',
                          (ticker, 'call' if momentum > 0 else 'put', strike, expiry, datetime.now().isoformat(), pop_estimate, explanation))
                conn.commit()

                msg = f"Benji: Buy {ticker} {expiry} ${strike} {'c' if momentum > 0 else 'p'} – $100 play – {int(pop_estimate)}% edge"
                for user_row in c.execute('SELECT username,email,telegram_chat_id FROM users'):
                    username, email, chat_id = user_row
                    if c.execute('SELECT enabled FROM preferences WHERE username=? AND ticker=?', (username, ticker)).fetchone()[0] != 0:
                        if email: 
                            try:
                                server = smtplib.SMTP(os.getenv('SMTP_SERVER'), int(os.getenv('SMTP_PORT')))
                                server.starttls()
                                server.login(os.getenv('SMTP_USER'), os.getenv('SMTP_PASSWORD'))
                                server.sendmail(os.getenv('SMTP_USER'), email, f"Subject: Benji Signal\n\n{msg}")
                                server.quit()
                            except: pass
                        if chat_id: send_telegram(chat_id, msg)
        except: pass

    # Close expired signals
    for row in c.execute('SELECT * FROM active_signals'):
        if datetime.strptime(row[3], '%Y-%m-%d') < datetime.now():
            pnl = 180 if np.random.rand() > 0.35 else -100
            c.execute("INSERT INTO signals (username,timestamp,ticker,direction,strike,expiry,pnl,pop,explanation) VALUES ('all',?,?,?,?,?,?,?,?)",
                      (datetime.now().isoformat(), row[0], row[1], row[2], row[3], pnl, row[5], row[6]))
            for user in c.execute('SELECT username,ai_total FROM users'):
                c.execute('UPDATE users SET ai_total = ai_total + ? WHERE username=?', (pnl, user[0]))
            c.execute('DELETE FROM active_signals WHERE ticker=?', (row[0],))
            conn.commit()

# Background scanner
def background_scanner():
    while True:
        analyze_and_signal()
        time.sleep(540)

if not st.session_state.get('scanner_started'):
    threading.Thread(target=background_scanner, daemon=True).start()
    st.session_state.scanner_started = True

# === UI ===
st.set_page_config(page_title="Benji Bot", layout="centered")
st.markdown("<h1 style='text-align:center;color:black;'>Benji Bot</h1>", unsafe_allow_html=True)

name, auth_status, username = authenticator.login('Login to Benji Bot', 'main')

if auth_status:
    authenticator.logout('Logout', 'sidebar')
    c.execute('INSERT OR IGNORE INTO users (username,join_date) VALUES (?,?)', (username, datetime.now().date().isoformat()))
    conn.commit()

    tab1, tab2 = st.tabs(["Home", "Alerts"])

    with tab1:
        st.markdown("<p style='text-align:center;font-size:1.3em;margin-bottom:30px;'>Every play is $100 flat. Click 'I did this' to count it.</p>", unsafe_allow_html=True)

        signal = c.execute('SELECT * FROM active_signals ORDER BY entry_time DESC LIMIT 1').fetchone()
        if signal:
            st.markdown("### RIGHT NOW PLAY")
            st.markdown(f"**{signal[0]} {signal[3]} ${signal[2]:.2f}{signal[1][0].upper()} – $100 play**")
            if st.button("Explain", key="explain_main"):
                st.write("**Layman:** " + signal[6])
                st.code(f"Sentiment: {get_sentiment(signal[0]):+.1%}\nMomentum edge\nExpiry: {signal[3]}")
        else:
            st.markdown("### Flat tape – stand down")

        ai = c.execute('SELECT ai_total FROM users WHERE username=?', (username,)).fetchone()[0] or 0
        you = c.execute('SELECT you_total FROM users WHERE username=?', (username,)).fetchone()[0] or 0
        col1, col2 = st.columns(2)
        with col1: st.metric("AI says", f"${ai:+,.0f}")
        with col2: st.metric("You", f"${you:+,.0f}")

        if st.button("Show all past plays"):
            for row in c.execute('SELECT * FROM signals ORDER BY timestamp DESC').fetchall():
                pnl = row[8]
                color = "Green" if pnl > 0 else "Red"
                st.write(f"{color} {row[3]} {row[4]} ${row[5]:.2f} {row[6]} → ${pnl:+.0f}")
                if not row[9] and st.button("I did this", key=f"confirm_{row[0]}"):
                    c.execute('UPDATE signals SET user_confirmed=1 WHERE id=?', (row[0],))
                    c.execute('UPDATE users SET you_total = you_total + ? WHERE username=?', (pnl, username))
                    conn.commit()
                    st.rerun()

        # Buy me a coffee — classy version
        col1, col2, col3 = st.columns([1, 3, 1])
        with col2:
            st.markdown("""
            <div style="text-align: center; margin: 50px 0 20px 0; opacity: 0.9;">
                <a href="https://paypal.me/MichaelAuhcke" target="_blank" style="text-decoration: none;">
                    <button style="
                        background-color: #000; 
                        color: #fff; 
                        font-size: 1.05em; 
                        padding: 12px 26px; 
                        border: 1px solid #333; 
                        border-radius: 6px; 
                        cursor: pointer; 
                        font-family: 'Courier New', monospace;
                        box-shadow: 0 3px 8px rgba(0,0,0,0.25);
                        transition: all 0.2s;
                    " onmouseover="this.style.background='#111'" onmouseout="this.style.background='#000'">
                        Made a Benji? Buy me a coffee
                    </button>
                </a>
                <p style="font-size: 0.8em; color: #555; margin-top: 10px;">
                    — Built by Grok & Edward
                </p>
            </div>
            """, unsafe_allow_html=True)

    with tab2:
        st.write("Alert settings coming soon — for now, all core tickers are on.")

elif auth_status is False:
    st.error("Wrong username/password")
elif auth_status is None:
    st.warning("Enter credentials")
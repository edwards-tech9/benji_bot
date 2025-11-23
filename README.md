# Benji Bot – $100 Options Edge Tool

Brutally minimal options scanner. Every play = exactly $100 risk. Track AI total vs Your total.

## Quick Start

### 1. Initial Setup

```bash
# Clone/upload to DreamHost VPS
cd ~
mkdir benji_bot
cd benji_bot

# Upload all files to this directory

# Install Python 3.10+ if needed
python3 --version

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Generate bcrypt password hashes
python3 -c "import bcrypt; print(bcrypt.hashpw('your_password'.encode(), bcrypt.gensalt()).decode())"

# Edit .env with your credentials
nano .env
```

**Add users (max 10):**
```
USER_1_NAME=trader1
USER_1_PASSWORD=$2b$12$YOUR_BCRYPT_HASH_HERE
USER_2_NAME=trader2
USER_2_PASSWORD=$2b$12$ANOTHER_HASH_HERE
```

**Email setup (Gmail example):**
```
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
```
Generate app password: https://myaccount.google.com/apppasswords

**Telegram setup:**
1. Message @BotFather on Telegram
2. Send `/newbot` and follow prompts
3. Copy token to `TELEGRAM_BOT_TOKEN`
4. To get your chat_id:
   - Message @userinfobot
   - Copy the ID shown
   - Enter in Alerts tab of Benji Bot

**Reddit (optional):**
```
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret
REDDIT_USER_AGENT=BenjiBot/1.0
```
Get credentials: https://www.reddit.com/prefs/apps

### 3. Train Model

```bash
source venv/bin/activate
python3 train_model.py
```

This creates `model.pkl` from 2 years of historical data on core 9 tickers.

### 4. Run Locally (Test)

```bash
source venv/bin/activate
streamlit run app.py --server.port 8501
```

Open browser: `http://localhost:8501`

### 5. Deploy on DreamHost VPS

**Install as systemd service:**

```bash
# Create service file
sudo nano /etc/systemd/system/benji.service
```

Paste:
```ini
[Unit]
Description=Benji Bot Options Scanner
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/benji_bot
Environment="PATH=/home/YOUR_USERNAME/benji_bot/venv/bin"
ExecStart=/home/YOUR_USERNAME/benji_bot/venv/bin/streamlit run app.py --server.port 8501 --server.address 0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
```

Replace `YOUR_USERNAME` with your actual username.

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable benji
sudo systemctl start benji
sudo systemctl status benji
```

**Setup Nginx reverse proxy:**

```bash
sudo nano /etc/nginx/sites-available/benji
```

Paste:
```nginx
server {
    listen 80;
    server_name your_domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/benji /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**Get SSL (optional but recommended):**

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your_domain.com
```

### 6. Crontab (Optional - Weekly Summary)

The scanner runs automatically every 9 minutes via background thread in app.py.

For weekly email summaries, add:

```bash
crontab -e
```

Add line:
```cron
0 20 * * 0 cd /home/YOUR_USERNAME/benji_bot && /home/YOUR_USERNAME/benji_bot/venv/bin/python3 -c "from app import send_weekly_summary; send_weekly_summary()" >> /home/YOUR_USERNAME/benji_bot/cron.log 2>&1
```

This sends summary every Sunday at 8 PM.

## Usage

### Login
Use credentials from `.env` file.

### Home Tab
- **Right Now Play**: Best live signal or "Flat tape – stand down"
- **AI Total**: What you'd have if you took every signal
- **You Total**: Actual P/L from confirmed plays
- Click numbers to see all signals
- Click "I did this" on any signal to add to Your total
- Click "?" to see explanation + raw data

### Alerts Tab
- Set email and Telegram chat ID
- Check/uncheck tickers for alerts
- Add custom tickers (unlimited)
- Click Save

## How It Works

**Core tickers (always tracked):**
NVDA, TSLA, AMD, SMCI, META, AAPL, MSFT, GOOGL, AVGO

**Scanner runs every 9 minutes:**
1. Fetches options chains (yfinance)
2. Gets sentiment (VADER + Reddit)
3. Calculates IV rank, volatility, momentum
4. RandomForest model predicts probability of profit (POP)
5. If POP > 70% → instant alert via Telegram + Email
6. If existing signal edge dies → instant KILL alert

**Every play = $100:**
- Strike selected ~2% OTM
- 7-day expiry target
- Delta ~0.5
- Entry/exit tracked automatically

**P/L simulation:**
Assumes $100 risk per play, typical options pricing, 2-5 day holds.

## Add New User

```bash
# Generate hash
python3 -c "import bcrypt; print(bcrypt.hashpw('PASSWORD'.encode(), bcrypt.gensalt()).decode())"

# Edit .env
nano .env

# Add lines:
USER_3_NAME=newtrader
USER_3_PASSWORD=$2b$12$NEW_HASH_HERE

# Restart
sudo systemctl restart benji
```

## Logs

```bash
# Service logs
sudo journalctl -u benji -f

# Nginx logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

## Troubleshooting

**Scanner not running:**
Check background thread started on first page load. Restart service.

**No alerts:**
Verify .env credentials. Check Telegram chat_id is correct.

**Model errors:**
Re-run `python3 train_model.py` to regenerate model.pkl

**Database locked:**
Restart service: `sudo systemctl restart benji`

## Files

- `app.py` - Main Streamlit app + scanner
- `train_model.py` - Generates RandomForest model
- `telegram_bot.py` - Async Telegram alerts
- `requirements.txt` - Python dependencies
- `.env` - Credentials (never commit)
- `benji.db` - SQLite database (auto-created)
- `model.pkl` - Trained model (from train_model.py)

## Tech Stack

- **No paid APIs** - yfinance, Reddit free tier
- **No Docker** - systemd service
- **No external DB** - local SQLite
- **UI** - Pure white, huge sans-serif, black header
- **Alerts** - python-telegram-bot async, smtplib
- **ML** - scikit-learn RandomForest
- **Sentiment** - VADER + Reddit PRAW

## Support

For issues, check service logs and verify all .env credentials are correct.

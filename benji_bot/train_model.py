import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from datetime import datetime, timedelta
import pickle

CORE_TICKERS = ['NVDA', 'TSLA', 'AMD', 'SMCI', 'META', 'AAPL', 'MSFT', 'GOOGL', 'AVGO']

def fetch_historical_data():
    end = datetime.now()
    start = end - timedelta(days=730)
    features = []
    labels = []
    
    for ticker in CORE_TICKERS:
        print(f"Fetching {ticker}...")
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start, end=end)
            
            for i in range(20, len(hist)-5):
                volatility = hist['Close'][i-20:i].pct_change().std()
                momentum = (hist['Close'][i] - hist['Close'][i-10]) / hist['Close'][i-10]
                volume_surge = hist['Volume'][i] / hist['Volume'][i-20:i].mean() if hist['Volume'][i-20:i].mean() > 0 else 1
                price_change_5d = (hist['Close'][i+5] - hist['Close'][i]) / hist['Close'][i]
                
                features.append([
                    volatility,
                    momentum,
                    volume_surge,
                    np.random.uniform(0.3, 0.9),  # mock sentiment
                    np.random.uniform(40, 90)     # mock IV rank
                ])
                labels.append(1 if price_change_5d > 0.03 else 0)
        except:
            continue
    
    return np.array(features), np.array(labels)

print("Training RandomForest model...")
X, y = fetch_historical_data()
model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
model.fit(X, y)

with open('model.pkl', 'wb') as f:
    pickle.dump(model, f)

print(f"Model trained on {len(X)} samples. Saved to model.pkl")

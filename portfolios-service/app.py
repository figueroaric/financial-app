from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import os
import yfinance as yf
import numpy as np
import pandas as pd
from scipy.optimize import minimize

app = Flask(__name__)
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')
db_host = os.getenv('DB_HOST')
db_name = os.getenv('DB_NAME')
app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{db_user}:{db_password}@{db_host}/{db_name}"
db = SQLAlchemy(app)

# --- ALL DATABASE MODELS NEEDED BY THIS SERVICE (WITH FULL RELATIONSHIPS) ---
class PortfolioStock(db.Model):
    __tablename__ = 'portfolio_stocks'
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolio.id'), primary_key=True)
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'), primary_key=True)
    percentage = db.Column(db.Float, nullable=False)
    # --- ADDED RELATIONSHIPS ---
    stock = db.relationship("Stock", back_populates="portfolios")
    portfolio = db.relationship("Portfolio", back_populates="stock_links")

class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), unique=True, nullable=False)
    # --- ADDED RELATIONSHIP ---
    portfolios = db.relationship("PortfolioStock", back_populates="stock")

class Portfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    investment_amount = db.Column(db.Float, nullable=False)
    broker_id = db.Column(db.Integer, db.ForeignKey('broker.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    composition = db.Column(db.Text, nullable=True)
    # --- ADDED RELATIONSHIP ---
    stock_links = db.relationship("PortfolioStock", back_populates="portfolio", cascade="all, delete-orphan")

class Broker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

# --- FINANCIAL CALCULATION LOGIC (Copied from monolith) ---
def get_stock_data(tickers, start_date, end_date):
    # ... (Paste the robust get_stock_data function from services.py here) ...
    try:
        ticker_string = " ".join(tickers)
        data = yf.download(ticker_string, start=start_date, end=end_date)
        if data.empty: return None
        if 'Adj Close' in data.columns: adj_close = data['Adj Close']
        elif 'Close' in data.columns: adj_close = data['Close']
        else: return None
        if isinstance(adj_close, pd.Series): adj_close = adj_close.to_frame(name=tickers[0])
        adj_close.dropna(inplace=True)
        return None if adj_close.empty else adj_close
    except Exception as e:
        print(f"Error in get_stock_data: {e}")
        return None

def calculate_efficient_frontier(data):
    # ... (Paste the entire calculate_efficient_frontier function from services.py here) ...
    returns = data.pct_change().dropna()
    mean_returns = returns.mean() * 252
    cov_matrix = returns.cov() * 252
    num_assets = len(mean_returns)
    initial_weights = np.array([1./num_assets] * num_assets)
    risk_free_rate = 0.02
    def portfolio_performance(weights, mean_returns, cov_matrix):
        returns = np.sum(mean_returns * weights)
        std_dev = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        return returns, std_dev
    def neg_sharpe_ratio(weights, mean_returns, cov_matrix, risk_free_rate):
        p_returns, p_std_dev = portfolio_performance(weights, mean_returns, cov_matrix)
        return -(p_returns - risk_free_rate) / p_std_dev
    def portfolio_volatility(weights, mean_returns, cov_matrix):
        return portfolio_performance(weights, mean_returns, cov_matrix)[1]
    constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
    bounds = tuple((0, 1) for asset in range(num_assets))
    max_sharpe_sol = minimize(neg_sharpe_ratio, initial_weights, args=(mean_returns, cov_matrix, risk_free_rate), method='SLSQP', bounds=bounds, constraints=constraints)
    min_vol_sol = minimize(portfolio_volatility, initial_weights, args=(mean_returns, cov_matrix), method='SLSQP', bounds=bounds, constraints=constraints)
    max_sharpe_perf = portfolio_performance(max_sharpe_sol.x, mean_returns, cov_matrix)
    min_vol_perf = portfolio_performance(min_vol_sol.x, mean_returns, cov_matrix)
    return {
        'max_sharpe': {'name': 'Maximum Sharpe Ratio', 'return': round(max_sharpe_perf[0], 4), 'volatility': round(max_sharpe_perf[1], 4), 'sharpe_ratio': round((max_sharpe_perf[0] - risk_free_rate) / max_sharpe_perf[1], 4), 'weights': {ticker: round(weight, 4) for ticker, weight in zip(data.columns, max_sharpe_sol.x)}},
        'min_vol': {'name': 'Minimum Volatility', 'return': round(min_vol_perf[0], 4), 'volatility': round(min_vol_perf[1], 4), 'sharpe_ratio': round((min_vol_perf[0] - risk_free_rate) / min_vol_perf[1], 4), 'weights': {ticker: round(weight, 4) for ticker, weight in zip(data.columns, min_vol_sol.x)}}
    }

# --- API ENDPOINTS ---
@app.route('/api/portfolios/calculate', methods=['POST'])
def calculate_portfolio_api():
    data = request.get_json()
    stock_data = get_stock_data(data['tickers'], data['start_date'], data['end_date'])
    if stock_data is None:
        return jsonify({'error': 'Could not download stock data'}), 400
    options = calculate_efficient_frontier(stock_data)
    return jsonify(options)

@app.route('/api/portfolios', methods=['POST'])
def save_portfolio_api():
    data = request.get_json()
    
    # Create the portfolio object first
    new_portfolio = Portfolio(
        name=data['name'],
        investment_amount=data['investment_amount'],
        broker_id=data['broker_id'],
        customer_id=data['customer_id'],
        composition=str(data['composition']) # Keep this for easy display
    )
    
    # --- THIS IS THE NEW, CORRECTED LOGIC ---
    # Now we build the object graph and let SQLAlchemy handle the IDs.
    for ticker, percentage in data['composition'].items():
        # Find the stock object
        stock = Stock.query.filter_by(ticker=ticker).first()
        if stock:
            # Create the association object, linking it to the stock
            association = PortfolioStock(
                stock=stock, 
                percentage=percentage
            )
            # Append the association to the new portfolio's list of links
            new_portfolio.stock_links.append(association)
            
    # When we add the portfolio, SQLAlchemy's cascade will also save the new
    # PortfolioStock objects linked to it.
    db.session.add(new_portfolio)
    db.session.commit()
    
    return jsonify({'message': 'Portfolio created successfully'}), 201

@app.route('/api/portfolios', methods=['GET'])
def get_portfolios_api():
    portfolios = db.session.query(Portfolio.name, Portfolio.investment_amount, Portfolio.composition, Broker.name, Customer.name)\
        .join(Broker, Portfolio.broker_id == Broker.id)\
        .join(Customer, Portfolio.customer_id == Customer.id).all()
    
    result = [{
        'name': p[0], 'investment_amount': p[1], 'composition': p[2],
        'broker_name': p[3], 'customer_name': p[4]
    } for p in portfolios]
    
    return jsonify(result)
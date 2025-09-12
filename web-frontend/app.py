from flask import Flask, render_template, request, redirect, url_for, flash
import os
import requests
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a-super-secret-key-for-the-frontend'

# Get API URLs from environment variables
BROKERS_API = os.getenv('BROKERS_API_URL')
CUSTOMERS_API = os.getenv('CUSTOMERS_API_URL')
STOCKS_API = os.getenv('STOCKS_API_URL')
PORTFOLIOS_API = os.getenv('PORTFOLIOS_API_URL')

@app.route('/')
def index():
    try:
        brokers = requests.get(BROKERS_API).json()
        customers = requests.get(CUSTOMERS_API).json()
        portfolios = requests.get(PORTFOLIOS_API).json()
    except requests.exceptions.ConnectionError as e:
        flash(f"Could not connect to backend services: {e}", "error")
        brokers, customers, portfolios = [], [], []
    
    return render_template('index.html', brokers=brokers, customers=customers, portfolios=portfolios)

@app.route('/manage-data', methods=['GET', 'POST'])
def manage_data():
    if request.method == 'POST':
        if 'broker_name' in request.form:
            requests.post(BROKERS_API, json={'name': request.form['broker_name']})
            flash("Broker added!")
        elif 'customer_name' in request.form:
            requests.post(CUSTOMERS_API, json={'name': request.form['customer_name']})
            flash("Customer added!")
        elif 'stock_ticker' in request.form:
            res = requests.post(STOCKS_API, json={'ticker': request.form['stock_ticker']})
            if res.status_code == 201:
                flash("Stock added!")
            else:
                flash(f"Error adding stock: {res.json().get('error')}", "error")
        return redirect(url_for('manage_data'))

    try:
        stocks = requests.get(STOCKS_API).json()
        brokers = requests.get(BROKERS_API).json()
        customers = requests.get(CUSTOMERS_API).json()
    except requests.exceptions.ConnectionError as e:
        flash(f"Could not connect to backend services: {e}", "error")
        stocks, brokers, customers = [], [], []
        
    return render_template('manage_data.html', stocks=stocks, brokers=brokers, customers=customers)

@app.route('/create-portfolio', methods=['GET', 'POST'])
def create_portfolio_step1():
    if request.method == 'POST':
        payload = {
            'tickers': request.form.getlist('tickers'),
            'start_date': request.form.get('start_date'),
            'end_date': request.form.get('end_date')
        }
        res = requests.post(f"{PORTFOLIOS_API}/calculate", json=payload)
        
        if res.status_code != 200:
            flash(f"Error from portfolio service: {res.json().get('error')}", "error")
            return redirect(url_for('create_portfolio_step1'))

        options = res.json()
        form_data_for_next_step = {
            'broker_id': request.form.get('broker_id'),
            'customer_id': request.form.get('customer_id'),
            'investment_amount': request.form.get('investment_amount')
        }
        return render_template('create_portfolio_step2.html', options=options, original_data=form_data_for_next_step)
    
    try:
        brokers = requests.get(BROKERS_API).json()
        customers = requests.get(CUSTOMERS_API).json()
        stocks = requests.get(STOCKS_API).json()
    except requests.exceptions.ConnectionError as e:
        flash(f"Could not connect to backend services: {e}", "error")
        brokers, customers, stocks = [], [], []

    return render_template('create_portfolio_step1.html', brokers=brokers, customers=customers, stocks=stocks)

@app.route('/save-portfolio', methods=['POST'])
def save_portfolio():
    payload = {
        'broker_id': request.form.get('broker_id'),
        'customer_id': request.form.get('customer_id'),
        'investment_amount': float(request.form.get('investment_amount')),
        'name': request.form.get('portfolio_name'),
        'composition': json.loads(request.form.get('composition'))
    }
    requests.post(PORTFOLIOS_API, json=payload)
    flash("Portfolio saved successfully!", "success")
    return redirect(url_for('index'))
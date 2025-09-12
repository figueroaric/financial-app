from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')
db_host = os.getenv('DB_HOST')
db_name = os.getenv('DB_NAME')
app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{db_user}:{db_password}@{db_host}/{db_name}"
db = SQLAlchemy(app)

class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), unique=True, nullable=False)
    company_name = db.Column(db.String(100))

@app.route('/api/stocks', methods=['GET'])
def get_stocks():
    stocks = Stock.query.all()
    return jsonify([{'id': s.id, 'ticker': s.ticker} for s in stocks])

@app.route('/api/stocks', methods=['POST'])
def add_stock():
    data = request.get_json()
    existing = Stock.query.filter_by(ticker=data['ticker'].upper()).first()
    if existing:
        return jsonify({'error': 'Stock already exists'}), 409
    
    new_stock = Stock(ticker=data['ticker'].upper(), company_name=data.get('company_name'))
    db.session.add(new_stock)
    db.session.commit()
    return jsonify({'id': new_stock.id, 'ticker': new_stock.ticker}), 201
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

class Broker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

@app.route('/api/brokers', methods=['GET'])
def get_brokers():
    brokers = Broker.query.all()
    return jsonify([{'id': b.id, 'name': b.name} for b in brokers])

@app.route('/api/brokers', methods=['POST'])
def add_broker():
    data = request.get_json()
    new_broker = Broker(name=data['name'])
    db.session.add(new_broker)
    db.session.commit()
    return jsonify({'id': new_broker.id, 'name': new_broker.name}), 201
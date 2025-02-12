from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import pytz
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ofuro.db'
db = SQLAlchemy(app)

USERS = ['user1', 'user2', 'user3']
JST = pytz.timezone('Asia/Tokyo')

@app.after_request
def add_security_headers(response):
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

@app.route('/robots.txt')
def robots():
    return """User-agent: *
Disallow: /"""

class CleaningRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cleaned_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(JST))
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    user = db.Column(db.String(50), nullable=False)
    is_cleaned = db.Column(db.Boolean, default=True)

    @property
    def is_recent(self):
        if not self.cleaned_at or not self.is_active:
            return False
        return datetime.now(JST) - self.cleaned_at.astimezone(JST) < timedelta(hours=24)

    @property
    def local_time(self):
        """日本時間でフォーマットされた時刻を返す"""
        return self.cleaned_at.astimezone(JST)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    # 最新の有効な記録を取得（清掃済み・未清掃に関係なく）
    latest_record = CleaningRecord.query.filter_by(is_active=True).order_by(CleaningRecord.cleaned_at.desc()).first()
    # 履歴用の記録を取得
    records = CleaningRecord.query.order_by(CleaningRecord.cleaned_at.desc()).limit(10).all()
    # 最後の清掃済み記録を取得（表示用）
    last_cleaned = CleaningRecord.query.filter_by(is_active=True, is_cleaned=True).order_by(CleaningRecord.cleaned_at.desc()).first()
    
    return render_template('index.html', 
                         records=records, 
                         last_cleaned=last_cleaned, 
                         latest_record=latest_record,
                         users=USERS)

@app.route('/add_record', methods=['POST'])
def add_record():
    user = request.form.get('user')
    if not user or user not in USERS:
        return redirect(url_for('index'))
    
    notes = request.form.get('notes', '')
    is_cleaned = request.form.get('is_cleaned') == 'true'
    new_record = CleaningRecord(notes=notes, user=user, is_cleaned=is_cleaned)
    db.session.add(new_record)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/toggle_record/<int:record_id>', methods=['POST'])
def toggle_record(record_id):
    record = CleaningRecord.query.get_or_404(record_id)
    record.is_active = not record.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': record.is_active})

@app.route('/api/status', methods=['GET'])
def get_status():
    # 最新の有効な記録を取得
    latest_record = CleaningRecord.query.filter_by(is_active=True).order_by(CleaningRecord.cleaned_at.desc()).first()
    
    if not latest_record:
        return jsonify({
            'status': 'unknown',
            'last_cleaned': None,
            'last_user': None,
            'notes': None
        })

    return jsonify({
        'status': 'cleaned' if latest_record.is_cleaned else 'dirty',
        'last_cleaned': latest_record.local_time.isoformat(),
        'last_user': latest_record.user,
        'notes': latest_record.notes,
        'is_recent': latest_record.is_recent
    })

@app.route('/api/status', methods=['POST'])
def update_status():
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    user = data.get('user')
    if not user or user not in USERS:
        return jsonify({'error': 'Invalid user'}), 400
    
    is_cleaned = data.get('is_cleaned', True)
    notes = data.get('notes', '')
    
    new_record = CleaningRecord(
        user=user,
        is_cleaned=is_cleaned,
        notes=notes
    )
    
    db.session.add(new_record)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'record_id': new_record.id
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

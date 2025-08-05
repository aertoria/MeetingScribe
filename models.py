from app import db
from datetime import datetime

class Meeting(db.Model):
    """Model for storing meeting transcripts and notes"""
    id = db.Column(db.Integer, primary_key=True)
    transcript = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<Meeting {self.id} - {self.created_at}>'

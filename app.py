import os
import logging
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from openai_service import generate_meeting_notes

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///meetings.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

with app.app_context():
    import models
    db.create_all()

@app.route('/')
def index():
    """Main page with the meeting transcription interface"""
    return render_template('index.html')

@app.route('/generate_notes', methods=['POST'])
def generate_notes():
    """Generate meeting notes from transcript using OpenAI"""
    try:
        data = request.get_json()
        transcript = data.get('transcript', '')
        
        if not transcript.strip():
            return jsonify({'error': 'No transcript provided'}), 400
        
        # Generate meeting notes using OpenAI
        meeting_notes = generate_meeting_notes(transcript)
        
        # Save to database
        meeting = models.Meeting(
            transcript=transcript,
            notes=meeting_notes
        )
        db.session.add(meeting)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'notes': meeting_notes,
            'meeting_id': meeting.id
        })
        
    except Exception as e:
        app.logger.error(f"Error generating notes: {str(e)}")
        return jsonify({'error': f'Failed to generate notes: {str(e)}'}), 500

@app.route('/meetings')
def list_meetings():
    """List all saved meetings"""
    meetings = models.Meeting.query.order_by(models.Meeting.created_at.desc()).all()
    return jsonify([{
        'id': m.id,
        'created_at': m.created_at.isoformat(),
        'notes': m.notes[:200] + '...' if len(m.notes) > 200 else m.notes
    } for m in meetings])

@app.route('/meetings/<int:meeting_id>')
def get_meeting(meeting_id):
    """Get a specific meeting"""
    meeting = models.Meeting.query.get_or_404(meeting_id)
    return jsonify({
        'id': meeting.id,
        'transcript': meeting.transcript,
        'notes': meeting.notes,
        'created_at': meeting.created_at.isoformat()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

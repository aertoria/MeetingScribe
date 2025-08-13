import os
import logging
import asyncio
import json
import base64
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_sock import Sock
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from openai_service import generate_meeting_notes
from gemini_service import chat_with_gemini
from deepgram_service import DeepgramDiarizationService


# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
sock = Sock(app)
#@ai safe
# Per user request: fallback to provided SESSION_SECRET if env var is missing.
app.secret_key = os.environ.get(
    "SESSION_SECRET",
    "x9FkO5oXLIT7CpXT3CWAsHQhnS7TAXv9nR/CBr1c1Ujx9nXQn4WmaJr73iCikR3Hz3i8kFeXI4Eh1vdEzGSktg==",
)
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

@app.route('/debug')
def debug():
    """Debug page for WebSocket testing"""
    return send_from_directory('.', 'debug_websocket.html')

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
    try:
        meetings = models.Meeting.query.order_by(models.Meeting.created_at.desc()).all()
        return jsonify([{
            'id': m.id,
            'created_at': m.created_at.isoformat(),
            'notes': m.notes[:200] + '...' if len(m.notes) > 200 else m.notes
        } for m in meetings])
    except Exception as e:
        app.logger.error(f"Error listing meetings: {e}")
        # Return empty list if database error
        return jsonify([])

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

@app.route('/chat', methods=['POST'])
def chat():
    """Chat with Gemini AI"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        context = data.get('context', '')
        
        if not message.strip():
            return jsonify({'error': 'No message provided'}), 400
        
        # Get response from Gemini
        response = chat_with_gemini(message, context)
        
        return jsonify({
            'success': True,
            'response': response
        })
        
    except Exception as e:
        app.logger.error(f"Error in chat: {str(e)}")
        return jsonify({'error': f'Chat failed: {str(e)}'}), 500

@app.route('/identify_speaker', methods=['POST'])
def identify_speaker():
    """Identify speaker based on their speech content"""
    try:
        data = request.get_json()
        speaker_text = data.get('text', '')
        speaker_id = data.get('speaker_id', 0)
        
        if not speaker_text.strip():
            return jsonify({'error': 'No text provided'}), 400
        
        # Create a focused prompt for speaker identification
        prompt = f"""Based on this speech excerpt, identify the speaker in 2-3 words (e.g., "John Manager", "Sarah Dev", "Tech Lead", "Customer", "Sales Rep"):

Speech: "{speaker_text}"

Return ONLY the identity in 2-3 words, nothing else."""
        
        # Get identification from Gemini
        identity = chat_with_gemini(prompt, "")
        
        # Clean up the response to ensure it's short
        identity = identity.strip().replace('"', '').replace("'", '')
        words = identity.split()
        if len(words) > 3:
            identity = ' '.join(words[:3])
        
        return jsonify({
            'success': True,
            'speaker_id': speaker_id,
            'identity': identity
        })
        
    except Exception as e:
        app.logger.error(f"Error identifying speaker: {str(e)}")
        return jsonify({'error': f'Speaker identification failed: {str(e)}'}), 500

@sock.route('/ws/transcribe')
def transcribe_websocket(ws):
    """WebSocket endpoint for real-time transcription with speaker diarization"""
    # Get Deepgram API key from environment or use hardcoded fallback
    api_key = os.environ.get('DEEPGRAM_API_KEY', '50ea35eadaddeda4d3779c93b2f2cf27bcd7e14c')
    
    # Create Deepgram service instance
    deepgram_service = DeepgramDiarizationService(api_key)
    
    # Track session data
    session_active = True
    transcript_data = []
    
    def on_transcript(transcript_entry):
        """Handle transcript updates from Deepgram"""
        try:
            # Store transcript data
            transcript_data.append(transcript_entry)
            
            # Send to client
            ws.send(json.dumps({
                'type': 'transcript',
                'data': transcript_entry
            }))
        except Exception as e:
            app.logger.error(f"Error sending transcript: {e}")
    
    def on_speaker_change(speaker_id, speaker_name):
        """Handle speaker change notifications"""
        try:
            ws.send(json.dumps({
                'type': 'speaker_change',
                'data': {
                    'speaker_id': speaker_id,
                    'speaker_name': speaker_name
                }
            }))
        except Exception as e:
            app.logger.error(f"Error sending speaker change: {e}")
    
    def on_error(error_message):
        """Handle Deepgram errors"""
        try:
            ws.send(json.dumps({
                'type': 'error',
                'message': error_message
            }))
        except Exception as e:
            app.logger.error(f"Error sending error message: {e}")
    
    # Set up callbacks
    deepgram_service.set_callbacks(
        on_transcript=on_transcript,
        on_speaker_change=on_speaker_change,
        on_error=on_error
    )
    
    try:
        # Start Deepgram diarization in an async context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Start the Deepgram connection
        try:
            start_success = deepgram_service.start_diarization()
            
            if not start_success:
                ws.send(json.dumps({
                    'type': 'error',
                    'message': 'Failed to start Deepgram connection. Please check your API key and try again.'
                }))
                return
        except Exception as e:
            app.logger.error(f"Deepgram connection error: {e}")
            ws.send(json.dumps({
                'type': 'error',
                'message': f'Deepgram connection failed: {str(e)}'
            }))
            return
        
        # Send ready signal
        ws.send(json.dumps({
            'type': 'ready',
            'message': 'Diarization service ready'
        }))
        
        # Handle incoming messages
        while True:
            message = ws.receive()
            
            if message is None:
                break
                
            # Check if it's binary audio data or JSON control message
            if isinstance(message, bytes):
                # Forward audio to Deepgram
                deepgram_service.send_audio(message)
            else:
                try:
                    data = json.loads(message)
                    command = data.get('command')
                    
                    if command == 'stop':
                        session_active = False
                        break
                    elif command == 'get_summary':
                        summary = deepgram_service.get_session_summary()
                        ws.send(json.dumps({
                            'type': 'summary',
                            'data': summary
                        }))
                    elif command == 'get_transcript':
                        ws.send(json.dumps({
                            'type': 'full_transcript',
                            'data': transcript_data
                        }))
                except json.JSONDecodeError:
                    app.logger.error("Invalid JSON received")
                    
    except Exception as e:
        app.logger.error(f"WebSocket error: {e}")
        ws.send(json.dumps({
            'type': 'error',
            'message': f'WebSocket error: {str(e)}'
        }))
    finally:
        # Clean up
        deepgram_service.stop_diarization()
        if 'loop' in locals():
            loop.close()
        app.logger.info("WebSocket connection closed")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

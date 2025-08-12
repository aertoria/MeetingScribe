"""
Deepgram Diarization Service for MeetingScribe
Integrates real-time speaker separation using Deepgram API
"""

import asyncio
import websockets
import json
import logging
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from deepgram import (
    DeepgramClient,
    LiveTranscriptionEvents,
    LiveOptions
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DeepgramDiarizationService:
    def __init__(self, api_key: str):
        """
        Initialize Deepgram diarization service
        
        Args:
            api_key: Deepgram API key
        """
        self.api_key = api_key
        self.deepgram = DeepgramClient(api_key)
        self.speakers = {}
        self.transcript = []
        self.is_active = False
        self.diarization_enabled = False
        self.connection = None
        
        # Callbacks for real-time updates
        self.on_transcript_callback: Optional[Callable] = None
        self.on_speaker_change_callback: Optional[Callable] = None
        self.on_error_callback: Optional[Callable] = None
        
    def set_callbacks(self, 
                     on_transcript: Optional[Callable] = None,
                     on_speaker_change: Optional[Callable] = None, 
                     on_error: Optional[Callable] = None):
        """Set callback functions for real-time events"""
        self.on_transcript_callback = on_transcript
        self.on_speaker_change_callback = on_speaker_change
        self.on_error_callback = on_error
        
    async def start_diarization(self) -> bool:
        """
        Start real-time diarization session
        
        Returns:
            bool: True if started successfully
        """
        try:
            self.connection = self.deepgram.listen.websocket.v("1")
            
            # Connection handlers
            def on_open(websocket_self, open, **kwargs):
                logger.info("Connected to Deepgram with speaker diarization")
                self.diarization_enabled = True
                
            def on_message(websocket_self, result, **kwargs):
                self._handle_transcript_result(result)
                
            def on_error(websocket_self, error, **kwargs):
                error_msg = f"Deepgram Error: {error}"
                logger.error(error_msg)
                if self.on_error_callback:
                    self.on_error_callback(error_msg)
                    
            def on_close(websocket_self, close, **kwargs):
                logger.info("Deepgram connection closed")
                self.is_active = False
                
            # Register handlers
            self.connection.on(LiveTranscriptionEvents.Open, on_open)
            self.connection.on(LiveTranscriptionEvents.Transcript, on_message)
            self.connection.on(LiveTranscriptionEvents.Error, on_error)
            self.connection.on(LiveTranscriptionEvents.Close, on_close)
            
            # Configure diarization options
            options = LiveOptions(
                model="nova-2",
                language="en",
                punctuate=True,
                smart_format=True,
                diarize=True,  # Enable speaker diarization
                encoding="linear16",
                sample_rate=16000,
                channels=1
            )
            
            # Start connection
            if self.connection.start(options):
                self.is_active = True
                logger.info("Diarization service started successfully")
                return True
            else:
                logger.error("Failed to start Deepgram connection")
                return False
                
        except Exception as e:
            logger.error(f"Error starting diarization: {e}")
            if self.on_error_callback:
                self.on_error_callback(f"Failed to start diarization: {e}")
            return False
            
    def _handle_transcript_result(self, result):
        """Handle incoming transcript results from Deepgram"""
        try:
            sentence = result.channel.alternatives[0].transcript
            
            if sentence and sentence.strip():
                # Get speaker info
                speaker_id = 0  # Default to speaker 0
                words = result.channel.alternatives[0].words
                
                # Look for speaker information in words
                if words and len(words) > 0:
                    first_word = words[0]
                    if hasattr(first_word, 'speaker') and first_word.speaker is not None:
                        speaker_id = first_word.speaker
                        
                        # Confirm diarization is working
                        if not self.diarization_enabled:
                            logger.info(f"Speaker diarization confirmed working! Detected speaker {speaker_id}")
                            self.diarization_enabled = True
                
                # Track speakers
                if speaker_id not in self.speakers:
                    speaker_number = len(self.speakers) + 1
                    self.speakers[speaker_id] = f"Speaker {speaker_number}"
                    
                    if len(self.speakers) > 1 and self.on_speaker_change_callback:
                        self.on_speaker_change_callback(speaker_id, self.speakers[speaker_id])
                        
                speaker_name = self.speakers[speaker_id]
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                # Create transcript entry
                transcript_entry = {
                    'time': timestamp,
                    'speaker': speaker_name,
                    'speaker_id': speaker_id,
                    'text': sentence.strip(),
                    'is_final': True
                }
                
                # Store transcript
                self.transcript.append(transcript_entry)
                
                # Call transcript callback
                if self.on_transcript_callback:
                    self.on_transcript_callback(transcript_entry)
                    
        except Exception as e:
            logger.error(f"Error processing transcript: {e}")
            
    def send_audio(self, audio_data: bytes):
        """
        Send audio data to Deepgram for processing
        
        Args:
            audio_data: Raw audio bytes
        """
        if self.connection and self.is_active:
            try:
                self.connection.send(audio_data)
            except Exception as e:
                logger.error(f"Error sending audio data: {e}")
                if self.on_error_callback:
                    self.on_error_callback(f"Audio streaming error: {e}")
                    
    def stop_diarization(self):
        """Stop diarization session"""
        if self.connection and self.is_active:
            try:
                self.is_active = False
                self.connection.finish()
                logger.info("Diarization session stopped")
            except Exception as e:
                logger.error(f"Error stopping diarization: {e}")
                
    def get_transcript_text(self) -> str:
        """
        Get formatted transcript text
        
        Returns:
            str: Formatted transcript with speaker labels
        """
        transcript_text = ""
        for entry in self.transcript:
            transcript_text += f"{entry['speaker']}: {entry['text']}\n"
        return transcript_text.strip()
        
    def get_transcript_data(self) -> List[Dict[str, Any]]:
        """
        Get full transcript data
        
        Returns:
            List of transcript entries
        """
        return self.transcript.copy()
        
    def get_speakers_count(self) -> int:
        """Get number of unique speakers detected"""
        return len(self.speakers)
        
    def get_session_summary(self) -> Dict[str, Any]:
        """
        Get session summary with statistics
        
        Returns:
            Dictionary with session statistics
        """
        speaker_stats = {}
        for entry in self.transcript:
            speaker = entry['speaker']
            if speaker not in speaker_stats:
                speaker_stats[speaker] = {'utterances': 0, 'words': 0}
            speaker_stats[speaker]['utterances'] += 1
            speaker_stats[speaker]['words'] += len(entry['text'].split())
            
        return {
            'diarization_enabled': self.diarization_enabled,
            'speakers_detected': len(self.speakers),
            'speakers': list(self.speakers.values()),
            'speaker_stats': speaker_stats,
            'total_utterances': len(self.transcript),
            'session_duration': self._calculate_session_duration()
        }
        
    def _calculate_session_duration(self) -> str:
        """Calculate session duration"""
        if not self.transcript:
            return "00:00:00"
            
        start_time = self.transcript[0]['time']
        end_time = self.transcript[-1]['time']
        
        try:
            start_dt = datetime.strptime(start_time, "%H:%M:%S")
            end_dt = datetime.strptime(end_time, "%H:%M:%S")
            duration = end_dt - start_dt
            return str(duration)
        except:
            return "Unknown"
            
    def clear_session(self):
        """Clear current session data"""
        self.speakers = {}
        self.transcript = []
        self.diarization_enabled = False


class WebSocketDiarizationHandler:
    """WebSocket handler for real-time diarization"""
    
    def __init__(self, deepgram_service: DeepgramDiarizationService):
        self.deepgram_service = deepgram_service
        self.websocket = None
        
    async def handle_client(self, websocket, path):
        """Handle WebSocket client connection"""
        self.websocket = websocket
        logger.info("WebSocket client connected")
        
        # Set up callbacks to send data to client
        self.deepgram_service.set_callbacks(
            on_transcript=self._send_transcript,
            on_speaker_change=self._send_speaker_change,
            on_error=self._send_error
        )
        
        try:
            # Start Deepgram session
            await self.deepgram_service.start_diarization()
            
            # Handle incoming audio data
            async for message in websocket:
                if isinstance(message, bytes):
                    # Audio data
                    self.deepgram_service.send_audio(message)
                else:
                    # Control message
                    try:
                        data = json.loads(message)
                        await self._handle_control_message(data)
                    except json.JSONDecodeError:
                        logger.error("Invalid JSON message received")
                        
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket client disconnected")
        finally:
            self.deepgram_service.stop_diarization()
            
    async def _handle_control_message(self, data: Dict[str, Any]):
        """Handle control messages from client"""
        command = data.get('command')
        
        if command == 'get_summary':
            summary = self.deepgram_service.get_session_summary()
            await self._send_to_client({
                'type': 'summary',
                'data': summary
            })
        elif command == 'clear_session':
            self.deepgram_service.clear_session()
            await self._send_to_client({
                'type': 'session_cleared'
            })
            
    async def _send_transcript(self, transcript_entry: Dict[str, Any]):
        """Send transcript update to client"""
        await self._send_to_client({
            'type': 'transcript',
            'data': transcript_entry
        })
        
    async def _send_speaker_change(self, speaker_id: int, speaker_name: str):
        """Send speaker change notification to client"""
        await self._send_to_client({
            'type': 'speaker_change',
            'data': {
                'speaker_id': speaker_id,
                'speaker_name': speaker_name
            }
        })
        
    async def _send_error(self, error_message: str):
        """Send error message to client"""
        await self._send_to_client({
            'type': 'error',
            'message': error_message
        })
        
    async def _send_to_client(self, message: Dict[str, Any]):
        """Send message to WebSocket client"""
        if self.websocket:
            try:
                await self.websocket.send(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to client: {e}")
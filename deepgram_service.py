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
        
        # Advanced speaker transition handling
        self.last_speaker_id = None
        self.speaker_confidence_threshold = 0.75
        self.min_words_for_speaker_change = 2
        self.pending_segments = []  # Buffer for handling transitions
        
        # Speaker consistency tracking
        self.speaker_history = []  # Track last N speaker assignments
        self.history_size = 10
        self.speaker_timings = {}  # Track timing patterns per speaker
        self.speaker_consistency_scores = {}  # Track consistency per speaker
        
        # Advanced detection parameters
        self.min_segment_duration = 0.3  # Minimum seconds for a valid segment
        self.max_rapid_switch_time = 1.0  # Max time for rapid switching detection
        self.consistency_weight = 0.6  # Weight for historical consistency
        self.timing_weight = 0.4  # Weight for timing patterns
        
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
        
    def start_diarization(self) -> bool:
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
            
            # Configure diarization options (using stable settings)
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
        """Handle incoming transcript results from Deepgram with improved speaker transition handling"""
        try:
            sentence = result.channel.alternatives[0].transcript
            
            if sentence and sentence.strip():
                words = result.channel.alternatives[0].words
                
                if not words or len(words) == 0:
                    # No word-level data, use last known speaker
                    speaker_id = self.last_speaker_id if self.last_speaker_id is not None else 0
                    self._process_single_speaker_segment(sentence.strip(), speaker_id)
                else:
                    # Process word-level speaker information
                    self._process_words_with_speakers(words, sentence.strip())
                    
        except Exception as e:
            logger.error(f"Error processing transcript: {e}")
    
    def _process_words_with_speakers(self, words, full_text):
        """Process words with advanced speaker detection and validation"""
        # Extract word-level speaker information with timing
        word_data = []
        for word in words:
            speaker_id = 0  # Default speaker
            confidence = 0.0
            
            # Extract speaker ID and confidence if available
            if hasattr(word, 'speaker') and word.speaker is not None:
                speaker_id = word.speaker
                confidence = getattr(word, 'confidence', 0.8)  # Default confidence
                
                # Confirm diarization is working
                if not self.diarization_enabled:
                    logger.info(f"Speaker diarization confirmed working! Detected speaker {speaker_id}")
                    self.diarization_enabled = True
            
            word_info = {
                'text': word.word if hasattr(word, 'word') else str(word),
                'speaker_id': speaker_id,
                'confidence': confidence,
                'start_time': getattr(word, 'start', 0.0),
                'end_time': getattr(word, 'end', 0.0),
                'duration': getattr(word, 'end', 0.0) - getattr(word, 'start', 0.0)
            }
            word_data.append(word_info)
        
        # Apply advanced speaker detection algorithm
        validated_segments = self._validate_speaker_assignments(word_data)
        
        # Process validated segments
        self._process_validated_segments(validated_segments)
    
    def _validate_speaker_assignments(self, word_data):
        """Apply advanced validation to speaker assignments"""
        if not word_data:
            return []
        
        validated_words = []
        
        for i, word in enumerate(word_data):
            original_speaker = word['speaker_id']
            
            # Get context window
            context_start = max(0, i - 3)
            context_end = min(len(word_data), i + 4)
            context_words = word_data[context_start:context_end]
            
            # Calculate speaker consistency in context
            speaker_votes = {}
            total_confidence = 0
            
            for ctx_word in context_words:
                sid = ctx_word['speaker_id']
                conf = ctx_word['confidence']
                
                if sid not in speaker_votes:
                    speaker_votes[sid] = {'count': 0, 'confidence': 0}
                
                speaker_votes[sid]['count'] += 1
                speaker_votes[sid]['confidence'] += conf
                total_confidence += conf
            
            # Determine most consistent speaker
            best_speaker = original_speaker
            best_score = 0
            
            for sid, data in speaker_votes.items():
                # Score based on count, confidence, and historical consistency
                count_score = data['count'] / len(context_words)
                conf_score = (data['confidence'] / data['count']) if data['count'] > 0 else 0
                history_score = self._get_speaker_consistency_score(sid)
                
                combined_score = (
                    count_score * 0.4 + 
                    conf_score * 0.3 + 
                    history_score * 0.3
                )
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_speaker = sid
            
            # Apply temporal consistency checks
            validated_speaker = self._apply_temporal_validation(
                best_speaker, word, i, word_data
            )
            
            # Create validated word
            validated_word = word.copy()
            validated_word['speaker_id'] = validated_speaker
            validated_word['validation_confidence'] = best_score
            validated_words.append(validated_word)
            
            # Update speaker history
            self._update_speaker_history(validated_speaker)
        
        # Group into segments
        return self._group_into_segments(validated_words)
    
    def _apply_temporal_validation(self, proposed_speaker, word, word_index, word_data):
        """Apply temporal consistency validation"""
        # Check for rapid speaker switching (likely errors)
        if word_index > 0:
            prev_word = word_data[word_index - 1]
            time_gap = word['start_time'] - prev_word['end_time']
            
            # If very rapid switch and short segment, validate carefully
            if time_gap < self.max_rapid_switch_time:
                if word['duration'] < self.min_segment_duration:
                    # Check if this creates a very short segment
                    if self._would_create_short_segment(proposed_speaker, word_index, word_data):
                        # Keep with previous speaker to avoid fragmentation
                        return self.last_speaker_id or proposed_speaker
        
        # Check speaker timing patterns
        if proposed_speaker in self.speaker_timings:
            expected_duration = self.speaker_timings[proposed_speaker].get('avg_duration', 1.0)
            if word['duration'] < expected_duration * 0.1:  # Too short for this speaker
                # Look for alternative in context
                return self._find_contextual_speaker(word_index, word_data)
        
        return proposed_speaker
    
    def _would_create_short_segment(self, speaker_id, word_index, word_data):
        """Check if assigning this speaker would create a very short segment"""
        # Count consecutive words that would belong to this speaker
        segment_length = 1
        
        # Look backwards
        for i in range(word_index - 1, -1, -1):
            if word_data[i]['speaker_id'] == speaker_id:
                segment_length += 1
            else:
                break
        
        # Look forwards
        for i in range(word_index + 1, len(word_data)):
            if word_data[i]['speaker_id'] == speaker_id:
                segment_length += 1
            else:
                break
        
        return segment_length < self.min_words_for_speaker_change
    
    def _find_contextual_speaker(self, word_index, word_data):
        """Find the most likely speaker based on surrounding context"""
        context_range = 2
        start_idx = max(0, word_index - context_range)
        end_idx = min(len(word_data), word_index + context_range + 1)
        
        speaker_counts = {}
        for i in range(start_idx, end_idx):
            if i != word_index:
                sid = word_data[i]['speaker_id']
                speaker_counts[sid] = speaker_counts.get(sid, 0) + 1
        
        if speaker_counts:
            return max(speaker_counts, key=speaker_counts.get)
        
        return self.last_speaker_id or 0
    
    def _get_speaker_consistency_score(self, speaker_id):
        """Get historical consistency score for a speaker"""
        if speaker_id not in self.speaker_consistency_scores:
            return 0.5  # Neutral score for new speakers
        return self.speaker_consistency_scores[speaker_id]
    
    def _update_speaker_history(self, speaker_id):
        """Update speaker assignment history"""
        self.speaker_history.append(speaker_id)
        if len(self.speaker_history) > self.history_size:
            self.speaker_history.pop(0)
        
        # Update consistency scores
        if len(self.speaker_history) >= 3:
            # Calculate consistency as ratio of stable assignments
            stable_count = 0
            for i in range(1, len(self.speaker_history) - 1):
                if (self.speaker_history[i] == self.speaker_history[i-1] or 
                    self.speaker_history[i] == self.speaker_history[i+1]):
                    stable_count += 1
            
            consistency = stable_count / (len(self.speaker_history) - 2) if len(self.speaker_history) > 2 else 0.5
            self.speaker_consistency_scores[speaker_id] = consistency
    
    def _group_into_segments(self, validated_words):
        """Group validated words into coherent segments"""
        if not validated_words:
            return []
        
        segments = []
        current_segment = {
            'speaker_id': validated_words[0]['speaker_id'],
            'words': [validated_words[0]['text']],
            'start_time': validated_words[0]['start_time'],
            'end_time': validated_words[0]['end_time'],
            'confidence': validated_words[0]['validation_confidence']
        }
        
        for word in validated_words[1:]:
            if word['speaker_id'] == current_segment['speaker_id']:
                # Continue current segment
                current_segment['words'].append(word['text'])
                current_segment['end_time'] = word['end_time']
                current_segment['confidence'] = max(current_segment['confidence'], 
                                                  word['validation_confidence'])
            else:
                # Start new segment
                segments.append(current_segment)
                current_segment = {
                    'speaker_id': word['speaker_id'],
                    'words': [word['text']],
                    'start_time': word['start_time'],
                    'end_time': word['end_time'],
                    'confidence': word['validation_confidence']
                }
        
        segments.append(current_segment)
        return segments
    
    def _process_validated_segments(self, segments):
        """Process validated speaker segments"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        for segment in segments:
            speaker_id = segment['speaker_id']
            text = ' '.join(segment['words'])
            
            # Track speakers
            if speaker_id not in self.speakers:
                speaker_number = len(self.speakers) + 1
                self.speakers[speaker_id] = f"Speaker {speaker_number}"
                
                # Update timing patterns for new speaker
                self.speaker_timings[speaker_id] = {
                    'avg_duration': segment['end_time'] - segment['start_time'],
                    'segment_count': 1
                }
                
                if len(self.speakers) > 1 and self.on_speaker_change_callback:
                    self.on_speaker_change_callback(speaker_id, self.speakers[speaker_id])
            else:
                # Update timing patterns
                if speaker_id in self.speaker_timings:
                    timing = self.speaker_timings[speaker_id]
                    segment_duration = segment['end_time'] - segment['start_time']
                    timing['avg_duration'] = (
                        (timing['avg_duration'] * timing['segment_count'] + segment_duration) /
                        (timing['segment_count'] + 1)
                    )
                    timing['segment_count'] += 1
            
            # Create transcript entry with confidence
            speaker_name = self.speakers[speaker_id]
            transcript_entry = {
                'time': timestamp,
                'speaker': speaker_name,
                'speaker_id': speaker_id,
                'text': text.strip(),
                'confidence': segment['confidence'],
                'is_final': True
            }
            
            # Store transcript
            self.transcript.append(transcript_entry)
            
            # Call transcript callback
            if self.on_transcript_callback:
                self.on_transcript_callback(transcript_entry)
            
            # Update last speaker
            self.last_speaker_id = speaker_id
            
            logger.debug(f"Processed segment: Speaker {speaker_id}, confidence {segment['confidence']:.2f}, text: '{text[:50]}...'")
    
    def _process_single_speaker_segment(self, text, speaker_id):
        """Process a segment with a single speaker"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Track speakers
        if speaker_id not in self.speakers:
            speaker_number = len(self.speakers) + 1
            self.speakers[speaker_id] = f"Speaker {speaker_number}"
            
            if len(self.speakers) > 1 and self.on_speaker_change_callback:
                self.on_speaker_change_callback(speaker_id, self.speakers[speaker_id])
        
        speaker_name = self.speakers[speaker_id]
        
        # Create transcript entry
        transcript_entry = {
            'time': timestamp,
            'speaker': speaker_name,
            'speaker_id': speaker_id,
            'text': text,
            'is_final': True
        }
        
        # Store transcript
        self.transcript.append(transcript_entry)
        
        # Call transcript callback
        if self.on_transcript_callback:
            self.on_transcript_callback(transcript_entry)
        
        # Update last speaker
        self.last_speaker_id = speaker_id
            
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
        
        # Clear advanced tracking data
        self.last_speaker_id = None
        self.speaker_history = []
        self.speaker_timings = {}
        self.speaker_consistency_scores = {}
        self.pending_segments = []


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
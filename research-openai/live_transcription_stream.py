#!/usr/bin/env python3
"""
Live Speaker Attribution + Transcription Stream
Real-time speaker identification with speech-to-text transcription
"""

import os
import json
import time
import threading
import queue
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import logging

import speech_recognition as sr
import google.generativeai as genai
from live_speaker_stream import LiveSpeakerStream, LiveSpeakerEvent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class TranscriptionSegment:
    """Transcribed speech segment with speaker attribution"""
    timestamp: datetime
    speaker_id: str
    identified_name: Optional[str]
    text: str
    confidence: float
    duration: float

class LiveTranscriptionStream(LiveSpeakerStream):
    """Live speaker attribution with real-time transcription"""
    
    def __init__(self, 
                 gemini_api_key: str,
                 hf_token: Optional[str] = None,
                 transcription_method: str = "google",  # "google", "whisper", "gemini"
                 chunk_duration: float = 3.0,
                 **kwargs):
        """
        Initialize live transcription stream
        
        Args:
            transcription_method: Method for speech-to-text ("google", "whisper", "gemini")
            Other args passed to LiveSpeakerStream
        """
        super().__init__(gemini_api_key, hf_token, chunk_duration, **kwargs)
        
        self.transcription_method = transcription_method
        
        # Transcription components
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone(device_index=self.device_index)
        
        # Transcription buffer and history
        self.transcription_queue = queue.Queue()
        self.transcription_history = []
        self.current_transcription = ""
        
        # Threading for transcription
        self.transcription_thread = None
        self.transcription_active = False
        
        # Initialize Gemini for transcription if selected
        if transcription_method == "gemini":
            genai.configure(api_key=gemini_api_key)
            self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
        # Calibrate microphone
        self._calibrate_microphone()
        
        logger.info(f"Live transcription stream initialized with {transcription_method}")
        
    def _calibrate_microphone(self):
        """Calibrate microphone for ambient noise"""
        try:
            print("Calibrating microphone for ambient noise...")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=2)
            print("Microphone calibrated.")
        except Exception as e:
            logger.warning(f"Microphone calibration failed: {e}")
            
    def start_streaming(self):
        """Start both speaker attribution and transcription"""
        super().start_streaming()
        
        # Start transcription thread
        self.transcription_active = True
        self.transcription_thread = threading.Thread(target=self._transcription_loop)
        self.transcription_thread.daemon = True
        self.transcription_thread.start()
        
        logger.info("Live transcription streaming started")
        
    def stop_streaming(self):
        """Stop both speaker attribution and transcription"""
        self.transcription_active = False
        
        if self.transcription_thread:
            self.transcription_thread.join(timeout=2.0)
            
        super().stop_streaming()
        logger.info("Live transcription streaming stopped")
        
    def _transcription_loop(self):
        """Continuous transcription loop"""
        logger.info("Transcription loop started")
        
        while self.transcription_active:
            try:
                # Listen for audio
                with self.microphone as source:
                    # Listen with timeout
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=self.chunk_duration)
                    
                # Add to transcription queue
                self.transcription_queue.put((audio, datetime.now()))
                
                # Process transcription
                self._process_transcription_queue()
                
            except sr.WaitTimeoutError:
                # Normal timeout, continue listening
                pass
            except Exception as e:
                logger.error(f"Transcription loop error: {e}")
                time.sleep(0.1)
                
        logger.info("Transcription loop stopped")
        
    def _process_transcription_queue(self):
        """Process queued transcription requests"""
        while not self.transcription_queue.empty():
            try:
                audio, timestamp = self.transcription_queue.get_nowait()
                
                # Transcribe audio
                text = self._transcribe_audio(audio)
                
                if text and text.strip():
                    # Get current speaker info
                    current_speaker = self.get_current_speakers()
                    speaker_id = current_speaker.get('active', 'Unknown')
                    confidence = current_speaker.get('confidence', 0.0)
                    
                    # Create transcription segment
                    segment = TranscriptionSegment(
                        timestamp=timestamp,
                        speaker_id=speaker_id,
                        identified_name=speaker_id if speaker_id != 'Unknown' else None,
                        text=text,
                        confidence=confidence,
                        duration=self.chunk_duration
                    )
                    
                    # Add to history
                    self.transcription_history.append(segment)
                    
                    # Update current transcription
                    self.current_transcription = text
                    
                    # Trigger callback
                    self._trigger_callback('transcription', segment)
                    
            except queue.Empty:
                break
            except Exception as e:
                logger.error(f"Transcription processing error: {e}")
                
    def _transcribe_audio(self, audio) -> str:
        """Transcribe audio using selected method"""
        try:
            if self.transcription_method == "google":
                return self._transcribe_google(audio)
            elif self.transcription_method == "whisper":
                return self._transcribe_whisper(audio)
            elif self.transcription_method == "gemini":
                return self._transcribe_gemini(audio)
            else:
                logger.error(f"Unknown transcription method: {self.transcription_method}")
                return ""
                
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""
            
    def _transcribe_google(self, audio) -> str:
        """Transcribe using Google Speech Recognition"""
        try:
            return self.recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            logger.error(f"Google Speech Recognition error: {e}")
            return ""
            
    def _transcribe_whisper(self, audio) -> str:
        """Transcribe using OpenAI Whisper"""
        try:
            return self.recognizer.recognize_whisper(audio)
        except sr.UnknownValueError:
            return ""
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return ""
            
    def _transcribe_gemini(self, audio) -> str:
        """Transcribe using Gemini API"""
        try:
            # Save audio to temporary file
            temp_file = f"temp_audio_{int(time.time())}.wav"
            with open(temp_file, "wb") as f:
                f.write(audio.get_wav_data())
                
            # Upload to Gemini
            # Note: This is a simplified example - Gemini's audio capabilities may vary
            # You might need to convert audio or use a different approach
            
            # For now, fall back to Google
            result = self._transcribe_google(audio)
            
            # Clean up
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
            return result
            
        except Exception as e:
            logger.error(f"Gemini transcription error: {e}")
            return ""
            
    def get_transcription_history(self, minutes: int = 10) -> List[TranscriptionSegment]:
        """Get recent transcription history"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [seg for seg in self.transcription_history if seg.timestamp >= cutoff_time]
        
    def get_current_transcription(self) -> str:
        """Get current transcription text"""
        return self.current_transcription
        
    def export_transcription(self, filename: str, format: str = "json"):
        """Export transcription in various formats"""
        if format == "json":
            data = []
            for seg in self.transcription_history:
                data.append({
                    "timestamp": seg.timestamp.isoformat(),
                    "speaker": seg.identified_name or seg.speaker_id,
                    "text": seg.text,
                    "confidence": seg.confidence
                })
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
                
        elif format == "txt":
            with open(filename, 'w') as f:
                for seg in self.transcription_history:
                    speaker = seg.identified_name or seg.speaker_id
                    timestamp = seg.timestamp.strftime("%H:%M:%S")
                    f.write(f"[{timestamp}] {speaker}: {seg.text}\n")
                    
        elif format == "srt":
            # Subtitle format
            with open(filename, 'w') as f:
                for i, seg in enumerate(self.transcription_history, 1):
                    start_time = seg.timestamp.strftime("%H:%M:%S,000")
                    end_time = (seg.timestamp + timedelta(seconds=seg.duration)).strftime("%H:%M:%S,000")
                    speaker = seg.identified_name or seg.speaker_id
                    
                    f.write(f"{i}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{speaker}: {seg.text}\n\n")
                    
        logger.info(f"Transcription exported to {filename}")
        
    def get_speaker_dialogue(self, speaker_name: str) -> List[str]:
        """Get all dialogue from a specific speaker"""
        return [seg.text for seg in self.transcription_history 
                if (seg.identified_name == speaker_name or seg.speaker_id == speaker_name)]
        
    def search_transcription(self, query: str) -> List[TranscriptionSegment]:
        """Search transcription for specific text"""
        query_lower = query.lower()
        return [seg for seg in self.transcription_history 
                if query_lower in seg.text.lower()]


def main():
    """Example usage of live transcription stream"""
    import argparse
    from datetime import timedelta
    
    parser = argparse.ArgumentParser(description="Live Speaker Attribution + Transcription")
    parser.add_argument("--gemini-key", default="AIzaSyAJ_uGXKX_Rg0FO5rdSMPEHdlw-0G76E7g", help="Gemini API key")
    parser.add_argument("--hf-token", help="HuggingFace token")
    parser.add_argument("--device", type=int, help="Audio device index")
    parser.add_argument("--transcription", default="google", choices=["google", "whisper", "gemini"], 
                       help="Transcription method")
    parser.add_argument("--chunk-duration", type=float, default=3.0, help="Processing chunk duration")
    parser.add_argument("--list-devices", action="store_true", help="List audio devices and exit")
    
    args = parser.parse_args()
    
    # Initialize live stream
    stream = LiveTranscriptionStream(
        gemini_api_key=args.gemini_key,
        hf_token=args.hf_token,
        transcription_method=args.transcription,
        device_index=args.device,
        chunk_duration=args.chunk_duration
    )
    
    # List devices if requested
    if args.list_devices:
        stream.list_audio_devices()
        return
    
    # Set up callbacks for live feedback
    def on_speaker_detected(event: LiveSpeakerEvent):
        speaker = event.identified_name or event.speaker_id
        print(f"\n🎤 {speaker} is speaking")
    
    def on_transcription(segment: TranscriptionSegment):
        speaker = segment.identified_name or segment.speaker_id
        timestamp = segment.timestamp.strftime("%H:%M:%S")
        print(f"[{timestamp}] {speaker}: {segment.text}")
    
    def on_speaker_changed(data):
        print(f"\n👥 Speaker changed: {data['from']} → {data['to']}")
    
    stream.add_callback('speaker_detected', on_speaker_detected)
    stream.add_callback('transcription', on_transcription)
    stream.add_callback('speaker_changed', on_speaker_changed)
    
    print("Live Speaker Attribution + Transcription")
    print("=" * 50)
    print(f"Transcription method: {args.transcription}")
    print("Commands:")
    print("  's' - Show current speaker stats")
    print("  't' - Show recent transcription")
    print("  'h' - Show recent history")
    print("  'e <name>' - Enroll new speaker")
    print("  'search <text>' - Search transcription")
    print("  'export <format>' - Export (json/txt/srt)")
    print("  'q' - Quit")
    print("=" * 50)
    print("Starting... Speak into your microphone!")
    
    # Start streaming
    stream.start_streaming()
    
    try:
        while True:
            command = input().strip()
            
            if command.lower() == 'q':
                break
            elif command.lower() == 's':
                stats = stream.get_speaker_stats()
                print("\n📊 Speaker Statistics:")
                for speaker, data in stats.items():
                    print(f"  {speaker}: {data['total_time']:.1f}s ({data['segment_count']} segments)")
                    
            elif command.lower() == 't':
                history = stream.get_transcription_history(minutes=5)
                print(f"\n📝 Recent Transcription ({len(history)} segments):")
                for seg in history[-10:]:
                    speaker = seg.identified_name or seg.speaker_id
                    timestamp = seg.timestamp.strftime("%H:%M:%S")
                    print(f"  [{timestamp}] {speaker}: {seg.text}")
                    
            elif command.lower() == 'h':
                history = stream.get_recent_history(minutes=5)
                print(f"\n🕒 Recent History ({len(history)} events):")
                for event in history[-10:]:
                    speaker = event.identified_name or event.speaker_id
                    timestamp = event.timestamp.strftime("%H:%M:%S")
                    print(f"  [{timestamp}] {speaker} spoke for {event.duration:.1f}s")
                    
            elif command.lower().startswith('e '):
                name = command[2:].strip()
                if name:
                    stream.enroll_speaker_live(name, duration=5.0)
                    
            elif command.lower().startswith('search '):
                query = command[7:].strip()
                if query:
                    results = stream.search_transcription(query)
                    print(f"\n🔍 Search results for '{query}' ({len(results)} matches):")
                    for seg in results:
                        speaker = seg.identified_name or seg.speaker_id
                        timestamp = seg.timestamp.strftime("%H:%M:%S")
                        print(f"  [{timestamp}] {speaker}: {seg.text}")
                        
            elif command.lower().startswith('export '):
                format_type = command[7:].strip().lower()
                if format_type in ['json', 'txt', 'srt']:
                    filename = f"transcription_{int(time.time())}.{format_type}"
                    stream.export_transcription(filename, format_type)
                    print(f"📁 Exported to {filename}")
                else:
                    print("❌ Invalid format. Use: json, txt, or srt")
                    
            elif command:
                print("❓ Unknown command. Type a command or 'q' to quit.")
                
    except KeyboardInterrupt:
        pass
    
    # Save session and cleanup
    timestamp = int(time.time())
    stream.save_session(f"session_{timestamp}.json")
    stream.export_transcription(f"transcription_{timestamp}.txt", "txt")
    stream.stop_streaming()
    print("\n✅ Session ended. Files saved.")


if __name__ == "__main__":
    main()
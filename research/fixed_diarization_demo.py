#!/usr/bin/env python3
"""
Fixed Live Demo with Working Speaker Diarization
Based on successful connection test
"""

import pyaudio
import json
import threading
import time
from datetime import datetime
from deepgram import (
    DeepgramClient,
    LiveTranscriptionEvents,
    LiveOptions
)

# Your API Key
API_KEY = "50ea35eadaddeda4d3779c93b2f2cf27bcd7e14c"

class FixedDiarizationDemo:
    def __init__(self):
        self.deepgram = DeepgramClient(API_KEY)
        self.speakers = {}
        self.transcript = []
        self.is_recording = False
        self.diarization_enabled = False
        
    def run(self):
        """Run live transcript demo with fixed diarization"""
        print("\nLIVE TRANSCRIPT WITH SPEAKER DIARIZATION")
        print("=" * 60)
        print("Starting live speech-to-text with speaker detection")
        print("Speak into your microphone now!")
        print("Press Ctrl+C to stop")
        print("=" * 60)
        
        try:
            # Create connection
            dg_connection = self.deepgram.listen.websocket.v("1")
            
            # Connection opened
            def on_open(websocket_self, open, **kwargs):
                diarization_status = "WITH" if self.diarization_enabled else "WITHOUT"
                print(f"Connected to Deepgram {diarization_status} speaker diarization!")
                print("\nLIVE TRANSCRIPT:")
                print("-" * 60)
            
            # Handle live transcript
            def on_message(websocket_self, result, **kwargs):
                """Display live transcript immediately"""
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
                                    print(f"Speaker diarization confirmed working! Detected speaker {speaker_id}")
                                    self.diarization_enabled = True
                        
                        # Track speakers
                        if speaker_id not in self.speakers:
                            speaker_number = len(self.speakers) + 1
                            self.speakers[speaker_id] = f"Speaker {speaker_number}"
                            if len(self.speakers) > 1:
                                print(f"NEW SPEAKER DETECTED: {self.speakers[speaker_id]} (ID: {speaker_id})")
                        
                        speaker_name = self.speakers[speaker_id]
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        
                        # Color coding for different speakers
                        colors = [
                            '\033[94m',  # Blue
                            '\033[92m',  # Green  
                            '\033[93m',  # Yellow
                            '\033[95m',  # Magenta
                            '\033[96m',  # Cyan
                            '\033[91m'   # Red
                        ]
                        color = colors[speaker_id % len(colors)]
                        reset = '\033[0m'
                        
                        # LIVE DISPLAY with enhanced formatting
                        print(f"[{timestamp}] {color}{speaker_name}{reset}: {sentence}")
                        
                        # Store
                        self.transcript.append({
                            'time': timestamp,
                            'speaker': speaker_name,
                            'speaker_id': speaker_id,
                            'text': sentence
                        })
                        
                except Exception as e:
                    print(f"Error processing transcript: {e}")
            
            def on_error(websocket_self, error, **kwargs):
                print(f"Deepgram Error: {error}")
            
            # Register handlers
            dg_connection.on(LiveTranscriptionEvents.Open, on_open)
            dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
            dg_connection.on(LiveTranscriptionEvents.Error, on_error)
            
            # Use the EXACT configuration that worked in our test
            print("Connecting with diarization (using tested configuration)...")
            
            diarization_options = LiveOptions(
                model="nova-2",
                language="en",
                punctuate=True,
                smart_format=True,
                diarize=True,  # Enable speaker diarization
                encoding="linear16",
                sample_rate=16000,
                channels=1
            )
            
            # Attempt connection
            if dg_connection.start(diarization_options):
                print("Diarization connection successful!")
                self.diarization_enabled = True
            else:
                print("Diarization connection failed, this shouldn't happen based on our tests")
                return
            
            # Setup microphone
            self.is_recording = True
            
            def stream_audio():
                """Stream audio to Deepgram"""
                RATE = 16000
                CHUNK = 1024
                
                p = pyaudio.PyAudio()
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK
                )
                
                print("Audio streaming started...")
                
                try:
                    while self.is_recording:
                        data = stream.read(CHUNK, exception_on_overflow=False)
                        dg_connection.send(data)
                        time.sleep(0.01)
                except Exception as e:
                    print(f"Audio streaming error: {e}")
                finally:
                    stream.stop_stream()
                    stream.close()
                    p.terminate()
            
            # Start audio streaming in background
            audio_thread = threading.Thread(target=stream_audio, daemon=True)
            audio_thread.start()
            
            print("\nREADY! Start speaking now...")
            print("Have different people speak to test speaker detection")
            print("-" * 60)
            
            # Keep running until interrupted
            try:
                while self.is_recording:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n\nStopping live transcript...")
                self.is_recording = False
            
            # Cleanup
            audio_thread.join(timeout=2)
            dg_connection.finish()
            
            # Show summary
            self.show_summary()
            
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
    
    def show_summary(self):
        """Show session summary"""
        print("\n" + "=" * 60)
        print("SESSION SUMMARY")
        print("=" * 60)
        
        print(f"Diarization Status: {'ENABLED' if self.diarization_enabled else 'DISABLED'}")
        
        if self.transcript:
            print(f"Captured {len(self.transcript)} utterances")
            print(f"Detected {len(self.speakers)} unique speaker(s):")
            
            # Show speaker statistics
            speaker_stats = {}
            for t in self.transcript:
                speaker = t['speaker']
                speaker_stats[speaker] = speaker_stats.get(speaker, 0) + 1
            
            for speaker, count in speaker_stats.items():
                words = sum(len(t['text'].split()) for t in self.transcript if t['speaker'] == speaker)
                print(f"   • {speaker}: {count} utterances, {words} words")
            
            # Save transcript
            filename = f"diarized_transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump({
                    'session_date': datetime.now().isoformat(),
                    'diarization_enabled': self.diarization_enabled,
                    'speakers_detected': len(self.speakers),
                    'speakers': list(self.speakers.values()),
                    'speaker_stats': speaker_stats,
                    'transcript': self.transcript
                }, f, indent=2)
            
            print(f"\nFull transcript saved to: {filename}")
            
            # Show if diarization actually worked
            if len(self.speakers) > 1:
                print("\nSUCCESS: Multiple speakers were detected!")
            elif self.diarization_enabled:
                print("\nOnly one speaker detected - try having different people speak")
            else:
                print("\nDiarization didn't activate - speaker detection unavailable")
        else:
            print("No speech was detected")
            print("   Make sure your microphone is working and speak clearly")


if __name__ == "__main__":
    print("\nFIXED LIVE DIARIZATION DEMO")
    print("This uses the exact configuration that passed our connection tests")
    
    try:
        demo = FixedDiarizationDemo()
        demo.run()
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\nDemo complete!")
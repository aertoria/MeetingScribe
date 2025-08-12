#!/usr/bin/env python3
"""
Live Speaker Attribution with Microphone Streaming
Real-time speaker identification from microphone input
"""

import os
import json
import time
import threading
from collections import deque, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
import numpy as np
import pyaudio
import wave
import torch
import torchaudio
from datetime import datetime, timedelta
import logging

from speaker_attribution import SpeakerAttributionSystem, SpeakerSegment

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class LiveSpeakerEvent:
    """Event for live speaker detection"""
    timestamp: datetime
    speaker_id: str
    identified_name: Optional[str]
    confidence: float
    duration: float
    audio_level: float

class LiveSpeakerStream:
    """Live speaker attribution from microphone input"""
    
    def __init__(self, 
                 gemini_api_key: str,
                 hf_token: Optional[str] = None,
                 chunk_duration: float = 3.0,
                 sample_rate: int = 16000,
                 channels: int = 1,
                 device_index: Optional[int] = None):
        """
        Initialize live speaker stream
        
        Args:
            gemini_api_key: Gemini API key
            hf_token: HuggingFace token
            chunk_duration: Duration of each processing chunk (seconds)
            sample_rate: Audio sample rate
            channels: Number of audio channels
            device_index: Specific microphone device index
        """
        
        # Audio settings
        self.chunk_duration = chunk_duration
        self.sample_rate = sample_rate
        self.channels = channels
        self.device_index = device_index
        self.chunk_size = 1024
        
        # Initialize speaker attribution system
        self.speaker_system = SpeakerAttributionSystem(
            gemini_api_key=gemini_api_key,
            hf_token=hf_token
        )
        
        # Audio components
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.is_recording = False
        
        # Buffer management
        self.audio_buffer = deque(maxlen=int(sample_rate * chunk_duration * 2))  # 2x chunk duration
        self.processing_buffer = []
        
        # Live tracking
        self.current_speakers = {}
        self.speaker_history = deque(maxlen=100)
        self.speaker_stats = defaultdict(lambda: {"total_time": 0, "segment_count": 0})
        
        # Callbacks
        self.callbacks = {
            'speaker_detected': [],
            'speaker_changed': [],
            'audio_level': [],
            'error': []
        }
        
        # Threading
        self.processing_thread = None
        self.stop_processing = threading.Event()
        
        # Voice activity detection
        self.vad_threshold = 0.01
        self.silence_duration = 1.0  # seconds of silence before processing
        self.last_audio_time = time.time()
        
        logger.info("Live speaker stream initialized")
        
    def list_audio_devices(self):
        """List available audio input devices"""
        print("Available audio input devices:")
        print("-" * 50)
        
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"Device {i}: {info['name']}")
                print(f"  Channels: {info['maxInputChannels']}")
                print(f"  Sample Rate: {info['defaultSampleRate']}")
                print()
                
    def add_callback(self, event_type: str, callback: Callable):
        """
        Add callback for live events
        
        Args:
            event_type: 'speaker_detected', 'speaker_changed', 'audio_level', 'error'
            callback: Function to call
        """
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
            
    def _trigger_callback(self, event_type: str, data):
        """Trigger callbacks for event"""
        for callback in self.callbacks.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
                
    def start_streaming(self):
        """Start live audio streaming and processing"""
        if self.is_recording:
            logger.warning("Already recording")
            return
            
        try:
            # Open audio stream
            self.stream = self.audio.open(
                format=pyaudio.paFloat32,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )
            
            self.is_recording = True
            self.stop_processing.clear()
            
            # Start processing thread
            self.processing_thread = threading.Thread(target=self._processing_loop)
            self.processing_thread.daemon = True
            self.processing_thread.start()
            
            self.stream.start_stream()
            logger.info("Live streaming started")
            
        except Exception as e:
            logger.error(f"Failed to start streaming: {e}")
            self._trigger_callback('error', str(e))
            
    def stop_streaming(self):
        """Stop live audio streaming"""
        if not self.is_recording:
            return
            
        self.is_recording = False
        self.stop_processing.set()
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            
        if self.processing_thread:
            self.processing_thread.join(timeout=2.0)
            
        logger.info("Live streaming stopped")
        
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Audio stream callback"""
        if status:
            logger.warning(f"Audio callback status: {status}")
            
        # Convert to numpy array
        audio_data = np.frombuffer(in_data, dtype=np.float32)
        
        # Calculate audio level
        audio_level = np.sqrt(np.mean(audio_data ** 2))
        self._trigger_callback('audio_level', audio_level)
        
        # Add to buffer if above threshold
        if audio_level > self.vad_threshold:
            self.audio_buffer.extend(audio_data)
            self.last_audio_time = time.time()
            
        return (None, pyaudio.paContinue)
        
    def _processing_loop(self):
        """Main processing loop for speaker attribution"""
        logger.info("Processing loop started")
        
        while not self.stop_processing.is_set():
            try:
                # Check if we have enough audio data
                required_samples = int(self.sample_rate * self.chunk_duration)
                
                if len(self.audio_buffer) >= required_samples:
                    # Check for silence period
                    time_since_audio = time.time() - self.last_audio_time
                    
                    if time_since_audio > self.silence_duration or len(self.audio_buffer) >= required_samples * 1.5:
                        # Process current buffer
                        audio_chunk = np.array(list(self.audio_buffer))
                        self.audio_buffer.clear()
                        
                        # Process chunk
                        self._process_audio_chunk(audio_chunk)
                        
                # Sleep to prevent excessive CPU usage
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Processing error: {e}")
                self._trigger_callback('error', str(e))
                
        logger.info("Processing loop stopped")
        
    def _process_audio_chunk(self, audio_data: np.ndarray):
        """Process a chunk of audio data"""
        try:
            # Save chunk to temporary file
            temp_file = f"temp_chunk_{int(time.time())}.wav"
            
            # Convert to tensor and save
            audio_tensor = torch.from_numpy(audio_data).float().unsqueeze(0)
            torchaudio.save(temp_file, audio_tensor, self.sample_rate)
            
            # Process with speaker attribution system
            segments = self.speaker_system.process_audio(
                temp_file,
                num_speakers=None,
                min_speakers=1,
                max_speakers=5
            )
            
            # Clean up temp file
            os.remove(temp_file)
            
            # Process results
            self._handle_speaker_segments(segments)
            
        except Exception as e:
            logger.error(f"Chunk processing error: {e}")
            
    def _handle_speaker_segments(self, segments: List[SpeakerSegment]):
        """Handle detected speaker segments"""
        current_time = datetime.now()
        
        for segment in segments:
            # Create live event
            event = LiveSpeakerEvent(
                timestamp=current_time,
                speaker_id=segment.speaker_id,
                identified_name=segment.identified_name,
                confidence=segment.confidence,
                duration=segment.end - segment.start,
                audio_level=0.0  # Could be calculated from segment audio
            )
            
            # Update current speakers
            previous_speaker = self.current_speakers.get('active')
            speaker_name = segment.identified_name or segment.speaker_id
            
            self.current_speakers['active'] = speaker_name
            self.current_speakers['confidence'] = segment.confidence
            self.current_speakers['timestamp'] = current_time
            
            # Update statistics
            self.speaker_stats[speaker_name]["total_time"] += segment.end - segment.start
            self.speaker_stats[speaker_name]["segment_count"] += 1
            
            # Add to history
            self.speaker_history.append(event)
            
            # Trigger callbacks
            self._trigger_callback('speaker_detected', event)
            
            if previous_speaker != speaker_name:
                self._trigger_callback('speaker_changed', {
                    'from': previous_speaker,
                    'to': speaker_name,
                    'confidence': segment.confidence
                })
                
    def enroll_speaker_live(self, name: str, duration: float = 5.0):
        """
        Enroll a speaker using live microphone input
        
        Args:
            name: Speaker name
            duration: Recording duration in seconds
        """
        print(f"Enrolling {name}...")
        print(f"Please speak for {duration} seconds...")
        print("Recording in 3... 2... 1...")
        
        # Record audio
        recorded_audio = []
        frames_to_record = int(self.sample_rate * duration)
        frames_recorded = 0
        
        # Temporarily stop main streaming
        was_recording = self.is_recording
        if was_recording:
            self.stop_streaming()
            
        # Open temporary stream for enrollment
        enrollment_stream = self.audio.open(
            format=pyaudio.paFloat32,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=self.chunk_size
        )
        
        print("Recording...")
        start_time = time.time()
        
        while frames_recorded < frames_to_record:
            data = enrollment_stream.read(self.chunk_size)
            audio_chunk = np.frombuffer(data, dtype=np.float32)
            recorded_audio.extend(audio_chunk)
            frames_recorded += len(audio_chunk)
            
            # Show progress
            elapsed = time.time() - start_time
            remaining = duration - elapsed
            if remaining > 0:
                print(f"Recording... {remaining:.1f}s remaining", end='\r')
                
        enrollment_stream.close()
        print(f"\nRecording complete!")
        
        # Save enrollment audio
        enrollment_file = f"enrollment_{name}_{int(time.time())}.wav"
        audio_tensor = torch.from_numpy(np.array(recorded_audio)).float().unsqueeze(0)
        torchaudio.save(enrollment_file, audio_tensor, self.sample_rate)
        
        # Enroll speaker
        self.speaker_system.enroll_speaker(name, [enrollment_file])
        
        # Clean up
        os.remove(enrollment_file)
        
        print(f"Successfully enrolled {name}!")
        
        # Restart streaming if it was running
        if was_recording:
            self.start_streaming()
            
    def get_current_speakers(self) -> Dict:
        """Get current speaker information"""
        return self.current_speakers.copy()
        
    def get_speaker_stats(self) -> Dict:
        """Get speaker statistics"""
        return dict(self.speaker_stats)
        
    def get_recent_history(self, minutes: int = 5) -> List[LiveSpeakerEvent]:
        """Get recent speaker history"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [event for event in self.speaker_history if event.timestamp >= cutoff_time]
        
    def save_session(self, filename: str):
        """Save current session data"""
        session_data = {
            'timestamp': datetime.now().isoformat(),
            'speaker_stats': dict(self.speaker_stats),
            'history': [
                {
                    'timestamp': event.timestamp.isoformat(),
                    'speaker_id': event.speaker_id,
                    'identified_name': event.identified_name,
                    'confidence': event.confidence,
                    'duration': event.duration
                }
                for event in self.speaker_history
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(session_data, f, indent=2)
            
        logger.info(f"Session saved to {filename}")
        
    def __del__(self):
        """Cleanup"""
        self.stop_streaming()
        if hasattr(self, 'audio'):
            self.audio.terminate()


def main():
    """Example usage of live speaker streaming"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Live Speaker Attribution Stream")
    parser.add_argument("--gemini-key", default="AIzaSyAJ_uGXKX_Rg0FO5rdSMPEHdlw-0G76E7g", help="Gemini API key")
    parser.add_argument("--hf-token", help="HuggingFace token")
    parser.add_argument("--device", type=int, help="Audio device index")
    parser.add_argument("--chunk-duration", type=float, default=3.0, help="Processing chunk duration")
    parser.add_argument("--list-devices", action="store_true", help="List audio devices and exit")
    parser.add_argument("--enroll", help="Enroll a speaker with given name")
    
    args = parser.parse_args()
    
    # Initialize live stream
    stream = LiveSpeakerStream(
        gemini_api_key=args.gemini_key,
        hf_token=args.hf_token,
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
        confidence_str = f" ({event.confidence:.2f})" if event.confidence > 0 else ""
        print(f"[{event.timestamp.strftime('%H:%M:%S')}] {speaker}{confidence_str} speaking for {event.duration:.1f}s")
    
    def on_speaker_changed(data):
        print(f"Speaker changed: {data['from']} → {data['to']} (confidence: {data['confidence']:.2f})")
    
    def on_audio_level(level):
        # Simple audio level indicator
        if level > 0.05:  # Only show when there's significant audio
            bars = int(level * 20)
            print(f"Audio: {'█' * bars}{'-' * (20-bars)} {level:.3f}", end='\r')
    
    stream.add_callback('speaker_detected', on_speaker_detected)
    stream.add_callback('speaker_changed', on_speaker_changed)
    stream.add_callback('audio_level', on_audio_level)
    
    # Enroll speaker if requested
    if args.enroll:
        stream.enroll_speaker_live(args.enroll, duration=5.0)
        return
    
    print("Live Speaker Attribution Stream")
    print("=" * 40)
    print("Commands:")
    print("  's' - Show current speaker stats")
    print("  'h' - Show recent history")
    print("  'e <name>' - Enroll new speaker")
    print("  'q' - Quit")
    print("=" * 40)
    
    # Start streaming
    stream.start_streaming()
    
    try:
        while True:
            command = input().strip().lower()
            
            if command == 'q':
                break
            elif command == 's':
                stats = stream.get_speaker_stats()
                print("\nSpeaker Statistics:")
                for speaker, data in stats.items():
                    print(f"  {speaker}: {data['total_time']:.1f}s ({data['segment_count']} segments)")
                    
            elif command == 'h':
                history = stream.get_recent_history(minutes=5)
                print(f"\nRecent History ({len(history)} events):")
                for event in history[-10:]:
                    speaker = event.identified_name or event.speaker_id
                    print(f"  {event.timestamp.strftime('%H:%M:%S')} - {speaker}")
                    
            elif command.startswith('e '):
                name = command[2:].strip()
                if name:
                    stream.enroll_speaker_live(name, duration=5.0)
                    
            elif command:
                print("Unknown command. Use 's', 'h', 'e <name>', or 'q'")
                
    except KeyboardInterrupt:
        pass
    
    # Save session and cleanup
    stream.save_session(f"session_{int(time.time())}.json")
    stream.stop_streaming()
    print("\nSession ended.")


if __name__ == "__main__":
    main()
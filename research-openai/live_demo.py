#!/usr/bin/env python3
"""
Simple Demo Script for Live Speaker Attribution + Transcription
Quick start script to test the live streaming functionality
"""

from live_transcription_stream import LiveTranscriptionStream
from live_speaker_stream import LiveSpeakerStream
import time

def simple_live_demo():
    """Simple demonstration of live speaker attribution"""
    print("🎤 Live Speaker Attribution Demo")
    print("=" * 40)
    
    # Initialize the system
    stream = LiveSpeakerStream(
        gemini_api_key="AIzaSyAJ_uGXKX_Rg0FO5rdSMPEHdlw-0G76E7g",
        chunk_duration=2.0  # Process every 2 seconds
    )
    
    # Set up simple callbacks
    def on_speaker_change(data):
        print(f"🔄 Speaker: {data['to']} (confidence: {data['confidence']:.2f})")
    
    def on_audio_level(level):
        if level > 0.02:  # Only show when speaking
            bars = int(level * 10)
            print(f"🔊 {'█' * bars}{'-' * (10-bars)}", end='\r')
    
    stream.add_callback('speaker_changed', on_speaker_change)
    stream.add_callback('audio_level', on_audio_level)
    
    print("Starting live stream... Speak into your microphone!")
    print("Press Ctrl+C to stop")
    
    # Start streaming
    stream.start_streaming()
    
    try:
        # Let it run
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    
    # Stop and show results
    stream.stop_streaming()
    
    # Show statistics
    stats = stream.get_speaker_stats()
    print(f"\n📊 Session Summary:")
    for speaker, data in stats.items():
        print(f"  {speaker}: {data['total_time']:.1f}s")

def transcription_demo():
    """Demo with transcription"""
    print("🎤📝 Live Speaker Attribution + Transcription Demo")
    print("=" * 50)
    
    # Initialize with transcription
    stream = LiveTranscriptionStream(
        gemini_api_key="AIzaSyAJ_uGXKX_Rg0FO5rdSMPEHdlw-0G76E7g",
        transcription_method="google",  # Use Google Speech Recognition
        chunk_duration=2.0
    )
    
    # Set up callbacks
    def on_transcription(segment):
        speaker = segment.identified_name or segment.speaker_id
        print(f"💬 {speaker}: {segment.text}")
    
    def on_speaker_change(data):
        print(f"🔄 Now speaking: {data['to']}")
    
    stream.add_callback('transcription', on_transcription)
    stream.add_callback('speaker_changed', on_speaker_change)
    
    print("Starting live transcription... Speak clearly into your microphone!")
    print("Press Ctrl+C to stop")
    
    # Start streaming
    stream.start_streaming()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    
    # Stop and export results
    stream.stop_streaming()
    
    # Export transcription
    timestamp = int(time.time())
    stream.export_transcription(f"demo_transcription_{timestamp}.txt", "txt")
    
    print(f"\n✅ Transcription saved to demo_transcription_{timestamp}.txt")

def enrollment_demo():
    """Demo speaker enrollment"""
    print("👥 Speaker Enrollment Demo")
    print("=" * 30)
    
    stream = LiveSpeakerStream(
        gemini_api_key="AIzaSyAJ_uGXKX_Rg0FO5rdSMPEHdlw-0G76E7g"
    )
    
    # Enroll yourself
    name = input("Enter your name for enrollment: ").strip()
    if name:
        stream.enroll_speaker_live(name, duration=5.0)
        
        # Now test identification
        print("\nNow speak again to test identification...")
        
        def on_speaker_detected(event):
            if event.identified_name:
                print(f"✅ Identified: {event.identified_name} (confidence: {event.confidence:.2f})")
            else:
                print(f"❓ Unknown speaker: {event.speaker_id}")
        
        stream.add_callback('speaker_detected', on_speaker_detected)
        
        stream.start_streaming()
        
        try:
            time.sleep(15)  # Run for 15 seconds
        except KeyboardInterrupt:
            pass
        
        stream.stop_streaming()

def main():
    """Main demo menu"""
    print("🎤 Live Speaker Attribution System - Demo Menu")
    print("=" * 50)
    print("Choose a demo:")
    print("1. Simple Speaker Detection")
    print("2. Speaker Detection + Transcription")
    print("3. Speaker Enrollment")
    print("4. List Audio Devices")
    print("0. Exit")
    
    while True:
        choice = input("\nSelect option (0-4): ").strip()
        
        if choice == "0":
            break
        elif choice == "1":
            simple_live_demo()
        elif choice == "2":
            transcription_demo()
        elif choice == "3":
            enrollment_demo()
        elif choice == "4":
            stream = LiveSpeakerStream(gemini_api_key="dummy")
            stream.list_audio_devices()
        else:
            print("Invalid choice. Please select 0-4.")

if __name__ == "__main__":
    main()
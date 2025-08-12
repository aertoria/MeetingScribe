#!/usr/bin/env python3
"""
Simple example of using the Speaker Attribution System
"""

from speaker_attribution import SpeakerAttributionSystem
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

def simple_example():
    """Basic usage example"""
    
    # Initialize the system with your Gemini API key
    system = SpeakerAttributionSystem(
        gemini_api_key="AIzaSyAJ_uGXKX_Rg0FO5rdSMPEHdlw-0G76E7g",
        hf_token=None  # Optional: Add your HuggingFace token for better diarization
    )
    
    # Example 1: Process a meeting recording
    print("Processing meeting audio...")
    segments = system.process_audio(
        "meeting_recording.wav",
        num_speakers=None,  # Let the system detect number of speakers
        min_speakers=2,
        max_speakers=5
    )
    
    # Print results
    print(f"\nFound {len(segments)} speech segments")
    for seg in segments[:10]:  # Show first 10 segments
        speaker = seg.identified_name or seg.speaker_id
        print(f"[{seg.start:.1f}s - {seg.end:.1f}s] {speaker}")
        if seg.confidence > 0:
            print(f"  Confidence: {seg.confidence:.2f}")
    
    # Export results
    system.export_results(segments, "meeting_results.json", format="json")
    system.export_results(segments, "meeting_timeline.txt", format="txt")
    print("\nResults saved to meeting_results.json and meeting_timeline.txt")


def enrollment_example():
    """Example of enrolling known speakers"""
    
    system = SpeakerAttributionSystem(
        gemini_api_key="AIzaSyAJ_uGXKX_Rg0FO5rdSMPEHdlw-0G76E7g"
    )
    
    # Enroll speakers with voice samples
    print("Enrolling speakers...")
    
    # Enroll Alice
    system.enroll_speaker("Alice", [
        "samples/alice_sample1.wav",
        "samples/alice_sample2.wav"
    ])
    
    # Enroll Bob
    system.enroll_speaker("Bob", [
        "samples/bob_sample1.wav",
        "samples/bob_sample2.wav"
    ])
    
    print("Speakers enrolled successfully!")
    
    # Now process a meeting with these enrolled speakers
    segments = system.process_audio("meeting_with_alice_and_bob.wav")
    
    # Check identification results
    identified_count = sum(1 for s in segments if s.identified_name)
    print(f"\nIdentified {identified_count}/{len(segments)} segments")


def streaming_example():
    """Example of real-time streaming processing"""
    
    import pyaudio
    import numpy as np
    
    system = SpeakerAttributionSystem(
        gemini_api_key="AIzaSyAJ_uGXKX_Rg0FO5rdSMPEHdlw-0G76E7g"
    )
    
    # Set up audio stream
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    
    p = pyaudio.PyAudio()
    
    def audio_stream_generator():
        """Generate audio chunks from microphone"""
        stream = p.open(format=FORMAT,
                       channels=CHANNELS,
                       rate=RATE,
                       input=True,
                       frames_per_buffer=CHUNK)
        
        print("Listening... Press Ctrl+C to stop")
        try:
            while True:
                data = stream.read(CHUNK)
                audio_chunk = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                yield audio_chunk
        except KeyboardInterrupt:
            stream.stop_stream()
            stream.close()
            p.terminate()
    
    # Process streaming audio
    for segments, current_speakers in system.process_streaming_audio(
        audio_stream_generator(),
        chunk_duration=3.0  # Process every 3 seconds
    ):
        print(f"\nCurrent speakers: {current_speakers}")
        for seg in segments:
            speaker = seg.identified_name or seg.speaker_id
            print(f"  [{seg.start:.1f}s - {seg.end:.1f}s] {speaker}")


def batch_processing_example():
    """Process multiple audio files"""
    
    system = SpeakerAttributionSystem(
        gemini_api_key="AIzaSyAJ_uGXKX_Rg0FO5rdSMPEHdlw-0G76E7g"
    )
    
    audio_files = [
        "meeting1.wav",
        "meeting2.wav",
        "meeting3.wav"
    ]
    
    all_results = {}
    
    for audio_file in audio_files:
        print(f"\nProcessing {audio_file}...")
        segments = system.process_audio(audio_file)
        all_results[audio_file] = segments
        
        # Export individual results
        output_name = audio_file.replace(".wav", "_results.json")
        system.export_results(segments, output_name, format="json")
        
    print(f"\nProcessed {len(audio_files)} files")
    for file, segments in all_results.items():
        speakers = set(s.speaker_id for s in segments)
        print(f"  {file}: {len(segments)} segments, {len(speakers)} speakers")


if __name__ == "__main__":
    print("Speaker Attribution System Examples")
    print("=" * 40)
    
    # Run simple example
    print("\n1. Simple Processing Example")
    print("-" * 30)
    # Uncomment to run:
    # simple_example()
    
    # Run enrollment example
    print("\n2. Speaker Enrollment Example")
    print("-" * 30)
    # Uncomment to run:
    # enrollment_example()
    
    # Run streaming example
    print("\n3. Real-time Streaming Example")
    print("-" * 30)
    # Uncomment to run:
    # streaming_example()
    
    # Run batch processing example
    print("\n4. Batch Processing Example")
    print("-" * 30)
    # Uncomment to run:
    # batch_processing_example()
    
    print("\nTo run examples, uncomment the desired function calls in the main block.")
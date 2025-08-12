#!/usr/bin/env python3
"""
Quick start script for Speaker Attribution System
"""

from speaker_attribution import SpeakerAttributionSystem

# Initialize system (Gemini API key is already included)
system = SpeakerAttributionSystem(
    gemini_api_key="AIzaSyAJ_uGXKX_Rg0FO5rdSMPEHdlw-0G76E7g",
    hf_token=None  # Add your HuggingFace token here if you have one
)

# Process your audio file
audio_file = "your_meeting.wav"  # Replace with your audio file path

print(f"Processing {audio_file}...")
segments = system.process_audio(audio_file)

# Display results
print(f"\nFound {len(segments)} speech segments:")
for i, segment in enumerate(segments[:20]):  # Show first 20
    speaker = segment.identified_name or segment.speaker_id
    print(f"{i+1}. [{segment.start:.1f}s - {segment.end:.1f}s] {speaker}")

# Save results
system.export_results(segments, "speaker_results.json", format="json")
system.export_results(segments, "speaker_timeline.txt", format="txt")

print("\nResults saved to:")
print("  - speaker_results.json (detailed data)")
print("  - speaker_timeline.txt (readable timeline)")
#!/usr/bin/env python3
"""
Fixed Live Demo with Working Speaker Diarization

This script demonstrates a clear, modular, and maintainable approach to
streaming microphone audio to Deepgram's realtime API with speaker
diarization enabled. It has been refactored for readability and includes
extensive inline comments and docstrings for every important step.

Security note:
- By default, the Deepgram API key is read from the environment variable
  "DEEPGRAM_API_KEY". For convenience in local development, this demo also
  includes a hardcoded fallback constant that can be overridden by the
  environment variable or constructor parameter. Avoid committing real
  production secrets to source control.
"""

from __future__ import annotations

import os
import json
import time
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List, Optional

import pyaudio
from deepgram import (
    DeepgramClient,
    LiveOptions,
    LiveTranscriptionEvents,
)


# Local-development fallback API key provided by the user.
# Precedence order for API key resolution is:
# 1) api_key argument passed to FixedDiarizationDemo(...)
# 2) DEEPGRAM_API_KEY environment variable
# 3) HARD_CODED_DEEPGRAM_API_KEY (below)
#
# IMPORTANT: Never use hardcoded keys in production. Rotate this key if
# it is ever exposed beyond your local environment.
HARD_CODED_DEEPGRAM_API_KEY: str = "50ea35eadaddeda4d3779c93b2f2cf27bcd7e14c"


@dataclass
class TranscriptEntry:
    """A single utterance captured from the live transcription stream.

    - time: Display-friendly timestamp (HH:MM:SS) when the utterance arrived
    - speaker: Human-readable speaker label (e.g., "Speaker 1")
    - speaker_id: Numeric speaker identifier from diarization
    - text: The transcribed sentence/utterance
    """

    time: str
    speaker: str
    speaker_id: int
    text: str


class FixedDiarizationDemo:
    """A readable, modular wrapper around Deepgram realtime diarization.

    Responsibilities:
    - Opening a realtime connection
    - Handling transcript/diarization events
    - Streaming audio from the microphone
    - Displaying live results and writing a summary at the end
    """

    # Audio configuration constants chosen to match Deepgram realtime defaults
    DEFAULT_SAMPLE_RATE: int = 16000
    DEFAULT_CHANNELS: int = 1
    DEFAULT_CHUNK_SIZE: int = 1024

    # ANSI color codes for differentiating speakers in the console
    ANSI_COLORS: List[str] = [
        "\033[94m",  # Blue
        "\033[92m",  # Green
        "\033[93m",  # Yellow
        "\033[95m",  # Magenta
        "\033[96m",  # Cyan
        "\033[91m",  # Red
    ]
    ANSI_RESET: str = "\033[0m"

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialize the demo with a Deepgram client and state containers.

        - api_key: Optionally provide the Deepgram API key directly.
                   If omitted, the value is read from DEEPGRAM_API_KEY.
        """

        # Resolve API key with precedence: explicit argument → environment → fallback constant
        resolved_api_key = api_key or os.getenv("DEEPGRAM_API_KEY") or HARD_CODED_DEEPGRAM_API_KEY
        if not resolved_api_key:
            # Fail fast with a clear, actionable message if no API key is set
            raise ValueError(
                "Deepgram API key not found. Set the 'DEEPGRAM_API_KEY' environment "
                "variable or pass api_key=... when constructing FixedDiarizationDemo."
            )

        # Construct the Deepgram client using the resolved API key
        self.deepgram: DeepgramClient = DeepgramClient(resolved_api_key)

        # Map of speaker_id → human-friendly label (e.g., 0 → "Speaker 1")
        self.speakers: Dict[int, str] = {}

        # In-memory transcript of the session, recorded in arrival order
        self.transcript: List[TranscriptEntry] = []

        # Flag to control the lifetime of the audio streaming thread and loop
        self.is_recording: bool = False

        # Tracks whether diarization was actually active/working during session
        self.diarization_enabled: bool = False

        # Handle to the background audio thread so we can join on shutdown
        self._audio_thread: Optional[threading.Thread] = None

    # -------------------------- Public API -------------------------- #

    def run(self) -> None:
        """Run the end-to-end live transcription and diarization demo.

        This method orchestrates the user-facing flow:
        - Print a readable header
        - Create the realtime connection and register event handlers
        - Start the connection with diarization options
        - Start the background audio streaming thread
        - Keep the main thread alive until interrupted
        - Cleanup and print a session summary at the end
        """

        # Print a simple header so users know what's happening
        self._print_header()

        try:
            # Create the Deepgram realtime websocket connection
            connection = self._create_connection()

            # Register event handlers for connection lifecycle and transcripts
            self._register_event_handlers(connection)

            # Start the connection with our chosen options (with diarization)
            if not self._start_connection(connection):
                # If the connection didn't start, abort gracefully
                return

            # Begin streaming microphone audio in the background
            self._start_audio_stream(connection)

            # Inform the user that we're ready to capture speech
            print("\nREADY! Start speaking now...")
            print("Have different people speak to test speaker detection")
            print("-" * 60)

            # Keep the main thread alive while streaming occurs in the background
            try:
                while self.is_recording:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                # User requested shutdown; stop the streaming loop
                print("\n\nStopping live transcript...")
                self.is_recording = False

            # Ensure a clean shutdown: stop audio thread and close connection
            self._cleanup(connection)

            # Present a readable summary and write the transcript to disk
            self.show_summary()

        except Exception as exc:
            # Catch all unexpected errors and present a helpful traceback
            print(f"\nError: {exc}")
            import traceback
            traceback.print_exc()

    def show_summary(self) -> None:
        """Print a human-friendly session summary and save transcript to JSON."""

        # Section heading for readability
        print("\n" + "=" * 60)
        print("SESSION SUMMARY")
        print("=" * 60)

        # Indicate whether diarization activated during the session
        print(f"Diarization Status: {'ENABLED' if self.diarization_enabled else 'DISABLED'}")

        # If we have any transcript entries, show stats and persist to file
        if self.transcript:
            # High-level totals for quick context
            print(f"Captured {len(self.transcript)} utterances")
            print(f"Detected {len(self.speakers)} unique speaker(s):")

            # Build a count of utterances per speaker
            speaker_stats = self._collect_speaker_stats()

            # Present per-speaker counts and word totals
            for speaker, count in speaker_stats.items():
                words = sum(
                    len(entry.text.split()) for entry in self.transcript if entry.speaker == speaker
                )
                print(f"   • {speaker}: {count} utterances, {words} words")

            # Persist the full transcript to a timestamped JSON file
            filename = self._save_transcript(speaker_stats)
            print(f"\nFull transcript saved to: {filename}")

            # Give a quick, friendly verdict on diarization success
            if len(self.speakers) > 1:
                print("\nSUCCESS: Multiple speakers were detected!")
            elif self.diarization_enabled:
                print("\nOnly one speaker detected - try having different people speak")
            else:
                print("\nDiarization didn't activate - speaker detection unavailable")

        else:
            # No transcript suggests either silence or input configuration issues
            print("No speech was detected")
            print("   Make sure your microphone is working and speak clearly")

    # ----------------------- Connection Lifecycle ----------------------- #

    def _print_header(self) -> None:
        """Print a consistent header for the demo session."""
        print("\nLIVE TRANSCRIPT WITH SPEAKER DIARIZATION")
        print("=" * 60)
        print("Starting live speech-to-text with speaker detection")
        print("Speak into your microphone now!")
        print("Press Ctrl+C to stop")
        print("=" * 60)

    def _create_connection(self):  # type: ignore[no-untyped-def]
        """Create the Deepgram websocket connection object.

        Returns the connection instance so callers can register event handlers
        and start the session.
        """
        return self.deepgram.listen.websocket.v("1")

    def _register_event_handlers(self, connection) -> None:  # type: ignore[no-untyped-def]
        """Attach event handlers for connection lifecycle and transcripts."""
        connection.on(LiveTranscriptionEvents.Open, self._on_open)
        connection.on(LiveTranscriptionEvents.Transcript, self._on_transcript)
        connection.on(LiveTranscriptionEvents.Error, self._on_error)

    def _build_live_options(self) -> LiveOptions:
        """Return the tested configuration that enables speaker diarization."""
        return LiveOptions(
            model="nova-2",
            language="en",
            punctuate=True,
            smart_format=True,
            diarize=True,  # Enable speaker diarization
            encoding="linear16",
            sample_rate=self.DEFAULT_SAMPLE_RATE,
            channels=self.DEFAULT_CHANNELS,
        )

    def _start_connection(self, connection) -> bool:  # type: ignore[no-untyped-def]
        """Start the Deepgram realtime connection with our live options.

        Returns True on success; otherwise prints an error and returns False.
        """
        print("Connecting with diarization (using tested configuration)...")
        options = self._build_live_options()
        if connection.start(options):
            print("Diarization connection successful!")
            self.diarization_enabled = True
            return True

        print("Diarization connection failed, this shouldn't happen based on our tests")
        return False

    # -------------------------- Event Handlers -------------------------- #

    def _on_open(self, websocket_self, open, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """Handle the connection open event by printing a friendly banner."""
        diarization_status = "WITH" if self.diarization_enabled else "WITHOUT"
        print(f"Connected to Deepgram {diarization_status} speaker diarization!")
        print("\nLIVE TRANSCRIPT:")
        print("-" * 60)

    def _on_transcript(self, websocket_self, result, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """Handle incoming transcript messages and display/store them."""
        try:
            self._handle_transcript_result(result)
        except Exception as exc:  # Keep the stream resilient to parsing issues
            print(f"Error processing transcript: {exc}")

    def _on_error(self, websocket_self, error, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """Handle errors emitted by the Deepgram connection."""
        print(f"Deepgram Error: {error}")

    # ----------------------- Transcript Processing ---------------------- #

    def _handle_transcript_result(self, result) -> None:  # type: ignore[no-untyped-def]
        """Extract sentence and speaker data from a Deepgram result object.

        This function keeps the parsing logic in one place and handles both
        the display of live text and recording of entries for the summary.
        """

        # Grab the top alternative text (Deepgram returns a ranked list)
        sentence: str = result.channel.alternatives[0].transcript

        # Ignore empty/whitespace-only results to reduce noise
        if not sentence or not sentence.strip():
            return

        # Default to a single speaker (ID 0) when diarization hasn't labeled it
        speaker_id: int = 0

        # Access the word-level results to see if Deepgram labeled a speaker
        words = result.channel.alternatives[0].words
        if words and len(words) > 0:
            first_word = words[0]
            # Some SDK versions expose .speaker on word objects when diarization is on
            if hasattr(first_word, "speaker") and first_word.speaker is not None:
                speaker_id = int(first_word.speaker)
                # The first time we observe a speaker label, mark diarization as active
                if not self.diarization_enabled:
                    print(
                        f"Speaker diarization confirmed working! Detected speaker {speaker_id}"
                    )
                    self.diarization_enabled = True

        # Ensure a stable, human-friendly label exists for this speaker_id
        if speaker_id not in self.speakers:
            speaker_number = len(self.speakers) + 1
            self.speakers[speaker_id] = f"Speaker {speaker_number}"
            if len(self.speakers) > 1:
                print(
                    f"NEW SPEAKER DETECTED: {self.speakers[speaker_id]} (ID: {speaker_id})"
                )

        # Resolve current speaker label and prepare a timestamp for display
        speaker_name = self.speakers[speaker_id]
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Colorize the speaker label for easy visual separation in the console
        color = self._color_for_speaker(speaker_id)

        # Show the live utterance with consistent, readable formatting
        print(f"[{timestamp}] {color}{speaker_name}{self.ANSI_RESET}: {sentence}")

        # Record the utterance to the in-memory transcript for the summary
        self.transcript.append(
            TranscriptEntry(time=timestamp, speaker=speaker_name, speaker_id=speaker_id, text=sentence)
        )

    def _color_for_speaker(self, speaker_id: int) -> str:
        """Return a stable ANSI color code for a given speaker ID."""
        return self.ANSI_COLORS[speaker_id % len(self.ANSI_COLORS)]

    # --------------------------- Audio Streaming ------------------------- #

    def _start_audio_stream(self, connection) -> None:  # type: ignore[no-untyped-def]
        """Start the background thread that streams microphone audio."""
        self.is_recording = True
        self._audio_thread = threading.Thread(
            target=self._audio_stream_loop, args=(connection,), daemon=True
        )
        self._audio_thread.start()

    def _audio_stream_loop(self, connection) -> None:  # type: ignore[no-untyped-def]
        """Continuously read audio from the default microphone and send it.

        Uses PyAudio to open the system default input device with the same
        sample rate/channels as the Deepgram connection and streams small
        chunks to the websocket for low-latency transcription.
        """

        # Create a PyAudio instance to manage the input stream lifecycle
        p = pyaudio.PyAudio()

        # Open the input stream with settings that match our Deepgram options
        stream = p.open(
            format=pyaudio.paInt16,
            channels=self.DEFAULT_CHANNELS,
            rate=self.DEFAULT_SAMPLE_RATE,
            input=True,
            frames_per_buffer=self.DEFAULT_CHUNK_SIZE,
        )

        print("Audio streaming started...")

        try:
            # Keep reading small chunks while the main thread wants to record
            while self.is_recording:
                data = stream.read(self.DEFAULT_CHUNK_SIZE, exception_on_overflow=False)
                connection.send(data)
                # A tiny sleep to avoid a busy loop; tune if needed
                time.sleep(0.01)
        except Exception as exc:
            # Keep the application resilient to transient audio/IO errors
            print(f"Audio streaming error: {exc}")
        finally:
            # Always release audio resources to avoid device locking
            stream.stop_stream()
            stream.close()
            p.terminate()

    # ------------------------------ Cleanup ------------------------------ #

    def _cleanup(self, connection) -> None:  # type: ignore[no-untyped-def]
        """Gracefully stop background work and close the connection."""
        # Signal the audio loop to exit and wait briefly for the thread to end
        self.is_recording = False
        if self._audio_thread is not None:
            self._audio_thread.join(timeout=2)

        # Tell the Deepgram connection we're done sending audio
        connection.finish()

    # ------------------------- Summary/Serialization --------------------- #

    def _collect_speaker_stats(self) -> Dict[str, int]:
        """Return a mapping of speaker label to utterance count."""
        counts: Dict[str, int] = {}
        for entry in self.transcript:
            counts[entry.speaker] = counts.get(entry.speaker, 0) + 1
        return counts

    def _save_transcript(self, speaker_stats: Dict[str, int]) -> str:
        """Write the full session transcript and metadata to a JSON file.

        Returns the filename used for saving so callers can display it.
        """
        filename = f"diarized_transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w") as f:
            json.dump(
                {
                    "session_date": datetime.now().isoformat(),
                    "diarization_enabled": self.diarization_enabled,
                    "speakers_detected": len(self.speakers),
                    "speakers": list(self.speakers.values()),
                    "speaker_stats": speaker_stats,
                    "transcript": [asdict(e) for e in self.transcript],
                },
                f,
                indent=2,
            )
        return filename


if __name__ == "__main__":
    # Provide a clear entrypoint banner for the demo
    print("\nFIXED LIVE DIARIZATION DEMO")
    print("This uses the exact configuration that passed our connection tests")

    try:
        # Construct the demo; API key is read from DEEPGRAM_API_KEY by default
        demo = FixedDiarizationDemo()
        demo.run()
    except KeyboardInterrupt:
        # Gracefully handle Ctrl+C even during startup
        print("\nGoodbye!")
    except Exception as exc:
        # Surface any unexpected setup/run errors to the user
        print(f"Error: {exc}")

    print("\nDemo complete!")
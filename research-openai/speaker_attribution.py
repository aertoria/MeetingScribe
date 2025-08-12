#!/usr/bin/env python3
"""
Speaker Attribution System for Meeting Transcription
Combines pyannote.audio diarization with speaker identification using embeddings
and Gemini API for enhanced recognition
"""

import os
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import torch
import torchaudio
from dataclasses import dataclass
from datetime import datetime
import logging
import google.generativeai as genai
from scipy.spatial.distance import cosine
import pickle

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class SpeakerSegment:
    """Represents a speaker segment in audio"""
    start: float
    end: float
    speaker_id: str
    confidence: float = 0.0
    identified_name: Optional[str] = None
    embedding: Optional[np.ndarray] = None

@dataclass
class SpeakerProfile:
    """Stored speaker profile for identification"""
    name: str
    embedding: np.ndarray
    created_at: datetime
    sample_count: int = 1

class SpeakerAttributionSystem:
    """Main system for speaker diarization and identification"""
    
    def __init__(self, gemini_api_key: str, hf_token: Optional[str] = None):
        """
        Initialize the speaker attribution system
        
        Args:
            gemini_api_key: API key for Gemini
            hf_token: HuggingFace token for pyannote.audio models
        """
        self.gemini_api_key = gemini_api_key
        self.hf_token = hf_token or os.getenv("HF_TOKEN")
        
        # Initialize components
        self._init_gemini()
        self._init_diarization()
        self._init_embedding_model()
        
        # Speaker database
        self.speaker_profiles: Dict[str, SpeakerProfile] = {}
        self.profiles_path = Path("speaker_profiles.pkl")
        self.load_speaker_profiles()
        
    def _init_gemini(self):
        """Initialize Gemini API"""
        genai.configure(api_key=self.gemini_api_key)
        self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        logger.info("Gemini API initialized")
        
    def _init_diarization(self):
        """Initialize pyannote.audio diarization pipeline"""
        try:
            from pyannote.audio import Pipeline
            
            if not self.hf_token:
                logger.warning("No HuggingFace token provided. Using fallback diarization.")
                self.diarization_pipeline = None
                return
                
            # Load pretrained pipeline
            self.diarization_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token
            )
            
            # Move to GPU if available
            if torch.cuda.is_available():
                self.diarization_pipeline.to(torch.device("cuda"))
                
            logger.info("Pyannote diarization pipeline loaded")
            
        except ImportError:
            logger.warning("pyannote.audio not installed. Install with: pip install pyannote.audio")
            self.diarization_pipeline = None
        except Exception as e:
            logger.error(f"Failed to load diarization pipeline: {e}")
            self.diarization_pipeline = None
            
    def _init_embedding_model(self):
        """Initialize speaker embedding model"""
        try:
            from speechbrain.inference.speaker import EncoderClassifier
            
            # Load pretrained ECAPA-TDNN model
            self.embedding_model = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir="pretrained_models/spkrec-ecapa-voxceleb"
            )
            logger.info("Speaker embedding model loaded")
            
        except ImportError:
            logger.warning("SpeechBrain not installed. Install with: pip install speechbrain")
            self.embedding_model = None
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self.embedding_model = None
            
    def process_audio(self, audio_path: str, 
                     num_speakers: Optional[int] = None,
                     min_speakers: int = 1,
                     max_speakers: int = 10) -> List[SpeakerSegment]:
        """
        Process audio file for speaker diarization and identification
        
        Args:
            audio_path: Path to audio file
            num_speakers: Known number of speakers (if available)
            min_speakers: Minimum number of speakers
            max_speakers: Maximum number of speakers
            
        Returns:
            List of speaker segments with identification
        """
        logger.info(f"Processing audio: {audio_path}")
        
        # Step 1: Diarization
        segments = self.diarize_audio(audio_path, num_speakers, min_speakers, max_speakers)
        
        # Step 2: Extract embeddings for each segment
        segments = self.extract_embeddings(audio_path, segments)
        
        # Step 3: Identify speakers
        segments = self.identify_speakers(segments)
        
        # Step 4: Enhance with Gemini (optional)
        segments = self.enhance_with_gemini(audio_path, segments)
        
        return segments
        
    def diarize_audio(self, audio_path: str,
                     num_speakers: Optional[int] = None,
                     min_speakers: int = 1, 
                     max_speakers: int = 10) -> List[SpeakerSegment]:
        """
        Perform speaker diarization on audio
        
        Returns:
            List of speaker segments
        """
        if self.diarization_pipeline is None:
            return self._fallback_diarization(audio_path)
            
        try:
            # Run diarization
            diarization = self.diarization_pipeline(
                audio_path,
                num_speakers=num_speakers,
                min_speakers=min_speakers,
                max_speakers=max_speakers
            )
            
            # Convert to segments
            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append(SpeakerSegment(
                    start=turn.start,
                    end=turn.end,
                    speaker_id=speaker
                ))
                
            logger.info(f"Diarization complete: {len(segments)} segments found")
            return segments
            
        except Exception as e:
            logger.error(f"Diarization failed: {e}")
            return self._fallback_diarization(audio_path)
            
    def _fallback_diarization(self, audio_path: str) -> List[SpeakerSegment]:
        """Simple fallback diarization using energy-based segmentation"""
        logger.info("Using fallback diarization method")
        
        # Load audio
        waveform, sample_rate = torchaudio.load(audio_path)
        
        # Convert to mono if stereo
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
            
        # Simple energy-based voice activity detection
        frame_length = int(sample_rate * 0.025)  # 25ms frames
        hop_length = int(sample_rate * 0.010)    # 10ms hop
        
        energy = []
        for i in range(0, waveform.shape[1] - frame_length, hop_length):
            frame = waveform[:, i:i+frame_length]
            energy.append(torch.mean(frame ** 2).item())
            
        energy = np.array(energy)
        threshold = np.mean(energy) * 0.5
        
        # Create segments (simplified - assumes single speaker)
        segments = []
        in_speech = False
        start_time = 0
        
        for i, e in enumerate(energy):
            time = i * hop_length / sample_rate
            
            if e > threshold and not in_speech:
                start_time = time
                in_speech = True
            elif e <= threshold and in_speech:
                if time - start_time > 0.5:  # Min segment length
                    segments.append(SpeakerSegment(
                        start=start_time,
                        end=time,
                        speaker_id="Speaker_0"
                    ))
                in_speech = False
                
        return segments
        
    def extract_embeddings(self, audio_path: str, segments: List[SpeakerSegment]) -> List[SpeakerSegment]:
        """
        Extract speaker embeddings for each segment
        """
        if self.embedding_model is None:
            logger.warning("Embedding model not available")
            return segments
            
        # Load full audio
        waveform, sample_rate = torchaudio.load(audio_path)
        
        # Convert to mono if needed
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
            
        # Resample to 16kHz if needed
        if sample_rate != 16000:
            resampler = torchaudio.transforms.Resample(sample_rate, 16000)
            waveform = resampler(waveform)
            sample_rate = 16000
            
        for segment in segments:
            try:
                # Extract segment audio
                start_sample = int(segment.start * sample_rate)
                end_sample = int(segment.end * sample_rate)
                segment_audio = waveform[:, start_sample:end_sample]
                
                # Skip if segment too short
                if segment_audio.shape[1] < sample_rate * 0.5:  # Min 0.5 seconds
                    continue
                    
                # Extract embedding
                embedding = self.embedding_model.encode_batch(segment_audio)
                segment.embedding = embedding.squeeze().cpu().numpy()
                
            except Exception as e:
                logger.warning(f"Failed to extract embedding for segment: {e}")
                
        return segments
        
    def identify_speakers(self, segments: List[SpeakerSegment]) -> List[SpeakerSegment]:
        """
        Identify speakers by matching embeddings to known profiles
        """
        if not self.speaker_profiles:
            logger.info("No speaker profiles loaded")
            return segments
            
        for segment in segments:
            if segment.embedding is None:
                continue
                
            best_match = None
            best_similarity = -1
            
            # Compare with known speakers
            for name, profile in self.speaker_profiles.items():
                similarity = 1 - cosine(segment.embedding, profile.embedding)
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = name
                    
            # Apply threshold
            if best_similarity > 0.7:  # Configurable threshold
                segment.identified_name = best_match
                segment.confidence = best_similarity
                logger.info(f"Identified {best_match} with confidence {best_similarity:.2f}")
                
        return segments
        
    def enhance_with_gemini(self, audio_path: str, segments: List[SpeakerSegment]) -> List[SpeakerSegment]:
        """
        Use Gemini API to enhance speaker identification
        """
        try:
            # Prepare context for Gemini
            context = self._prepare_gemini_context(segments)
            
            # Create prompt
            prompt = f"""
            Analyze the following speaker segments from a meeting audio:
            
            {context}
            
            Based on the speaking patterns, segment durations, and transitions:
            1. Are there any obvious speaker groupings that should be merged?
            2. Can you identify any speaking patterns that suggest specific roles (e.g., moderator, presenter)?
            3. Suggest any corrections to the speaker assignments.
            
            Return your analysis in JSON format with:
            - merge_suggestions: list of segment IDs that likely belong to the same speaker
            - role_assignments: suggested roles for each speaker
            - confidence_adjustments: any segments where confidence should be adjusted
            """
            
            response = self.gemini_model.generate_content(prompt)
            
            # Parse and apply Gemini suggestions
            suggestions = self._parse_gemini_response(response.text)
            segments = self._apply_gemini_suggestions(segments, suggestions)
            
        except Exception as e:
            logger.error(f"Gemini enhancement failed: {e}")
            
        return segments
        
    def _prepare_gemini_context(self, segments: List[SpeakerSegment]) -> str:
        """Prepare context string for Gemini analysis"""
        context_lines = []
        for i, seg in enumerate(segments[:50]):  # Limit to first 50 segments
            line = f"Segment {i}: {seg.start:.1f}s-{seg.end:.1f}s, Speaker: {seg.speaker_id}"
            if seg.identified_name:
                line += f" (Identified: {seg.identified_name}, Confidence: {seg.confidence:.2f})"
            context_lines.append(line)
        return "\n".join(context_lines)
        
    def _parse_gemini_response(self, response_text: str) -> Dict:
        """Parse Gemini response"""
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        return {}
        
    def _apply_gemini_suggestions(self, segments: List[SpeakerSegment], suggestions: Dict) -> List[SpeakerSegment]:
        """Apply Gemini suggestions to segments"""
        # This is a placeholder - implement based on actual Gemini response format
        return segments
        
    def enroll_speaker(self, name: str, audio_samples: List[str]):
        """
        Enroll a new speaker with voice samples
        
        Args:
            name: Speaker name
            audio_samples: List of audio file paths for enrollment
        """
        if self.embedding_model is None:
            logger.error("Cannot enroll speaker: embedding model not available")
            return
            
        embeddings = []
        
        for audio_path in audio_samples:
            try:
                # Load audio
                waveform, sample_rate = torchaudio.load(audio_path)
                
                # Preprocess
                if waveform.shape[0] > 1:
                    waveform = torch.mean(waveform, dim=0, keepdim=True)
                    
                if sample_rate != 16000:
                    resampler = torchaudio.transforms.Resample(sample_rate, 16000)
                    waveform = resampler(waveform)
                    
                # Extract embedding
                embedding = self.embedding_model.encode_batch(waveform)
                embeddings.append(embedding.squeeze().cpu().numpy())
                
            except Exception as e:
                logger.error(f"Failed to process enrollment sample: {e}")
                
        if embeddings:
            # Average embeddings
            avg_embedding = np.mean(embeddings, axis=0)
            
            # Create profile
            self.speaker_profiles[name] = SpeakerProfile(
                name=name,
                embedding=avg_embedding,
                created_at=datetime.now(),
                sample_count=len(embeddings)
            )
            
            self.save_speaker_profiles()
            logger.info(f"Enrolled speaker: {name} with {len(embeddings)} samples")
            
    def save_speaker_profiles(self):
        """Save speaker profiles to disk"""
        try:
            with open(self.profiles_path, 'wb') as f:
                pickle.dump(self.speaker_profiles, f)
            logger.info(f"Saved {len(self.speaker_profiles)} speaker profiles")
        except Exception as e:
            logger.error(f"Failed to save profiles: {e}")
            
    def load_speaker_profiles(self):
        """Load speaker profiles from disk"""
        if self.profiles_path.exists():
            try:
                with open(self.profiles_path, 'rb') as f:
                    self.speaker_profiles = pickle.load(f)
                logger.info(f"Loaded {len(self.speaker_profiles)} speaker profiles")
            except Exception as e:
                logger.error(f"Failed to load profiles: {e}")
                
    def process_streaming_audio(self, audio_stream, chunk_duration: float = 3.0):
        """
        Process audio stream in real-time
        
        Args:
            audio_stream: Audio stream generator
            chunk_duration: Duration of each chunk in seconds
        """
        buffer = []
        current_speakers = {}
        
        for chunk in audio_stream:
            buffer.append(chunk)
            
            # Process when buffer reaches chunk_duration
            if len(buffer) * chunk.duration >= chunk_duration:
                # Combine buffer
                combined_audio = np.concatenate(buffer)
                
                # Process chunk
                segments = self.process_audio_chunk(combined_audio)
                
                # Update current speakers
                for seg in segments:
                    if seg.identified_name:
                        current_speakers[seg.speaker_id] = seg.identified_name
                        
                # Yield results
                yield segments, current_speakers
                
                # Clear buffer
                buffer = []
                
    def export_results(self, segments: List[SpeakerSegment], output_path: str, format: str = "json"):
        """
        Export results in various formats
        
        Args:
            segments: List of speaker segments
            output_path: Output file path
            format: Output format (json, csv, txt, rttm)
        """
        if format == "json":
            data = []
            for seg in segments:
                data.append({
                    "start": seg.start,
                    "end": seg.end,
                    "speaker_id": seg.speaker_id,
                    "identified_name": seg.identified_name,
                    "confidence": seg.confidence
                })
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2)
                
        elif format == "csv":
            import csv
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Start", "End", "Speaker ID", "Identified Name", "Confidence"])
                for seg in segments:
                    writer.writerow([seg.start, seg.end, seg.speaker_id, seg.identified_name or "", seg.confidence])
                    
        elif format == "txt":
            with open(output_path, 'w') as f:
                for seg in segments:
                    name = seg.identified_name or seg.speaker_id
                    f.write(f"[{seg.start:.2f} - {seg.end:.2f}] {name}\n")
                    
        elif format == "rttm":
            # RTTM format for evaluation
            with open(output_path, 'w') as f:
                for seg in segments:
                    duration = seg.end - seg.start
                    f.write(f"SPEAKER meeting 1 {seg.start:.3f} {duration:.3f} <NA> <NA> {seg.speaker_id} <NA> <NA>\n")
                    
        logger.info(f"Results exported to {output_path} in {format} format")


def main():
    """Example usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Speaker Attribution System")
    parser.add_argument("audio", help="Path to audio file")
    parser.add_argument("--gemini-key", default="AIzaSyAJ_uGXKX_Rg0FO5rdSMPEHdlw-0G76E7g", help="Gemini API key")
    parser.add_argument("--hf-token", help="HuggingFace token for pyannote models")
    parser.add_argument("--num-speakers", type=int, help="Known number of speakers")
    parser.add_argument("--enroll", nargs=2, metavar=("NAME", "AUDIO"), help="Enroll a speaker")
    parser.add_argument("--output", default="results.json", help="Output file path")
    parser.add_argument("--format", default="json", choices=["json", "csv", "txt", "rttm"], help="Output format")
    
    args = parser.parse_args()
    
    # Initialize system
    system = SpeakerAttributionSystem(
        gemini_api_key=args.gemini_key,
        hf_token=args.hf_token
    )
    
    # Enroll speaker if requested
    if args.enroll:
        name, audio = args.enroll
        system.enroll_speaker(name, [audio])
        print(f"Enrolled speaker: {name}")
        return
        
    # Process audio
    segments = system.process_audio(
        args.audio,
        num_speakers=args.num_speakers
    )
    
    # Export results
    system.export_results(segments, args.output, args.format)
    
    # Print summary
    print(f"\nProcessing complete!")
    print(f"Total segments: {len(segments)}")
    
    identified = [s for s in segments if s.identified_name]
    print(f"Identified segments: {len(identified)}")
    
    speakers = set(s.speaker_id for s in segments)
    print(f"Unique speakers: {len(speakers)}")
    
    if identified:
        avg_confidence = np.mean([s.confidence for s in identified])
        print(f"Average confidence: {avg_confidence:.2f}")


if __name__ == "__main__":
    main()
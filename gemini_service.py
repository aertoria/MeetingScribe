import json
import logging
import os

from google import genai
from google.genai import types

# IMPORTANT: KEEP THIS COMMENT
# Follow these instructions when using this blueprint:
# - Note that the newest Gemini model series is "gemini-2.5-flash" or gemini-2.5-pro"
#   - do not change this unless explicitly requested by the user
# - Sometimes the google genai SDK has occasional type errors. You might need to run to validate, at time.  
# The SDK was recently renamed from google-generativeai to google-genai. This file reflects the new name and the new APIs.

# This API key is from Gemini Developer API Key, not vertex AI API Key
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def chat_with_gemini(message, context=None):
    """
    Chat with Gemini AI model for meeting assistance
    """
    try:
        # Prepare the conversation context
        system_prompt = """You are a helpful AI assistant integrated into a meeting transcription application. 
        You help users with meeting-related tasks such as:
        - Analyzing meeting content and transcripts
        - Suggesting action items and follow-ups
        - Answering questions about meeting discussions
        - Providing insights and summaries
        - General assistance with meeting management
        
        If provided with meeting context, use it to give more relevant responses.
        When analyzing transcripts with multiple speakers, acknowledge the different participants and their contributions."""
        
        # Build the conversation content
        conversation_parts = []
        
        if context:
            conversation_parts.append(f"Current meeting transcript:\n{context}")
        
        conversation_parts.append(f"User: {message}")
        
        full_content = "\n\n".join(conversation_parts)
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Content(role="user", parts=[types.Part(text=full_content)])
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=1000,
                temperature=0.7,
            ),
        )
        
        return response.text or "I'm sorry, I couldn't generate a response. Please try again."
        
    except Exception as e:
        logging.error(f"Error in Gemini chat: {str(e)}")
        return f"Sorry, I encountered an error: {str(e)}"
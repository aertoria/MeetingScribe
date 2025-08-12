import json
import os
from openai import OpenAI

# The newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# Do not change this unless explicitly requested by the user

#@ai safe
# Per user request: hard-code a fallback API key so the app never fails on startup
# if the environment variable is not set. Environment variable still takes precedence.
OPENAI_API_KEY = os.environ.get(
    "OPENAI_API_KEY",
    "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",
)
openai = OpenAI(api_key=OPENAI_API_KEY)

def generate_meeting_notes(transcript):
    """
    Generate structured meeting notes from a raw transcript using OpenAI
    """
    try:
        prompt = f"""
        Please analyze the following meeting transcript and generate comprehensive meeting notes in JSON format with enhanced action items extraction.
        
        The output should include:
        - summary: A concise 2-3 sentence summary of the meeting's main purpose and outcomes
        - key_points: List of main discussion points and topics covered
        - action_items: List of specific tasks, assignments, or follow-ups with details (who, what, when if mentioned)
        - decisions: List of concrete decisions made during the meeting
        - participants_mentioned: Names, roles, or departments mentioned in the transcript
        - next_steps: Any mentioned next steps, future meetings, or deadlines
        - priority_actions: Top 3 most important action items that need immediate attention
        - meeting_type: The type/purpose of meeting (e.g., "Planning", "Status Update", "Decision Making", "Brainstorming")
        
        For action items, be specific and extract:
        - What needs to be done
        - Who is responsible (if mentioned)  
        - Any deadlines or timeframes mentioned
        - Priority level if indicated
        
        Look for phrases like:
        - "We need to..."
        - "Someone should..."
        - "I'll take care of..."
        - "Let's make sure to..."
        - "Action item..."
        - "Follow up on..."
        - "By next week/month..."
        
        Transcript:
        {transcript}
        
        Please respond with valid JSON only.
        """
        
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional meeting secretary. Generate structured meeting notes from transcripts. Always respond with valid JSON format."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=1500
        )
        
        # Parse the JSON response
        content = response.choices[0].message.content
        if not content:
            raise Exception("Empty response from OpenAI")
        notes_data = json.loads(content)
        
        # Format the notes into a readable structure
        formatted_notes = format_meeting_notes(notes_data)
        
        return formatted_notes
        
    except Exception as e:
        raise Exception(f"Failed to generate meeting notes: {str(e)}")

def format_meeting_notes(notes_data):
    """
    Format the JSON notes data into a readable meeting notes format with enhanced action items
    """
    formatted = []
    
    # Meeting Type and Summary
    if notes_data.get('meeting_type'):
        formatted.append(f"## {notes_data['meeting_type']} Meeting")
        formatted.append("")
    
    if notes_data.get('summary'):
        formatted.append("## Executive Summary")
        formatted.append(notes_data['summary'])
        formatted.append("")
    
    # Priority Actions (highlighted section)
    if notes_data.get('priority_actions'):
        formatted.append("## 🔥 Priority Action Items")
        for i, item in enumerate(notes_data['priority_actions'], 1):
            formatted.append(f"{i}. {item}")
        formatted.append("")
    
    # All Action Items
    if notes_data.get('action_items'):
        formatted.append("## 📋 Complete Action Items")
        for i, item in enumerate(notes_data['action_items'], 1):
            formatted.append(f"{i}. {item}")
        formatted.append("")
    
    # Key Discussion Points
    if notes_data.get('key_points'):
        formatted.append("## 💬 Key Discussion Points")
        for point in notes_data['key_points']:
            formatted.append(f"• {point}")
        formatted.append("")
    
    # Decisions Made
    if notes_data.get('decisions'):
        formatted.append("## ✅ Decisions Made")
        for decision in notes_data['decisions']:
            formatted.append(f"• {decision}")
        formatted.append("")
    
    # Next Steps
    if notes_data.get('next_steps'):
        formatted.append("## ⏭️ Next Steps")
        for step in notes_data['next_steps']:
            formatted.append(f"• {step}")
        formatted.append("")
    
    # Participants
    if notes_data.get('participants_mentioned'):
        formatted.append("## 👥 Participants Mentioned")
        for participant in notes_data['participants_mentioned']:
            formatted.append(f"• {participant}")
        formatted.append("")
    
    return "\n".join(formatted)

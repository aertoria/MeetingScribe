import json
import os
from openai import OpenAI

# The newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# Do not change this unless explicitly requested by the user
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai = OpenAI(api_key=OPENAI_API_KEY)

def generate_meeting_notes(transcript):
    """
    Generate structured meeting notes from a raw transcript using OpenAI
    """
    try:
        prompt = f"""
        Please analyze the following meeting transcript and generate professional meeting notes in JSON format.
        
        The output should include:
        - summary: A concise summary of the meeting
        - key_points: List of main discussion points
        - action_items: List of tasks or follow-ups mentioned
        - decisions: List of decisions made during the meeting
        - participants_mentioned: Names or roles mentioned in the transcript
        - next_steps: Any mentioned next steps or future meetings
        
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
    Format the JSON notes data into a readable meeting notes format
    """
    formatted = []
    
    # Meeting Summary
    if notes_data.get('summary'):
        formatted.append("## Meeting Summary")
        formatted.append(notes_data['summary'])
        formatted.append("")
    
    # Key Points
    if notes_data.get('key_points'):
        formatted.append("## Key Discussion Points")
        for point in notes_data['key_points']:
            formatted.append(f"• {point}")
        formatted.append("")
    
    # Decisions Made
    if notes_data.get('decisions'):
        formatted.append("## Decisions Made")
        for decision in notes_data['decisions']:
            formatted.append(f"• {decision}")
        formatted.append("")
    
    # Action Items
    if notes_data.get('action_items'):
        formatted.append("## Action Items")
        for item in notes_data['action_items']:
            formatted.append(f"• {item}")
        formatted.append("")
    
    # Participants
    if notes_data.get('participants_mentioned'):
        formatted.append("## Participants Mentioned")
        for participant in notes_data['participants_mentioned']:
            formatted.append(f"• {participant}")
        formatted.append("")
    
    # Next Steps
    if notes_data.get('next_steps'):
        formatted.append("## Next Steps")
        for step in notes_data['next_steps']:
            formatted.append(f"• {step}")
        formatted.append("")
    
    return "\n".join(formatted)

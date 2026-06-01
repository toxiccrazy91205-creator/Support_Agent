import json
import re
from typing import Optional
from pydantic import BaseModel, Field
from support.models import SocialMessage, Lead
from .agents import get_llm

class SocialExtractionSchema(BaseModel):
    category: str = Field(description="One of: Support, Sales Inquiry, Complaint, General Comment, Spam")
    priority: str = Field(description="One of: High, Medium, Low. Automatically assign High for severe complaints or VIP sales.")
    summary: str = Field(description="A concise 1-sentence summary of the user's message")
    is_lead: bool = Field(description="True if the user seems interested in purchasing or hiring services")
    draft_response: str = Field(description="A suggested contextual reply, tailored to the specific platform (e.g., use emojis/hashtags for X/Instagram, professional for LinkedIn).")
    requires_escalation: bool = Field(description="True if the message is highly offensive, legally threatening, or requires immediate human escalation")

def process_social_message_ai(platform: str, message_type: str, sender_handle: str, content: str):
    """
    Analyzes a social media message, updates the database, and flags leads/escalations.
    """
    if not content or not content.strip():
        return
        
    llm = get_llm()
    prompt = f"""You are an expert Social Media Community Manager AI.
Analyze the following social media message and extract the required information into the exact JSON schema.
Ensure the 'draft_response' is appropriate for the platform context.

Platform: {platform}
Message Type: {message_type}
Sender Handle: {sender_handle}
Content: "{content}"
"""
    
    # Try structured output with a fallback parser for robustness
    try:
        structured_llm = llm.with_structured_output(SocialExtractionSchema)
        extracted = structured_llm.invoke(prompt)
        data = extracted.model_dump()
    except Exception as e:
        print(f"Structured output failed, attempting fallback JSON parse: {e}")
        try:
            # Fallback
            res = llm.invoke(prompt + "\nReturn ONLY valid JSON.")
            text_res = res.content.strip()
            start = text_res.find('{')
            end = text_res.rfind('}')
            if start != -1 and end != -1:
                text_res = text_res[start:end+1]
            text_res = re.sub(r'([{,]\s*)([a-zA-Z0-9_]+)(\s*:)', r'\1"\2"\3', text_res)
            data = json.loads(text_res)
        except Exception as e2:
            print(f"Fallback failed: {e2}")
            data = {
                "category": "General Comment",
                "priority": "Medium",
                "summary": content[:100],
                "is_lead": False,
                "draft_response": f"Thanks for reaching out on {platform}! We will look into this.",
                "requires_escalation": False
            }

    # Handle Escalation directly via status
    status = 'Escalated' if data.get('requires_escalation') else 'Pending Review'
    
    # Sometimes complaints are natively high priority and should be escalated
    if data.get('category') == 'Complaint' and data.get('priority') == 'High':
        status = 'Escalated'

    # Create SocialMessage Record
    SocialMessage.objects.create(
        platform=platform,
        message_type=message_type,
        sender_handle=sender_handle,
        content=content,
        category=data.get('category', 'General Comment'),
        priority=data.get('priority', 'Medium'),
        summary=data.get('summary', ''),
        draft_response=data.get('draft_response', ''),
        is_lead=data.get('is_lead', False),
        status=status
    )

    # Handle Lead Capture (basic mapping using handle)
    if data.get('is_lead'):
        Lead.objects.get_or_create(
            phone_number=f"{platform}_{sender_handle}", # Placeholder for unique ID
            defaults={
                'name': sender_handle,
                'email': '',
                'company': platform,
                'requirements': data.get('summary', ''),
                'status': 'New'
            }
        )

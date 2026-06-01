import os
import json
import re
from typing import TypedDict, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from support.models import CallRecord, Lead, Appointment
from .agents import get_llm
import dateutil.parser

class CallExtractionSchema(BaseModel):
    category: str = Field(description="One of: Support, Sales Inquiry, Appointment Booking, Complaint, General Inquiry")
    priority: str = Field(description="One of: High, Medium, Low")
    summary: str = Field(description="A concise 1-sentence summary of the caller's request")
    is_lead: bool = Field(description="True if the caller seems interested in purchasing or hiring services")
    extracted_name: Optional[str] = Field(description="The caller's name, if mentioned")
    extracted_email: Optional[str] = Field(description="The caller's email, if mentioned")
    extracted_requirement: Optional[str] = Field(description="Detailed requirements or needs of the caller")
    is_appointment: bool = Field(description="True if the caller wants to schedule a meeting or appointment")
    appointment_date_str: Optional[str] = Field(description="The date/time they want to meet, e.g. 'Tomorrow at 2pm' or 'Next Tuesday'")
    draft_response: str = Field(description="A polite, conversational text response to be spoken back to the user to confirm their request has been handled")

def process_call_transcript_ai(transcript: str, phone_number: str, call_sid: str) -> str:
    """
    Analyzes the call transcript, updates the database, and returns a spoken response.
    """
    if not transcript or not transcript.strip():
        # Fallback for silent calls
        CallRecord.objects.create(
            caller_phone=phone_number,
            call_sid=call_sid,
            transcript="[Silence/No Input]",
            category="General Inquiry",
            priority="Low",
            summary="Empty call transcript"
        )
        return "I didn't quite catch that. Please call back if you still need assistance. Goodbye!"

    llm = get_llm()
    prompt = f"""You are an expert call center AI analyzing a voice transcript.
Extract the required information into the JSON schema exactly.

Caller Phone: {phone_number}
Transcript: "{transcript}"
"""
    
    # Try with_structured_output first, but fallback to raw JSON extraction for robustness
    try:
        structured_llm = llm.with_structured_output(CallExtractionSchema)
        extracted = structured_llm.invoke(prompt)
        data = extracted.model_dump()
    except Exception as e:
        print(f"Structured output failed, attempting fallback JSON parse: {e}")
        try:
            # Fallback
            res = llm.invoke(prompt + "\nReturn ONLY valid JSON.")
            content = res.content.strip()
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1:
                content = content[start:end+1]
            content = re.sub(r'([{,]\s*)([a-zA-Z0-9_]+)(\s*:)', r'\1"\2"\3', content)
            data = json.loads(content)
        except Exception as e2:
            print(f"Fallback failed: {e2}")
            data = {
                "category": "Support",
                "priority": "Medium",
                "summary": transcript[:100],
                "is_lead": False,
                "is_appointment": False,
                "draft_response": "Thank you for calling. A representative will review your message."
            }

    # 1. Create Call Record
    record = CallRecord.objects.create(
        caller_phone=phone_number,
        call_sid=call_sid,
        transcript=transcript,
        category=data.get('category', 'Support'),
        priority=data.get('priority', 'Medium'),
        summary=data.get('summary', '')
    )

    # 2. Handle Lead Capture
    lead = None
    if data.get('is_lead') or data.get('is_appointment'):
        # Try to find existing lead by phone
        lead, created = Lead.objects.get_or_create(
            phone_number=phone_number,
            defaults={
                'name': data.get('extracted_name', 'Unknown Caller'),
                'email': data.get('extracted_email', ''),
                'company': 'Unknown',
                'requirements': data.get('extracted_requirement', data.get('summary', '')),
                'status': 'New'
            }
        )
        if not created:
            # Update existing lead with new info if available
            if data.get('extracted_name') and lead.name == 'Unknown Caller':
                lead.name = data.get('extracted_name')
            if data.get('extracted_email') and not lead.email:
                lead.email = data.get('extracted_email')
            lead.save()

    # 3. Handle Appointments
    if data.get('is_appointment') and data.get('appointment_date_str'):
        try:
            # Simple fuzzy parse for demo purposes. 
            # In production, use an LLM specifically instructed to output ISO8601, or use dateparser
            parsed_date = dateutil.parser.parse(data.get('appointment_date_str'), fuzzy=True)
        except Exception:
            # Fallback to now if unparseable
            parsed_date = datetime.now()
            
        Appointment.objects.create(
            lead=lead,
            scheduled_time=parsed_date,
            notes=f"Requested via call. Details: {data.get('appointment_date_str')}"
        )

    return data.get('draft_response', "Thank you for your message. We will get back to you shortly.")

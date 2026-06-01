import os
import json
import re
from typing import TypedDict, List, Dict, Any
from imap_tools import MailBox, AND
from django.core.mail import send_mail
from support.models import EmailRecord, Lead
from .agents import get_llm

class EmailState(TypedDict):
    raw_emails: List[Dict[str, str]]
    processed_emails: List[Dict[str, Any]]
    imap_user: str
    imap_password: str

def fetch_emails_node(state: EmailState) -> EmailState:
    imap_server = os.getenv('IMAP_SERVER', 'imap.gmail.com')
    imap_user = state.get('imap_user') or os.getenv('IMAP_USER')
    imap_password = state.get('imap_password') or os.getenv('IMAP_PASSWORD')
    
    emails = []
    
    if not all([imap_server, imap_user, imap_password]):
        print("IMAP credentials missing. Skipping fetch.")
        state['raw_emails'] = emails
        return state
        
    try:
        with MailBox(imap_server).login(imap_user, imap_password) as mailbox:
            for msg in mailbox.fetch(AND(seen=False), limit=10):
                emails.append({
                    'sender': msg.from_,
                    'subject': msg.subject,
                    'body': msg.text or msg.html
                })
    except Exception as e:
        print(f"IMAP Fetch Error: {e}")
        
    state['raw_emails'] = emails
    return state

def process_email_node(state: EmailState) -> EmailState:
    llm = get_llm()
    processed = []
    
    for email in state.get('raw_emails', []):
        prompt = f"""Analyze the following email and extract key information. 
Return EXACTLY a valid JSON object. ALL keys and string values MUST be enclosed in double quotes. Do not use markdown backticks.

Expected JSON Keys:
- "category": one of ["Support", "Sales", "Billing", "Internal", "Spam"]
- "priority": one of ["High", "Medium", "Low"]
- "summary": a 1-sentence summary of the email
- "is_lead": boolean true or false (true if they want to hire or buy services)
- "draft_response": a drafted polite reply to the email

Email Sender: {email['sender']}
Email Subject: {email['subject']}
Email Body: {email['body']}"""

        try:
            res = llm.invoke(prompt)
            content = res.content.strip()
            
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1:
                content = content[start:end+1]
                
            try:
                extracted = json.loads(content)
            except json.JSONDecodeError:
                # Fallback for unquoted keys
                content = re.sub(r'([{,]\s*)([a-zA-Z0-9_]+)(\s*:)', r'\1"\2"\3', content)
                extracted = json.loads(content)
                
            processed.append({
                'sender': email['sender'],
                'subject': email['subject'],
                'body': email['body'],
                'data': extracted
            })
        except Exception as e:
            print(f"Error processing email {email['subject']}: {e}")
            
    state['processed_emails'] = processed
    return state

def store_and_lead_capture_node(state: EmailState) -> EmailState:
    for item in state.get('processed_emails', []):
        sender = item['sender']
        subject = item['subject']
        body = item['body']
        data = item['data']
        
        # Save EmailRecord
        record = EmailRecord.objects.create(
            sender_email=sender,
            subject=subject,
            body=body,
            category=data.get('category', 'Support'),
            priority=data.get('priority', 'Medium'),
            summary=data.get('summary', ''),
            draft_response=data.get('draft_response', ''),
            is_lead=bool(data.get('is_lead', False)),
            status='Pending Review'
        )
        
        # Save Lead if applicable
        if record.is_lead:
            Lead.objects.create(
                name=sender.split('@')[0], # Fallback name
                phone_number="N/A", # WhatsApp schema requires this
                email=sender,
                company="Unknown",
                requirements=record.summary,
                status="New"
            )
            
    return state

# LangGraph Orchestration for Email
from langgraph.graph import StateGraph, START, END

builder = StateGraph(EmailState)
builder.add_node("fetch", fetch_emails_node)
builder.add_node("process", process_email_node)
builder.add_node("store", store_and_lead_capture_node)

builder.add_edge(START, "fetch")
builder.add_edge("fetch", "process")
builder.add_edge("process", "store")
builder.add_edge("store", END)

email_graph = builder.compile()

def run_email_agent(imap_user=None, imap_password=None):
    initial_state = {
        "raw_emails": [], 
        "processed_emails": [],
        "imap_user": imap_user,
        "imap_password": imap_password
    }
    return email_graph.invoke(initial_state)

def send_approved_email(record_id: int, final_body: str):
    try:
        record = EmailRecord.objects.get(id=record_id)
        # Using Django's built in send_mail which relies on SMTP config in settings
        # If settings aren't fully configured for SMTP, this will just print or fail gracefully.
        send_mail(
            subject=f"Re: {record.subject}",
            message=final_body,
            from_email=os.getenv('IMAP_USER', 'support@example.com'),
            recipient_list=[record.sender_email],
            fail_silently=True,
        )
        record.status = 'Sent'
        record.draft_response = final_body
        record.save()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

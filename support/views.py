import json
import requests
import os
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from .models import Customer, Lead, VoiceLead, VoiceSession, InteractionLog, EmailRecord, CallRecord, Appointment
from ai_engine.graph import run_whatsapp_agent
from ai_engine.browser_voice_agent import run_assistant_pipeline

def send_whatsapp_message(phone, text, media_link=None):
    if not settings.WHATSAPP_API_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        print("Missing WhatsApp credentials in settings.")
        return
        
    url = f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone
    }
    
    if media_link:
        payload["type"] = "document"
        payload["document"] = {"link": media_link, "caption": text}
    else:
        payload["type"] = "text"
        payload["text"] = {"body": text}
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to send WhatsApp message: {e}")

@csrf_exempt
def whatsapp_webhook(request):
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        if mode == 'subscribe' and token == settings.WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(challenge, status=200)
        return HttpResponse('error', status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Simulated Chat Tester handling (for local dashboard testing)
            if 'text' in data and 'from' in data and 'entry' not in data:
                sender_phone = data.get('from', 'unknown')
                message_text = data.get('text', '')
                result = run_whatsapp_agent(sender_phone, message_text)
                response_text = result.get('response_text', '')
                
                customer, _ = Customer.objects.get_or_create(phone_number=sender_phone)
                InteractionLog.objects.create(
                    customer=customer, message_in=message_text,
                    response_out=response_text, intent_detected=result.get('intent', 'unknown')
                )
                
                lead_data = result.get('extracted_lead_data')
                if lead_data and any(v for k, v in lead_data.items() if v):
                    Lead.objects.create(
                        name=lead_data.get('name', ''),
                        phone_number=sender_phone,
                        email=lead_data.get('email', ''),
                        company=lead_data.get('company', ''),
                        requirements=lead_data.get('requirements', ''),
                        status='New'
                    )
                return JsonResponse({
                    "status": "success", 
                    "reply": response_text, 
                    "intent": result.get('intent'),
                    "media_link": result.get('media_link')
                })

            # Real Meta WhatsApp payload structure parsing
            if 'entry' in data and data['entry']:
                for entry in data['entry']:
                    for change in entry.get('changes', []):
                        value = change.get('value', {})
                        if 'messages' in value:
                            for msg in value['messages']:
                                sender_phone = msg.get('from')
                                message_text = msg.get('text', {}).get('body', '')
                                
                                if sender_phone and message_text:
                                    # Run Agent
                                    result = run_whatsapp_agent(sender_phone, message_text)
                                    response_text = result.get('response_text', '')
                                    media_link = result.get('media_link')
                                    
                                    # Send reply to actual WhatsApp
                                    send_whatsapp_message(sender_phone, response_text, media_link)
                                    
                                    # Store logs
                                    customer, _ = Customer.objects.get_or_create(phone_number=sender_phone)
                                    InteractionLog.objects.create(
                                        customer=customer,
                                        message_in=message_text,
                                        response_out=response_text,
                                        intent_detected=result.get('intent', 'unknown')
                                    )
                                    
                                    # Extract lead data
                                    lead_data = result.get('extracted_lead_data')
                                    if lead_data and any(v for k, v in lead_data.items() if v):
                                        Lead.objects.create(
                                            name=lead_data.get('name', ''),
                                            phone_number=sender_phone,
                                            email=lead_data.get('email', ''),
                                            company=lead_data.get('company', ''),
                                            requirements=lead_data.get('requirements', ''),
                                            status='New'
                                        )

            return HttpResponse(status=200)
        except Exception as e:
            print(f"Webhook error: {e}")
            return HttpResponse(status=200) # Always return 200 so Meta doesn't retry
            
    return HttpResponse(status=405)

def dashboard_view(request):
    leads = Lead.objects.all().order_by('-id')
    return render(request, 'dashboard.html', {'lead_count': leads.count(), 'leads': leads[:10]})

def chat_logs_view(request):
    logs = InteractionLog.objects.all().order_by('-timestamp')
    return render(request, 'chat_logs.html', {'logs': logs[:50]})

def chat_tester_view(request):
    return render(request, 'chat_tester.html')

# --- Email Management Agent Views ---

from .models import EmailRecord
from ai_engine.email_agent import run_email_agent, send_approved_email

def email_inbox_view(request):
    if request.method == 'POST':
        imap_user = request.POST.get('imap_user')
        imap_password = request.POST.get('imap_password')
        # Trigger IMAP Fetch with dynamic credentials (or None to fallback to .env)
        run_email_agent(imap_user=imap_user, imap_password=imap_password)
        return redirect('email_inbox')
        
    current_tab = request.GET.get('tab', 'Pending Review')
    if current_tab not in ['Pending Review', 'Sent', 'Ignored']:
        current_tab = 'Pending Review'
        
    emails = EmailRecord.objects.filter(status=current_tab).order_by('-created_at')
    
    # Sort logically by priority (High -> Medium -> Low)
    priority_map = {'High': 0, 'Medium': 1, 'Low': 2}
    sorted_emails = sorted(emails, key=lambda x: priority_map.get(x.priority, 3))
    
    return render(request, 'email_inbox.html', {
        'emails': sorted_emails,
        'current_tab': current_tab
    })

def review_email_view(request, email_id):
    email = get_object_or_404(EmailRecord, id=email_id)
    return render(request, 'email_review.html', {'email': email})

def approve_and_send_email_view(request, email_id):
    if request.method == 'POST':
        action = request.POST.get('action')
        email = get_object_or_404(EmailRecord, id=email_id)
        
        if action == 'send':
            edited_body = request.POST.get('draft_response', '')
            send_approved_email(email.id, edited_body)
        elif action == 'ignore':
            email.status = 'Ignored'
            email.save()
            
        return redirect('email_inbox')
    return redirect('email_inbox')

# --- Voice Call Assistant Agent Views ---

from twilio.twiml.voice_response import VoiceResponse
from .models import CallRecord, Appointment
from ai_engine.call_agent import process_call_transcript_ai

@csrf_exempt
def twilio_voice_webhook(request):
    """
    Initial webhook hit by Twilio when a call comes in.
    """
    response = VoiceResponse()
    # Greet the user and gather their speech input
    gather = response.gather(input='speech', action='/support/voice/process-speech/', method='POST', timeout=5)
    gather.say("Hello. You have reached Agentic A I support. How can I help you today?", voice='alice')
    
    # If they don't say anything, it falls through to here
    response.say("We didn't receive any input. Goodbye!", voice='alice')
    response.hangup()
    
    return HttpResponse(str(response), content_type='text/xml')

@csrf_exempt
def twilio_process_speech(request):
    """
    Webhook hit by Twilio after capturing the user's speech.
    """
    speech_result = request.POST.get('SpeechResult', '')
    caller_phone = request.POST.get('From', 'Unknown')
    call_sid = request.POST.get('CallSid', 'Unknown')
    
    response = VoiceResponse()
    
    if speech_result:
        # Pass to LangChain AI Engine
        ai_spoken_response = process_call_transcript_ai(speech_result, caller_phone, call_sid)
        response.say(ai_spoken_response, voice='alice')
    else:
        response.say("I'm sorry, I couldn't hear you clearly. Please try calling again.", voice='alice')
        
    response.hangup()
    return HttpResponse(str(response), content_type='text/xml')

def call_dashboard_view(request):
    calls = CallRecord.objects.all().order_by('-timestamp')
    appointments = Appointment.objects.all().order_by('-scheduled_time')
    voice_sessions = VoiceSession.objects.all().order_by('-created_at')
    leads = VoiceLead.objects.all().order_by('-id')
    
    context = {
        'total_calls': calls.count(),
        'total_appointments': appointments.count(),
        'high_priority_count': calls.filter(priority='High').count(),
        'recent_calls': calls[:15],
        'upcoming_appointments': appointments[:10],
        'voice_sessions': voice_sessions,
        'leads': leads
    }
    return render(request, 'call_dashboard.html', context)

@csrf_exempt
def process_voice_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message', '')
            session_history = data.get('session_history', [])
            session_id = data.get('session_id', '')
            
            result = run_assistant_pipeline(message, session_history)
            
            ai_response = result.get('ai_response', 'I am sorry, I did not understand that.')
            extracted_data = result.get('extracted_lead_data', {})
            lead_score = result.get('lead_score', 0)
            summary = result.get('summary', '')
            action_items = result.get('action_items', '')
            
            email = extracted_data.get('email')
            phone = extracted_data.get('phone')
            lead = None
            if phone or email:
                # Try phone first
                if phone:
                    lead, _ = VoiceLead.objects.get_or_create(phone=phone)
                elif email:
                    lead, _ = VoiceLead.objects.get_or_create(email=email)
            else:
                if any(extracted_data.values()):
                    lead = VoiceLead.objects.create()
                    
            if lead:
                if extracted_data.get('name'): lead.name = extracted_data['name']
                if extracted_data.get('phone'): lead.phone = extracted_data['phone']
                if extracted_data.get('email'): lead.email = extracted_data['email']
                if extracted_data.get('company'): lead.company = extracted_data['company']
                if extracted_data.get('requirement'): lead.requirement = extracted_data['requirement']
                if lead_score > lead.lead_score:
                    lead.lead_score = lead_score
                lead.save()

            full_transcript = ""
            for msg in session_history:
                full_transcript += f"{msg.get('role', 'unknown')}: {msg.get('content', '')}\n"
            full_transcript += f"user: {message}\n"
            full_transcript += f"ai: {ai_response}\n"

            if session_id:
                session, _ = VoiceSession.objects.get_or_create(session_id=session_id)
                session.lead = lead
                session.transcript = full_transcript
                session.summary = summary
                session.action_items = action_items
                session.save()
            else:
                VoiceSession.objects.create(
                    lead=lead,
                    transcript=full_transcript,
                    summary=summary,
                    action_items=action_items
                )

            return JsonResponse({
                'response': ai_response,
                'is_complete': False
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Invalid request'}, status=400)

# --- Social Media Reply Agent Views ---

from .models import SocialMessage
from ai_engine.social_agent import process_social_message_ai

def social_inbox_view(request):
    current_tab = request.GET.get('tab', 'Pending Review')
    if current_tab not in ['Pending Review', 'Replied', 'Escalated', 'Ignored']:
        current_tab = 'Pending Review'
        
    messages = SocialMessage.objects.filter(status=current_tab).order_by('-created_at')
    
    # Sort logically by priority (High -> Medium -> Low)
    priority_map = {'High': 0, 'Medium': 1, 'Low': 2}
    sorted_messages = sorted(messages, key=lambda x: priority_map.get(x.priority, 3))
    
    return render(request, 'social_inbox.html', {
        'messages': sorted_messages,
        'current_tab': current_tab
    })

def social_review_view(request, msg_id):
    msg = get_object_or_404(SocialMessage, id=msg_id)
    return render(request, 'social_review.html', {'msg': msg})

def social_action_view(request, msg_id):
    if request.method == 'POST':
        action = request.POST.get('action')
        msg = get_object_or_404(SocialMessage, id=msg_id)
        
        if action == 'reply':
            # In a real app, this sends the drafted response via platform API
            edited_body = request.POST.get('draft_response', '')
            msg.draft_response = edited_body
            msg.status = 'Replied'
            msg.save()
        elif action == 'escalate':
            msg.status = 'Escalated'
            msg.save()
        elif action == 'ignore':
            msg.status = 'Ignored'
            msg.save()
            
        return redirect('social_inbox')
    return redirect('social_inbox')

@csrf_exempt
def seed_social_data_view(request):
    """
    Utility endpoint to mock incoming social messages for testing.
    """
    if request.method == 'POST':
        platform = request.POST.get('platform', 'X')
        message_type = request.POST.get('message_type', 'DM')
        sender_handle = request.POST.get('sender_handle', '@test_user')
        content = request.POST.get('content', '')
        
        if content:
            process_social_message_ai(platform, message_type, sender_handle, content)
            
    return redirect('social_inbox')

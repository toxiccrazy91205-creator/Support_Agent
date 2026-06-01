import json
import requests
import os
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from .models import Lead, InteractionLog, Customer
from ai_engine.graph import run_whatsapp_agent

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

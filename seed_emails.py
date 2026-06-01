import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'whatsapp_agent_project.settings')
django.setup()

from support.models import EmailRecord, Lead

# Clear existing dummy data to avoid duplicates if run multiple times
EmailRecord.objects.all().delete()

# Seed Email 1: A High Priority Lead
e1 = EmailRecord.objects.create(
    sender_email='sarah.connor@cyberdyne.com',
    subject='Interested in enterprise licensing for our team',
    body='Hi Team,\n\nWe are looking to roll out your autonomous agents across our entire support floor. We have about 500 agents and need a custom enterprise SLA.\n\nCould we set up a call this week to discuss pricing and implementation timelines?\n\nThanks,\nSarah',
    category='Sales',
    priority='High',
    summary='Sarah from Cyberdyne wants to discuss enterprise pricing for a 500-seat rollout of autonomous agents.',
    draft_response='Hi Sarah,\n\nThank you for reaching out! We would be thrilled to support Cyberdyne.\n\nI have passed your request to our enterprise sales director, who will reach out shortly to schedule a call this week.\n\nBest regards,\nAgentic AI Team',
    is_lead=True,
    status='Pending Review'
)
Lead.objects.create(
    name='sarah.connor',
    phone_number='N/A',
    email='sarah.connor@cyberdyne.com',
    company='Unknown',
    requirements='Sarah from Cyberdyne wants to discuss enterprise pricing for a 500-seat rollout of autonomous agents.',
    status='New'
)

# Seed Email 2: A Medium Priority Support Ticket
e2 = EmailRecord.objects.create(
    sender_email='john.doe@startup.io',
    subject='Issue with webhook configuration',
    body='Hello,\n\nI am trying to connect my WhatsApp business account but the webhook is failing validation. The meta dashboard says the verify token is incorrect, even though I copied it exactly from the .env file.\n\nPlease help.\n\nJohn',
    category='Support',
    priority='Medium',
    summary='John is experiencing a webhook validation failure when connecting his WhatsApp account in the Meta dashboard.',
    draft_response='Hi John,\n\nI am sorry you are experiencing this issue. Please double check that there are no trailing spaces in your WHATSAPP_VERIFY_TOKEN inside your .env file. Also ensure that you have restarted the Django server after making changes to the file.\n\nLet me know if this resolves the issue!\n\nBest regards,\nAgentic AI Support',
    is_lead=False,
    status='Pending Review'
)

# Seed Email 3: A Low Priority Spam/Internal Email
e3 = EmailRecord.objects.create(
    sender_email='newsletter@saas-weekly.com',
    subject='Top 10 AI tools you need in 2026',
    body='Check out our latest blog post on the top AI tools that are revolutionizing the workspace. Click here to read more!',
    category='Spam',
    priority='Low',
    summary='A promotional newsletter about top AI tools for 2026.',
    draft_response='',
    is_lead=False,
    status='Pending Review'
)

print("Successfully seeded 3 dummy emails into the database!")

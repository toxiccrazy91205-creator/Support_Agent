from django.db import models

class Customer(models.Model):
    phone_number = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.phone_number

class Lead(models.Model):
    name = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    company = models.CharField(max_length=100, blank=True, null=True)
    requirements = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, default='New')
    lead_score = models.IntegerField(default=0)

    def __str__(self):
        return f"Lead: {self.name or self.phone_number} - {self.company}"

class VoiceLead(models.Model):
    name = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    company = models.CharField(max_length=100, blank=True, null=True)
    requirement = models.TextField(blank=True, null=True)
    lead_score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or self.email or "Unknown Lead"

class VoiceSession(models.Model):
    session_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    lead = models.ForeignKey(VoiceLead, on_delete=models.SET_NULL, null=True, blank=True, related_name='voice_sessions')
    transcript = models.TextField(blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    action_items = models.TextField(blank=True, null=True)
    duration_seconds = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Browser Voice Session on {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

class InteractionLog(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    message_in = models.TextField()
    response_out = models.TextField()
    intent_detected = models.CharField(max_length=50, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.timestamp}] {self.customer.phone_number}: {self.intent_detected}"

class EmailRecord(models.Model):
    STATUS_CHOICES = (
        ('Pending Review', 'Pending Review'),
        ('Sent', 'Sent'),
        ('Ignored', 'Ignored'),
    )

    sender_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    category = models.CharField(max_length=50, blank=True, null=True)
    priority = models.CharField(max_length=20, blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    draft_response = models.TextField(blank=True, null=True)
    is_lead = models.BooleanField(default=False)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Pending Review')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Email from {self.sender_email}: {self.subject}"

class CallRecord(models.Model):
    caller_phone = models.CharField(max_length=20)
    call_sid = models.CharField(max_length=100, unique=True)
    transcript = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=50, blank=True, null=True)
    priority = models.CharField(max_length=20, blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Call from {self.caller_phone} at {self.timestamp}"

class Appointment(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, null=True, blank=True, related_name='appointments')
    scheduled_time = models.DateTimeField()
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        lead_name = self.lead.name if self.lead and self.lead.name else "Unknown Lead"
        return f"Appointment with {lead_name} at {self.scheduled_time}"

class SocialMessage(models.Model):
    STATUS_CHOICES = (
        ('Pending Review', 'Pending Review'),
        ('Replied', 'Replied'),
        ('Escalated', 'Escalated'),
        ('Ignored', 'Ignored'),
    )

    platform = models.CharField(max_length=50) # Instagram, Facebook, X, LinkedIn
    message_type = models.CharField(max_length=50) # DM, Comment
    sender_handle = models.CharField(max_length=100)
    content = models.TextField()
    category = models.CharField(max_length=50, blank=True, null=True)
    priority = models.CharField(max_length=20, blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    draft_response = models.TextField(blank=True, null=True)
    is_lead = models.BooleanField(default=False)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Pending Review')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.platform} {self.message_type} from {self.sender_handle}"

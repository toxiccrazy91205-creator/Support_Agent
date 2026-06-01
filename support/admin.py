from django.contrib import admin
from .models import Customer, Lead, InteractionLog, EmailRecord, CallRecord, Appointment

admin.site.register(Customer)
admin.site.register(Lead)
admin.site.register(InteractionLog)
admin.site.register(EmailRecord)
admin.site.register(CallRecord)
admin.site.register(Appointment)

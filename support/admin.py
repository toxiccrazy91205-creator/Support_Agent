from django.contrib import admin
from .models import Customer, Lead, InteractionLog, EmailRecord

admin.site.register(Customer)
admin.site.register(Lead)
admin.site.register(InteractionLog)
admin.site.register(EmailRecord)

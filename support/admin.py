from django.contrib import admin
from .models import Customer, Lead, InteractionLog

admin.site.register(Customer)
admin.site.register(Lead)
admin.site.register(InteractionLog)

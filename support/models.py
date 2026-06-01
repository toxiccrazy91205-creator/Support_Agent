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

    def __str__(self):
        return f"Lead: {self.name or self.phone_number} - {self.company}"

class InteractionLog(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    message_in = models.TextField()
    response_out = models.TextField()
    intent_detected = models.CharField(max_length=50, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.timestamp}] {self.customer.phone_number}: {self.intent_detected}"

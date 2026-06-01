import os
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

def get_llm():
    api_key = os.environ.get('OPENROUTER_API_KEY', 'dummy_key')
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        model="openai/gpt-3.5-turbo",
        api_key=api_key,
        temperature=0
    )

class LeadExtractionSchema(BaseModel):
    name: str = Field(default="", description="The person's full name")
    email: str = Field(default="", description="The person's email address")
    company: str = Field(default="", description="The company the person works for")
    requirements: str = Field(default="", description="The services or products the person is interested in")

class IntentSchema(BaseModel):
    intent: str = Field(description="One of: 'faq', 'catalog', 'lead', 'invoice'")

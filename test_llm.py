import sys
import os

sys.path.append('e:/ASTNIQ-SOLUTION/task/Whatsapp_Support_Agent/whatsapp_agent_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'whatsapp_agent_project.settings')
import django
django.setup()

from ai_engine.agents import get_llm
llm = get_llm()

prompt = """Extract lead information (name, email, company, requirements) from the following message. If a field is missing, leave it empty.
Return EXACTLY a JSON object with keys "name", "email", "company", "requirements". Do not use markdown backticks.

Message: I want to hire you for web dev services. My name is Bob and my email is bob@test.com . I work at FreakSolutions."""

try:
    res = llm.invoke(prompt)
    print("RAW LLM OUTPUT:")
    print(repr(res.content))
    print("---")
except Exception as e:
    print("EXCEPTION:")
    print(e)

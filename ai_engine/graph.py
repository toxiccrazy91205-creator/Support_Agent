from typing import TypedDict, Optional, Dict, Any
from langgraph.graph import StateGraph, START, END
from .agents import get_llm, LeadExtractionSchema, IntentSchema
from .vector_store import search_knowledge_base, seed_knowledge_base

seed_knowledge_base()

class State(TypedDict):
    sender_phone: str
    message: str
    intent: Optional[str]
    extracted_lead_data: Optional[Dict[str, Any]]
    response_text: Optional[str]
    media_link: Optional[str]

def classifier_node(state: State) -> State:
    llm = get_llm()
    prompt = f"""Analyze the user message and determine the intent. You must reply with EXACTLY ONE WORD from this list: faq, catalog, lead, invoice. Do not explain.
- If they ask a general question or say "hi", "hello", return faq.
- If they ask for a catalog or brochure, return catalog.
- If they want to hire you, ask for services, or provide contact info, return lead.
- If they ask for an invoice or billing, return invoice.

User Message: {state['message']}"""
    try:
        res = llm.invoke(prompt)
        intent_text = res.content.lower().strip()
        import re
        intent_text = re.sub(r'[^\w\s]', '', intent_text)
        words = intent_text.split()
        
        if 'catalog' in words:
            intent = 'catalog'
        elif 'lead' in words:
            intent = 'lead'
        elif 'invoice' in words:
            intent = 'invoice'
        else:
            intent = 'faq'
    except Exception as e:
        print(f"Error in classifier: {e}")
        intent = 'faq'
    
    state['intent'] = intent
    return state

def faq_node(state: State) -> State:
    llm = get_llm()
    kb_result = search_knowledge_base(state['message'])
    
    prompt = f"User asks: {state['message']}\nContext: {kb_result}\n\nDraft a polite, helpful response based ONLY on the context."
    response = llm.invoke(prompt)
    
    state['response_text'] = response.content
    return state

def catalog_node(state: State) -> State:
    llm = get_llm()
    kb_result = search_knowledge_base("catalog")
    
    prompt = f"User is asking for a catalog. Draft a polite message offering the catalog.\nContext: {kb_result}"
    response = llm.invoke(prompt)
    
    state['response_text'] = response.content
    state['media_link'] = "https://example.com/catalog.pdf"
    return state

def lead_capture_node(state: State) -> State:
    llm = get_llm()
    try:
        prompt = f"""Extract lead information (name, email, company, requirements) from the following message. If a field is missing, leave it empty.
Return EXACTLY a valid JSON object. ALL keys and string values MUST be enclosed in double quotes ("key": "value"). Do not use markdown backticks.

Message: {state['message']}"""
        res = llm.invoke(prompt)
        content = res.content.strip()
        
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
            content = content[start:end+1]
            
        import json
        try:
            extracted = json.loads(content)
        except json.JSONDecodeError:
            # Fallback to fix unquoted keys returned by some LLMs
            import re
            content = re.sub(r'([{,]\s*)([a-zA-Z0-9_]+)(\s*:)', r'\1"\2"\3', content)
            extracted = json.loads(content)
        
        state['extracted_lead_data'] = extracted
        
        missing = []
        if not extracted.get('name'): missing.append('name')
        if not extracted.get('email'): missing.append('email')
        
        if missing:
            state['response_text'] = f"Thank you! I have noted your interest. Our team will get back to you shortly. Could you confirm your {' and '.join(missing)} so we can reach out?"
        else:
            state['response_text'] = f"Thank you, {extracted.get('name')}! I have noted your interest and saved your contact details. Our team will get back to you shortly."
    except Exception as e:
        print(f"Error in lead capture structured output: {e}")
        state['extracted_lead_data'] = {"name": "", "email": "", "company": "", "requirements": ""}
        state['response_text'] = "Thank you! I have noted your interest. Our team will get back to you shortly. Could you confirm your name and email if you haven't provided them?"
    
    return state

def invoice_node(state: State) -> State:
    state['response_text'] = f"Here is the latest mock invoice for your account ({state['sender_phone']}). Please let us know if you need any adjustments."
    state['media_link'] = "https://example.com/invoice_mock.pdf"
    return state

def output_node(state: State) -> State:
    return state

def route_intent(state: State):
    intent = state.get('intent', 'faq')
    if intent in ['catalog', 'lead', 'invoice']:
        return intent
    return 'faq'

builder = StateGraph(State)

builder.add_node("classifier", classifier_node)
builder.add_node("faq", faq_node)
builder.add_node("catalog", catalog_node)
builder.add_node("lead", lead_capture_node)
builder.add_node("invoice", invoice_node)
builder.add_node("output", output_node)

builder.add_edge(START, "classifier")
builder.add_conditional_edges(
    "classifier",
    route_intent,
    {
        "faq": "faq",
        "catalog": "catalog",
        "lead": "lead",
        "invoice": "invoice"
    }
)

builder.add_edge("faq", "output")
builder.add_edge("catalog", "output")
builder.add_edge("lead", "output")
builder.add_edge("invoice", "output")
builder.add_edge("output", END)

graph = builder.compile()

def run_whatsapp_agent(sender_phone: str, message: str) -> Dict[str, Any]:
    initial_state = {
        "sender_phone": sender_phone,
        "message": message,
        "intent": None,
        "extracted_lead_data": None,
        "response_text": None,
        "media_link": None
    }
    result = graph.invoke(initial_state)
    return result

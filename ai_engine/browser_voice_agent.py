import os
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field
from ai_engine.agents import get_llm

# Using get_llm to avoid missing api_key issues
llm = get_llm()
llm.temperature = 0.7
llm_structured = get_llm()
llm_structured.temperature = 0

class AgentState(TypedDict):
    chat_history: List[Dict[str, str]]
    current_input: str
    ai_response: str
    extracted_lead_data: Dict[str, Any]
    lead_score: int
    summary: str
    action_items: str

class LeadDataExtraction(BaseModel):
    name: str = Field(description="The name of the lead", default="")
    email: str = Field(description="The email address of the lead", default="")
    phone: str = Field(description="The phone number of the lead", default="")
    company: str = Field(description="The company the lead works for", default="")
    requirement: str = Field(description="What the lead is looking for or needs", default="")

class QualificationData(BaseModel):
    lead_score: int = Field(description="A score from 0 to 100 indicating lead quality based on requirement", default=0)

class SummaryData(BaseModel):
    summary: str = Field(description="A short summary of the conversation", default="")
    action_items: str = Field(description="Action items or next steps", default="")

def conversation_node(state: AgentState):
    history = state.get("chat_history", [])
    current_input = state.get("current_input", "")
    
    messages = [SystemMessage(content="You are a helpful AI voice assistant acting as a sales representative. Be concise and natural, as your responses will be spoken aloud. Maintain a professional yet friendly tone.")]
    for msg in history:
        if msg.get('role') == 'user':
            messages.append(HumanMessage(content=msg.get('content')))
        elif msg.get('role') == 'ai':
            messages.append(AIMessage(content=msg.get('content')))
            
    messages.append(HumanMessage(content=current_input))
    
    response = llm.invoke(messages)
    return {"ai_response": response.content}

def extraction_node(state: AgentState):
    history = state.get("chat_history", [])
    current_input = state.get("current_input", "")
    ai_response = state.get("ai_response", "")
    
    full_text = ""
    for msg in history:
        full_text += f"{msg.get('role')}: {msg.get('content')}\n"
    full_text += f"user: {current_input}\n"
    full_text += f"ai: {ai_response}\n"
    
    prompt = f"""Extract the lead information from the following conversation. If a piece of information is not present, leave it as an empty string.
Return EXACTLY a valid JSON object with keys: "name", "email", "phone", "company", "requirement". ALL keys and string values MUST be enclosed in double quotes. Do not use markdown backticks.

Conversation:
{full_text}"""
    try:
        res = llm.invoke([HumanMessage(content=prompt)])
        content = res.content.strip()
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
            content = content[start:end+1]
        import json
        extracted = json.loads(content)
        return {"extracted_lead_data": extracted}
    except Exception as e:
        print(f"Error in extraction: {e}")
        return {"extracted_lead_data": {}}

def qualification_node(state: AgentState):
    extracted_data = state.get("extracted_lead_data", {})
    requirement = extracted_data.get("requirement", "")
    
    if not requirement:
        return {"lead_score": 0}
        
    prompt = f"""Based on the following requirement, score the lead from 0 to 100. Higher score means clear, high-value requirement.
Return EXACTLY a valid JSON object with key "lead_score" mapping to an integer. Do not use markdown backticks.

Requirement: {requirement}"""
    try:
        res = llm.invoke([HumanMessage(content=prompt)])
        content = res.content.strip()
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
            content = content[start:end+1]
        import json
        result = json.loads(content)
        return {"lead_score": int(result.get("lead_score", 0))}
    except Exception as e:
        print(f"Error in qualification: {e}")
        return {"lead_score": 0}

def summary_node(state: AgentState):
    history = state.get("chat_history", [])
    current_input = state.get("current_input", "")
    ai_response = state.get("ai_response", "")
    
    full_text = ""
    for msg in history:
        full_text += f"{msg.get('role')}: {msg.get('content')}\n"
    full_text += f"user: {current_input}\n"
    full_text += f"ai: {ai_response}\n"
    
    prompt = f"""Summarize the following conversation and list action items.
Return EXACTLY a valid JSON object with keys "summary" and "action_items" as strings. Do not use markdown backticks.

Conversation:
{full_text}"""
    try:
        res = llm.invoke([HumanMessage(content=prompt)])
        content = res.content.strip()
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
            content = content[start:end+1]
        import json
        result = json.loads(content)
        return {"summary": result.get("summary", ""), "action_items": result.get("action_items", "")}
    except Exception as e:
        print(f"Error in summary: {e}")
        return {"summary": "Error generating summary.", "action_items": ""}

workflow = StateGraph(AgentState)

workflow.add_node("conversation", conversation_node)
workflow.add_node("extraction", extraction_node)
workflow.add_node("qualification", qualification_node)
workflow.add_node("summary", summary_node)

workflow.set_entry_point("conversation")
workflow.add_edge("conversation", "extraction")
workflow.add_edge("extraction", "qualification")
workflow.add_edge("qualification", "summary")
workflow.add_edge("summary", END)

app = workflow.compile()

def run_assistant_pipeline(current_input: str, chat_history: List[Dict[str, str]]):
    initial_state = {
        "chat_history": chat_history,
        "current_input": current_input,
        "ai_response": "",
        "extracted_lead_data": {},
        "lead_score": 0,
        "summary": "",
        "action_items": ""
    }
    result = app.invoke(initial_state)
    return result

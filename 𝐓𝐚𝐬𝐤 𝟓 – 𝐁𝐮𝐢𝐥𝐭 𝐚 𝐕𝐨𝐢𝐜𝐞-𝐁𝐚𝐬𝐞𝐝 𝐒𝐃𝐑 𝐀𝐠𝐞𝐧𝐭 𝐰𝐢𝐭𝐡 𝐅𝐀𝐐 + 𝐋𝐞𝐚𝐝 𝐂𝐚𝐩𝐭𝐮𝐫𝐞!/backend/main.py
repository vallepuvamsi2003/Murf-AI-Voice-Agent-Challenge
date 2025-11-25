from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import json
import os
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not os.path.exists("leads"):
    os.makedirs("leads")

with open("company_data.json", "r") as f:
    KNOWLEDGE_BASE = json.load(f)

# --- Data Models ---
class LeadProfile(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    use_case: Optional[str] = None
    team_size: Optional[str] = None
    timeline: Optional[str] = None

class ChatRequest(BaseModel):
    user_input: str
    lead_data: LeadProfile
    conversation_step: str

class ChatResponse(BaseModel):
    agent_response: str
    updated_lead_data: LeadProfile
    updated_step: str
    is_complete: bool

# --- Helper Functions ---
def find_faq_answer(text):
    text = text.lower()
    for entry in KNOWLEDGE_BASE["faqs"]:
        for keyword in entry["keywords"]:
            if keyword in text:
                return entry["answer"]
    return None

def save_lead(lead: LeadProfile):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"leads/lead_{lead.name}_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump(lead.dict(), f, indent=4)
    return filename

# --- Main Logic ---

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    user_text = request.user_input.strip()
    lead = request.lead_data
    step = request.conversation_step
    
    # 0. Stop if finished
    if step == "finished":
        return ChatResponse(
            agent_response="",
            updated_lead_data=lead,
            updated_step="finished",
            is_complete=True
        )

    # 1. Check Profile Completeness
    profile_full = all([lead.name, lead.company, lead.role, lead.email, lead.use_case, lead.team_size, lead.timeline])

    # 2. Check Exit Intents
    basic_exits = ["bye", "exit", "done", "that's all", "thank you", "thanks"]
    conditional_exits = ["no", "nope", "nah", "nothing"] 
    is_exit = False
    
    if any(w in user_text.lower() for w in basic_exits):
        is_exit = True
    elif profile_full and any(w in user_text.lower() for w in conditional_exits):
        is_exit = True

    if is_exit:
        save_lead(lead)
        summary = (
            f"Thanks {lead.name}. I have captured your details for {lead.company}. "
            f"We will contact you at {lead.email} regarding your {lead.use_case} solution "
            f"for your team of {lead.team_size}. I've noted that you are planning to go live {lead.timeline}. "
            "Our team will reach out shortly. Have a great day!"
        )
        return ChatResponse(
            agent_response=summary,
            updated_lead_data=lead,
            updated_step="finished",
            is_complete=True
        )

    # 3. Check FAQ (But don't block lead capture yet)
    faq_answer = find_faq_answer(user_text)
    
    # 4. Lead Collection (Slot Filling) - FIXED PRIORITY
    # We attempt to save data even if an FAQ was found, to prevent loops.
    if user_text:
        if not lead.name: lead.name = user_text
        elif not lead.company: lead.company = user_text
        elif not lead.role: lead.role = user_text
        elif not lead.email: lead.email = user_text
        elif not lead.use_case:
            # --- FIX: ROBUST "SOMETHING ELSE" DETECTION ---
            text_lower = user_text.lower()
            
            # Check if input is EXACTLY "something else" or "i need something else" (vague)
            # If the user says "Banking solution", we save it.
            # If the user says "Something else", we wait.
            
            is_vague = text_lower in ["something else", "i need something else", "i want something else"]
            
            if is_vague:
                pass # Don't save, wait for next prompt to ask for specification
            else:
                lead.use_case = user_text # Save the specific answer

        elif not lead.team_size: lead.team_size = user_text
        elif not lead.timeline: lead.timeline = user_text

    # 5. Determine Next Question
    next_question = ""
    if not lead.name: next_question = "May I start with your name?"
    elif not lead.company: next_question = f"Thanks {lead.name}. Which company are you representing?"
    elif not lead.role: next_question = "And what is your role there?"
    elif not lead.email: next_question = "What's the best email to reach you at?"
    elif not lead.use_case:
        # If we are here, lead.use_case is still None.
        # This means the user gave a VAGUE answer (triggered is_vague above).
        # So we ask the specific clarification question.
        if "something else" in user_text.lower():
             next_question = "Could you please specify what kind of solution you are looking for?"
        else:
             next_question = "Are you looking for a Payment Gateway, Payroll solution, or something else?"
             
    elif not lead.team_size: next_question = "Roughly how large is your team?"
    elif not lead.timeline: next_question = "When are you planning to go live with this solution?"
    else: next_question = "I have all your details. Do you have any other questions for me?"

    # 6. Construct Response
    response_text = ""
    
    if not user_text and step == "greeting":
        response_text = "Welcome to Razorpay! I'm Riya, your sales assistant. I can answer questions about our products and pricing. To start, may I ask your name?"
        step = "collecting"
    
    elif faq_answer:
        # If an FAQ was triggered, we still want to move to the next question
        # UNLESS the question was regarding the current field (e.g. asking about Payment Gateway while selecting Use Case)
        # In that case, we acknowledge the FAQ but assume the next prompt is still valid.
        response_text = f"{faq_answer} By the way, {next_question}"
        step = "collecting"
        
    else:
        response_text = next_question
        step = "collecting"

    return ChatResponse(
        agent_response=response_text,
        updated_lead_data=lead,
        updated_step=step,
        is_complete=False
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
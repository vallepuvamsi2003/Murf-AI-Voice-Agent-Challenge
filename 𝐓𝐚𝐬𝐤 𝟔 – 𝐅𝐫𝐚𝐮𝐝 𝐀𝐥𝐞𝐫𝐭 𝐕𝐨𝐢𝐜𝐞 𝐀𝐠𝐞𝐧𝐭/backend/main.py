from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import os
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "database.json"

# --- Models ---
class ChatState(BaseModel):
    step: str = "greeting"  # greeting, verification, transaction_review, finished
    current_user_name: Optional[str] = None
    attempts: int = 0

class ChatRequest(BaseModel):
    user_input: str
    state: ChatState

class ChatResponse(BaseModel):
    message: str
    state: ChatState
    case_details: Optional[Dict[str, Any]] = None # To show on UI dashboard
    is_complete: bool

# --- DB Helpers ---
def load_db():
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_case(name):
    data = load_db()
    for case in data:
        if case["userName"].lower() == name.lower():
            return case
    return None

def update_case_status(name, new_status, outcome_note):
    data = load_db()
    for case in data:
        if case["userName"].lower() == name.lower():
            case["status"] = new_status
            case["outcome_note"] = outcome_note
            save_db(data)
            return True
    return False

# --- Logic ---

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    text = req.user_input.strip().lower()
    state = req.state
    response_text = ""
    case_data = None
    is_complete = False

    # 1. Greeting -> Ask for Name
    if state.step == "greeting":
        if not text: # Initial Load
            response_text = "This is the HDFC Fraud Prevention Department. I am calling regarding suspicious activity on your card. For security, please state your name."
        else:
            # User provided name, try to find case
            case = get_case(text)
            if case:
                state.current_user_name = case["userName"]
                state.step = "verification"
                response_text = f"Thank you, {case['userName']}. To verify your identity, please answer your security question: {case['securityQuestion']}"
                case_data = case # Send to UI to display basic info
            else:
                response_text = "I could not find a case under that name. Please state your name exactly as it appears on your account."

    # 2. Verification -> Check Security Answer
    elif state.step == "verification":
        case = get_case(state.current_user_name)
        case_data = case
        
        # Check Answer
        if text == case["securityAnswer"].lower():
            state.step = "transaction_review"
            response_text = (f"Identity verified. We flagged a transaction at {case['transactionName']} "
                             f"for {case['amount']} on {case['transactionTime']}. "
                             f"Location: {case['location']}. Did you authorize this transaction? (Yes/No)")
        else:
            state.attempts += 1
            if state.attempts >= 2:
                # Failed too many times
                update_case_status(state.current_user_name, "verification_failed", "User failed security question.")
                response_text = "I'm sorry, that is incorrect. For your security, I must end this call. Please visit your nearest branch."
                state.step = "finished"
                is_complete = True
            else:
                response_text = "That answer is incorrect. Please try again. " + case["securityQuestion"]

    # 3. Transaction Review -> Safe vs Fraud
    elif state.step == "transaction_review":
        case = get_case(state.current_user_name)
        case_data = case
        
        if "yes" in text or "i did" in text or "safe" in text:
            # Confirmed Safe
            update_case_status(state.current_user_name, "confirmed_safe", "Customer confirmed transaction.")
            response_text = "Thank you for confirming. We have marked this transaction as safe and unblocked your card. You may continue using it immediately. Have a good day."
            state.step = "finished"
            is_complete = True
            
        elif "no" in text or "didn't" in text or "fraud" in text:
            # Confirmed Fraud
            update_case_status(state.current_user_name, "confirmed_fraud", "Customer denied transaction.")
            response_text = (f"Understood. I have marked this as fraudulent. Your card ending in {case['cardEnding']} "
                             "has been blocked immediately to prevent further loss. We will issue a new card within 3-5 business days.")
            state.step = "finished"
            is_complete = True
        else:
            response_text = "I didn't catch that. Did you authorize this transaction? Please say Yes or No."

    return ChatResponse(
        message=response_text, 
        state=state, 
        case_details=case_data,
        is_complete=is_complete
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import json
import os
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Enable CORS so frontend can talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create orders directory if it doesn't exist
if not os.path.exists("orders"):
    os.makedirs("orders")

# --- Data Models ---
class OrderState(BaseModel):
    drinkType: Optional[str] = None
    size: Optional[str] = None
    milk: Optional[str] = None
    extras: List[str] = []
    name: Optional[str] = None

class ChatRequest(BaseModel):
    user_input: str
    current_state: OrderState

class ChatResponse(BaseModel):
    agent_response: str
    updated_state: OrderState
    is_complete: bool

# --- Logic ---

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    state = request.current_state
    text = request.user_input.lower()
    
    # 1. Entity Extraction (Simple Rule-Based for Demo)
    # In a real production app, you would use an LLM (like OpenAI) here.
    
    if "latte" in text: state.drinkType = "Latte"
    if "cappuccino" in text: state.drinkType = "Cappuccino"
    if "americano" in text: state.drinkType = "Americano"
    
    if "small" in text: state.size = "Small"
    if "medium" in text: state.size = "Medium"
    if "large" in text: state.size = "Large"
    
    if "oat" in text: state.milk = "Oat Milk"
    if "almond" in text: state.milk = "Almond Milk"
    if "whole" in text: state.milk = "Whole Milk"
    if "skim" in text: state.milk = "Skim Milk"
    
    if "sugar" in text and "sugar" not in state.extras: state.extras.append("Sugar")
    if "vanilla" in text and "vanilla" not in state.extras: state.extras.append("Vanilla Syrup")
    if "ice" in text and "ice" not in state.extras: state.extras.append("Extra Ice")

    # Simple logic to catch names (Assuming input is "My name is X" or just the name at the end)
    if state.drinkType and state.size and state.milk and not state.name:
        if "name is" in text:
            state.name = text.split("name is")[-1].strip().title()
        elif len(text.split()) == 1 and text not in ["yes", "no"]:
             state.name = text.title()

    # 2. Determine Next Question (The Persona)
    response_text = ""
    is_complete = False

    if not state.drinkType:
        response_text = "Welcome to Cafe Py! What drink can I get started for you today? We have Lattes, Cappuccinos, and Americanos."
    elif not state.size:
        response_text = f"Great choice. What size {state.drinkType} would you like? (Small, Medium, Large)"
    elif not state.milk:
        response_text = "And what kind of milk would you prefer? We have Whole, Skim, Oat, and Almond."
    elif not state.name:
        response_text = "Almost done! Who is this order for?"
    else:
        # All fields filled
        response_text = f"Thanks {state.name}! I have a {state.size} {state.drinkType} with {state.milk}"
        if state.extras:
            response_text += f" and {', '.join(state.extras)}"
        response_text += ". Creating your order ticket now!"
        is_complete = True
        
        # Save to JSON
        save_order(state)

    return ChatResponse(
        agent_response=response_text,
        updated_state=state,
        is_complete=is_complete
    )

def save_order(state: OrderState):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"orders/order_{state.name}_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump(state.dict(), f, indent=4)
    print(f"Order saved to {filename}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
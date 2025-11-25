from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
import os
from fastapi.middleware.cors import CORSMiddleware

# --- 1. Initialize the App (This fixes your previous error) ---
app = FastAPI()

# --- 2. Setup CORS (Allows Frontend to talk to Backend) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 3. Load Content ---
# This looks for content.json in the same folder as main.py
CURRICULUM = []
try:
    with open("content.json", "r") as f:
        CURRICULUM = json.load(f)
except FileNotFoundError:
    print("WARNING: content.json not found. Creating dummy data.")
    CURRICULUM = [{"title": "Error", "summary": "No content.json found", "sample_question": "N/A"}]

# --- 4. Data Models ---
class TutorState(BaseModel):
    mode: str = "setup"  # Options: setup, learn, quiz, teach_back
    topic_index: int = 0
    last_agent_message: Optional[str] = ""

class ChatRequest(BaseModel):
    user_input: str
    current_state: TutorState

class ChatResponse(BaseModel):
    agent_response: str
    updated_state: TutorState
    mode_display: str

# --- 5. Helper Functions ---
def get_topic(index):
    # Uses modulo to cycle back to the start if index exceeds list length
    safe_index = index % len(CURRICULUM)
    return CURRICULUM[safe_index]

def grade_teach_back(user_text, summary):
    """
    Simple keyword matching to simulate 'grading' the user.
    """
    # Extract words longer than 4 chars from summary to use as keywords
    keywords = [word.lower().strip(".,") for word in summary.split() if len(word) > 4]
    user_words = user_text.lower()
    
    # Count how many keywords the user mentioned
    match_count = sum(1 for k in keywords if k in user_words)
    
    if match_count >= 2:
        return "Excellent! You hit on the key concepts."
    elif match_count == 1:
        return "You're on the right track, but can you be a bit more specific?"
    else:
        return "That's a good start, but try to use some of the technical terms we discussed."

# --- 6. The Chat Endpoint ---
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    state = request.current_state
    text = request.user_input.lower()
    topic = get_topic(state.topic_index)
    
    response_text = ""
    mode_display = state.mode.upper()

    # --- Mode Switching Logic ---
    # Check if user wants to switch modes explicitly
    if "learn" in text and "mode" in text:
        state.mode = "learn"
        response_text = f"Switching to **Learn Mode**. Topic: {topic['title']}. \n\n{topic['summary']}"
        mode_display = "LEARN"
    
    elif "quiz" in text and "mode" in text:
        state.mode = "quiz"
        response_text = f"Switching to **Quiz Mode**. \n\nQuestion: {topic['sample_question']}"
        mode_display = "QUIZ"
    
    elif "teach" in text and "mode" in text:
        state.mode = "teach_back"
        response_text = f"Switching to **Teach-Back Mode**. \n\nOkay, I'm the student now. Please explain '{topic['title']}' to me in your own words."
        mode_display = "TEACH-BACK"

    elif "next topic" in text or "next" in text:
        state.topic_index += 1
        topic = get_topic(state.topic_index) # Update topic variable
        state.mode = "setup" # Reset to setup so they can choose mode for new topic
        response_text = f"Moved to next topic: **{topic['title']}**. \n\nWhich mode would you like? Learn, Quiz, or Teach-Back?"
        mode_display = "SETUP"

    # --- Conversation Logic per Mode ---
    else:
        if state.mode == "setup":
            response_text = f"We are currently on the topic: **{topic['title']}**. \n\nSay 'Learn Mode', 'Quiz Mode', or 'Teach Back Mode' to begin."
        
        elif state.mode == "learn":
            response_text = "Does that explanation make sense? We can move to 'Quiz Mode' to test you, or 'Next Topic' to continue."
            
        elif state.mode == "quiz":
            response_text = f"Good attempt! The core idea is: {topic['summary']}. \n\nReady for the next topic?"
            
        elif state.mode == "teach_back":
            feedback = grade_teach_back(text, topic['summary'])
            response_text = f"{feedback} \n\nWould you like to try 'Quiz Mode' or go to the 'Next Topic'?"

    return ChatResponse(
        agent_response=response_text,
        updated_state=state,
        mode_display=mode_display
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
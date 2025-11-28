from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import os
import google.generativeai as genai
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
API_KEY = os.getenv("GOOGLE_API_KEY")

# Determine if we use Real AI or Mock
USE_MOCK = True if not API_KEY else False

if not USE_MOCK:
    try:
        genai.configure(api_key=API_KEY)
        # --- FIX IS HERE: Changed 'gemini-pro' to 'gemini-1.5-flash' ---
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"API Setup Error: {e}")
        USE_MOCK = True

class Message(BaseModel):
    role: str
    content: str

class GameRequest(BaseModel):
    history: List[Message]
    user_input: str

class GameResponse(BaseModel):
    response: str
    updated_history: List[Message]

@app.post("/turn", response_model=GameResponse)
async def play_turn(req: GameRequest):
    history = req.history
    user_input = req.user_input
    user_lower = user_input.lower()
    ai_response = ""

    # 1. Start Game Logic
    if not history and user_input == "START":
        ai_response = (
            "CRITICAL ALERT. U.S.S. Aegis has crashed. "
            "You are trapped in the Medical Bay. The door is jammed. "
            "There is a ventilation shaft above you. What is your directive?"
        )
    
    # 2. Mock Logic (Fallback)
    elif USE_MOCK:
        if "door" in user_lower:
             ai_response = "The door is sealed tight. Sparks fly from the control panel. It is useless. You must find another way."
        elif "vent" in user_lower:
             ai_response = "You climb into the vents. It is dark. You hear skittering sounds ahead. Left or Right?"
        elif "left" in user_lower:
             ai_response = "You go Left. You find a stash of Emergency Flares. Suddenly, an Alien Drone blocks your path! It is charging a laser. Do you ATTACK or RUN?"
        elif "right" in user_lower:
             ai_response = "You go Right. It is a dead end. You hear the drone coming closer. You must go back."
        elif "attack" in user_lower or "flare" in user_lower:
             ai_response = "VICTORY! You light the flare and throw it at the drone. The heat sensor overloads and it explodes! The path to the Escape Pod is clear. MISSION ACCOMPLISHED."
        elif "run" in user_lower:
             ai_response = "GAME OVER. You try to run, but the drone is faster. The laser hits you. Life support terminated."
        else:
             ai_response = "Command Unclear. We are running out of time. Restate action."

    # 3. Real AI Logic
    else:
        try:
            # Construct a prompt with history
            full_prompt = "You are A.R.E.S., a ship AI. The ship crashed on Mars. Guide the user (Commander) to escape. Be robotic, atmospheric, and urgent. Keep responses short (max 2 sentences).\n\n"
            for msg in history:
                full_prompt += f"{msg.role.upper()}: {msg.content}\n"
            full_prompt += f"USER: {user_input}\nA.R.E.S.:"

            response = model.generate_content(full_prompt)
            ai_response = response.text
        except Exception as e:
            print(f"--------------- API ERROR DETAILS: {e} ---------------")
            ai_response = "SYSTEM ERROR: Neural Link Severed. (API Error - Check Terminal)"

    # Update History
    history.append(Message(role="user", content=user_input))
    history.append(Message(role="model", content=ai_response))
    
    return GameResponse(response=ai_response, updated_history=history)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
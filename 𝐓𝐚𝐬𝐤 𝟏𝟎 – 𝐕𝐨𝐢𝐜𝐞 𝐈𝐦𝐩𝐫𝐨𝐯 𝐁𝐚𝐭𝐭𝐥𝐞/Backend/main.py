from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import os
import random
import google.generativeai as genai
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from scenarios import SCENARIOS

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- AI CONFIGURATION ---
API_KEY = os.getenv("GOOGLE_API_KEY")
USE_MOCK = True if not API_KEY else False

if not USE_MOCK:
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
    except:
        USE_MOCK = True

# --- GAME STATE MODEL ---
class GameState(BaseModel):
    player_name: str
    current_round: int = 0
    max_rounds: int = 3
    current_scenario: str = ""
    history: List[str] = [] # Stores summary of performance
    phase: str = "intro" # intro, playing, feedback, summary

class TurnRequest(BaseModel):
    user_input: str
    state: GameState

class TurnResponse(BaseModel):
    host_speech: str
    state: GameState
    is_game_over: bool

# --- AI PERSONA ---
HOST_PERSONA = """
You are 'Zap Rogers', the high-energy, witty, slightly sarcastic host of the game show 'IMPROV ROYALE'.
Your job is to judge the player's improv skills.
- If they are funny/creative, praise them enthusiastically.
- If they are short/boring, gently roast them or tease them.
- Keep responses short (2-3 sentences max).
- NEVER break character.
"""

# --- HELPERS ---
def generate_reaction(scenario, user_input):
    if USE_MOCK:
        return "Haha! That was... interesting! Let's see what else you've got."
    
    try:
        prompt = f"{HOST_PERSONA}\n\nScenario: {scenario}\nPlayer said: \"{user_input}\"\n\nGive a reaction to the player's performance. Be specific about what they said."
        response = model.generate_content(prompt)
        return response.text
    except:
        return "Wow! I didn't expect that! Moving on!"

def generate_summary(history):
    if USE_MOCK:
        return "You were great! Thanks for playing!"
    
    try:
        prompt = f"{HOST_PERSONA}\n\nHere is a summary of the player's rounds: {history}\n\nGive a final verdict on what kind of improviser they are. Be dramatic."
        response = model.generate_content(prompt)
        return response.text
    except:
        return "That's a wrap folks! You survived Improv Royale!"

# --- ENDPOINT ---

@app.post("/turn", response_model=TurnResponse)
async def play_turn(req: TurnRequest):
    state = req.state
    user_input = req.user_input
    response_text = ""
    is_game_over = False

    # PHASE 1: INTRO (Start Button Clicked)
    if state.phase == "intro":
        state.player_name = user_input if user_input else "Contestant"
        response_text = (f"Welcome to IMPROV ROYALE! I'm your host, Zap Rogers! "
                         f"Hello {state.player_name}! We're going to do {state.max_rounds} rounds of improv. "
                         "I'll give you a scenario, you act it out. Let's start!")
        
        # Prepare Round 1
        state.current_round = 1
        state.current_scenario = random.choice(SCENARIOS)
        response_text += f" Round 1: {state.current_scenario}"
        state.phase = "playing"

    # PHASE 2: PLAYING (User just spoke their improv line)
    elif state.phase == "playing":
        # 1. Generate Reaction to what user just said
        reaction = generate_reaction(state.current_scenario, user_input)
        
        # 2. Store history
        state.history.append(f"Round {state.current_round}: {user_input}")
        
        # 3. Check if game over
        if state.current_round >= state.max_rounds:
            state.phase = "summary"
            final_summary = generate_summary(state.history)
            response_text = f"{reaction} ... Alright, that was the final round! {final_summary}"
            is_game_over = True
        else:
            # 4. Set up next round
            state.current_round += 1
            state.current_scenario = random.choice(SCENARIOS) # Pick new scenario
            response_text = f"{reaction} ... Okay! Moving on. Round {state.current_round}: {state.current_scenario}"

    return TurnResponse(
        host_speech=response_text,
        state=state,
        is_game_over=is_game_over
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
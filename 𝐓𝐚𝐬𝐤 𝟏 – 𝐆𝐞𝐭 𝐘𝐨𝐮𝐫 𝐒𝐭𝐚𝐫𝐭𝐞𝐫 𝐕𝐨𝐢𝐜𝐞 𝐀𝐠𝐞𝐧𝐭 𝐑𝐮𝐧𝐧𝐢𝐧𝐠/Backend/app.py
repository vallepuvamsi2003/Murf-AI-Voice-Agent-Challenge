from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import os

app = Flask(__name__)
CORS(app)

# --- Configuration ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDyNaxaGDLgPcJOEC12z8Xdc7L5BnbO6BU")
genai.configure(api_key=GEMINI_API_KEY)

@app.route('/')
def home():
    return "Voice Agent Backend is Running!"

@app.route('/voice-chat', methods=['POST'])
def voice_chat():
    try:
        data = request.get_json()
        user_text = data.get('text')

        if not user_text:
            return jsonify({"error": "No text provided"}), 400

        print(f"User said: {user_text}")

        # --- FIX 1: Use a more stable model ---
        # 'gemini-2.0-flash' is generally more reliable than the 2.5 preview
        model = genai.GenerativeModel('gemini-2.0-flash')

        # --- FIX 2: Increase Token Limit ---
        # Sometimes '100' is too tight and causes the 'finish_reason: 2' error.
        # We increased it to 300.
        response = model.generate_content(
            user_text,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=300, 
                temperature=0.7
            )
        )

        # --- FIX 3: Safer Text Extraction ---
        # Instead of crashing if response.text is empty, we check for it.
        agent_text = "I'm sorry, I couldn't generate a response."
        
        try:
            if response.text:
                agent_text = response.text
        except ValueError:
            # This catches the specific error you saw
            print(f"⚠️ Response blocked or empty. Finish Reason: {response.candidates[0].finish_reason}")
            agent_text = "I heard you, but I couldn't think of a valid response."

        print(f"🤖 Agent: {agent_text}")

        return jsonify({
            "response_text": agent_text
        })

    except Exception as e:
        print(f"❌ Server Error: {e}")
        return jsonify({
            "response_text": "I am having trouble connecting. Please try again."
        }), 500

if __name__ == '__main__':
    print("Starting server on port 5000...")
    print("Using Model: gemini-2.0-flash")
    app.run(debug=True, port=5000)
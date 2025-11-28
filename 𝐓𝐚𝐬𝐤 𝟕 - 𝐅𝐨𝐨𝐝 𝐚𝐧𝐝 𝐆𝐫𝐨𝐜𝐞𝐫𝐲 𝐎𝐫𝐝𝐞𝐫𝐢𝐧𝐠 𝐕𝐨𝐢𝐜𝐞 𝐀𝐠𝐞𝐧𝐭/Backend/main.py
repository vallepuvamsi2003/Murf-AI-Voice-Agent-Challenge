from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Optional
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

if not os.path.exists("orders"):
    os.makedirs("orders")

# --- Load Catalog ---
with open("catalog.json", "r") as f:
    CATALOG = json.load(f)

# --- Recipe/Bundle Definitions ---
RECIPES = {
    "sandwich": ["bread", "butter", "cheese", "tomato"],
    "pasta": ["pasta", "sauce", "cheese"],
    "party": ["coke", "chips", "chocolate"]
}

# --- Models ---
class CartItem(BaseModel):
    id: str
    name: str
    price: float
    quantity: int

class OrderState(BaseModel):
    step: str = "shopping" # shopping, confirmed, finished
    cart: List[CartItem] = []
    total: float = 0.0

class ChatRequest(BaseModel):
    user_input: str
    state: OrderState

class ChatResponse(BaseModel):
    message: str
    state: OrderState
    is_complete: bool

# --- Helpers ---
def find_item_by_text(text: str):
    """Scans catalog for matches in user text."""
    matches = []
    text = text.lower()
    for item in CATALOG:
        for kw in item["keywords"]:
            if kw in text:
                matches.append(item)
                break # Found this item, move to next catalog item
    return matches

def update_cart(cart: List[CartItem], item_data: dict, qty: int = 1, operation: str = "add"):
    """Adds or Removes items from cart."""
    # Check if item exists
    existing = next((i for i in cart if i.id == item_data["id"]), None)
    
    if operation == "add":
        if existing:
            existing.quantity += qty
        else:
            cart.append(CartItem(
                id=item_data["id"], 
                name=item_data["name"], 
                price=item_data["price"], 
                quantity=qty
            ))
    elif operation == "remove":
        if existing:
            existing.quantity -= qty
            if existing.quantity <= 0:
                cart.remove(existing)
    
    return cart

def calculate_total(cart):
    return sum(item.price * item.quantity for item in cart)

def save_order(cart, total):
    order_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": total,
        "items": [item.dict() for item in cart],
        "status": "Order Placed"
    }
    filename = f"orders/order_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w") as f:
        json.dump(order_data, f, indent=4)
    return filename

# --- Main Logic ---

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    text = req.user_input.lower().strip()
    state = req.state
    response_text = ""
    is_complete = False

    # 1. Check for Checkout / Finish
    if any(w in text for w in ["place order", "checkout", "done", "that's all", "finish"]):
        if not state.cart:
            response_text = "Your cart is empty! Add some snacks or groceries first."
        else:
            filename = save_order(state.cart, state.total)
            response_text = (f"Order placed successfully! Total amount is ₹{state.total}. "
                             f"I've saved your receipt to {filename}. Delivering in 10 minutes!")
            state.step = "finished"
            is_complete = True
        
        return ChatResponse(message=response_text, state=state, is_complete=is_complete)

    # 2. Check for "Ingredients for X" (Recipes)
    recipe_found = False
    for recipe_name, ingredients in RECIPES.items():
        if recipe_name in text and ("ingredients" in text or "make" in text or "recipe" in text):
            # Add all ingredients
            for item_id in ingredients:
                # Find item object from catalog
                catalog_item = next((i for i in CATALOG if i["id"] == item_id), None)
                if catalog_item:
                    state.cart = update_cart(state.cart, catalog_item, 1, "add")
            
            recipe_found = True
            response_text = f"I've added the ingredients for {recipe_name} ({', '.join(ingredients)}) to your cart. Anything else?"
            break
    
    if recipe_found:
        state.total = calculate_total(state.cart)
        return ChatResponse(message=response_text, state=state, is_complete=False)

    # 3. Check for Remove Intent
    if "remove" in text or "delete" in text:
        detected_items = find_item_by_text(text)
        if not detected_items:
            response_text = "I'm not sure which item you want to remove."
        else:
            names = []
            for item in detected_items:
                state.cart = update_cart(state.cart, item, 1, "remove")
                names.append(item["name"])
            response_text = f"Removed {', '.join(names)} from your cart."

    # 4. Check for Add Intent (Default)
    else:
        detected_items = find_item_by_text(text)
        
        if detected_items:
            names = []
            for item in detected_items:
                # Simple quantity check (very basic: looks for numbers in text, defaults to 1)
                qty = 1
                for word in text.split():
                    if word.isdigit():
                        qty = int(word)
                        break
                
                state.cart = update_cart(state.cart, item, qty, "add")
                names.append(f"{qty} x {item['name']}")
            
            response_text = f"Added {', '.join(names)}."
        
        # 5. Handle "What's in my cart?"
        elif "cart" in text or "list" in text:
            if not state.cart:
                response_text = "Your cart is empty."
            else:
                items_list = [f"{i.quantity} {i.name}" for i in state.cart]
                response_text = f"You have: {', '.join(items_list)}. Total is ₹{state.total}."
        
        # 6. Greeting / Fallback
        elif not text and state.step == "shopping":
            response_text = "Hey! I'm ZeptoBot. I can get you groceries in 10 minutes. Try asking for 'Milk and Eggs' or 'Ingredients for a Sandwich'."
        
        elif not detected_items:
            response_text = "Sorry, we don't have that item in stock right now. Try asking for Milk, Bread, Chips, or Pasta."

    # Update Total
    state.total = calculate_total(state.cart)

    return ChatResponse(message=response_text, state=state, is_complete=is_complete)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
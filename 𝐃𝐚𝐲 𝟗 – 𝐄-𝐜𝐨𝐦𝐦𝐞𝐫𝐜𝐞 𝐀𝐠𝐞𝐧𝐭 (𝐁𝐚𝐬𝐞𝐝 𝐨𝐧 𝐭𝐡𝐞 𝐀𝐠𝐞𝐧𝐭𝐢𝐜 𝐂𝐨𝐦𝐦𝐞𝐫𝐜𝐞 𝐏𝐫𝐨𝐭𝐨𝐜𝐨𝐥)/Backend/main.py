from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
import uuid
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from catalog import PRODUCTS

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ORDER_FILE = "orders.json"
CART = [] 

# --- MODELS ---
class LineItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    currency: str

class Order(BaseModel):
    order_id: str
    items: List[LineItem]
    total_amount: float
    currency: str
    status: str
    created_at: str

class AgentRequest(BaseModel):
    user_input: str

class AgentResponse(BaseModel):
    voice_response: str
    ui_view: str 
    data: Any

# --- MERCHANT LAYER ---

def list_products(query: str = None):
    if not query: return PRODUCTS
    query = query.lower()
    return [p for p in PRODUCTS if query in p["name"].lower() or query in p["category"] or any(tag in query for tag in p["tags"])]

def get_product_by_name(query: str):
    candidates = list_products(query)
    return candidates[0] if candidates else None

def add_to_cart_logic(product_query: str, quantity: int = 1):
    product = get_product_by_name(product_query)
    if not product:
        return None, "not_found"
    
    for item in CART:
        if item["product_id"] == product["id"]:
            item["quantity"] += quantity
            return item, "updated"

    item = {
        "product_id": product["id"],
        "product_name": product["name"],
        "quantity": quantity,
        "unit_price": product["price"],
        "currency": product["currency"],
        "image": product["image"]
    }
    CART.append(item)
    return item, "added"

def checkout_cart():
    if not CART:
        return None, "empty"
    
    total = sum(item["quantity"] * item["unit_price"] for item in CART)
    currency = CART[0]["currency"]
    
    line_items = [LineItem(**item) for item in CART]
    
    new_order = Order(
        order_id=f"ord_{str(uuid.uuid4())[:8]}",
        items=line_items,
        total_amount=total,
        currency=currency,
        status="CONFIRMED",
        created_at=datetime.now().isoformat()
    )
    
    save_order_to_db(new_order)
    CART.clear() 
    return new_order, "success"

def get_last_order():
    if not os.path.exists(ORDER_FILE): return None
    try:
        with open(ORDER_FILE, "r") as f:
            orders = json.load(f)
            return orders[-1] if orders else None
    except: return None

def save_order_to_db(order: Order):
    orders = []
    if os.path.exists(ORDER_FILE):
        try:
            with open(ORDER_FILE, "r") as f: orders = json.load(f)
        except: pass
    orders.append(order.dict())
    with open(ORDER_FILE, "w") as f: json.dump(orders, f, indent=2)

# --- AGENT LAYER ---

@app.post("/chat", response_model=AgentResponse)
async def chat_handler(req: AgentRequest):
    text = req.user_input.lower().strip()
    
    # --- PRIORITY 1: CHECKOUT / BUY CART ---
    # Moved to top so it catches "Buy ... cart" before Add logic sees it.
    is_checkout = False
    
    # Check for explicit checkout words
    if any(w in text for w in ["checkout", "place order", "finish shopping"]):
        is_checkout = True
    
    # Check for "Buy" + "Cart" (e.g., "Buy the products in cart")
    elif "buy" in text and "cart" in text:
        is_checkout = True
        
    if is_checkout:
        order, status = checkout_cart()
        if status == "empty":
            return AgentResponse(voice_response="Your cart is empty. Add something first.", ui_view="none", data=None)
        
        # Generate Summary
        item_names = [f"{item.quantity} {item.product_name}" for item in order.items]
        if len(item_names) > 1:
            items_summary = ", ".join(item_names[:-1]) + " and " + item_names[-1]
        else:
            items_summary = item_names[0]

        msg = f"Order confirmed! You have purchased {items_summary}. The total is {order.total_amount} {order.currency}."
        return AgentResponse(voice_response=msg, ui_view="order_success", data=order)

    # --- PRIORITY 2: VIEW HISTORY ---
    if any(w in text for w in ["history", "last order", "previous order"]):
        order = get_last_order()
        if order:
            msg = f"Your last order was for {len(order['items'])} items totaling {order['total_amount']} {order['currency']}."
            return AgentResponse(voice_response=msg, ui_view="history", data=order)
        return AgentResponse(voice_response="No history found.", ui_view="none", data=None)

    # --- PRIORITY 3: VIEW CART ---
    if "what is in" in text or text == "show cart" or text == "view cart":
        if not CART:
            return AgentResponse(voice_response="Your cart is empty.", ui_view="cart", data={"cart": [], "total": 0})
        
        total = sum(i['quantity']*i['unit_price'] for i in CART)
        msg = f"You have {len(CART)} items in your cart. Total is {total} INR."
        return AgentResponse(voice_response=msg, ui_view="cart", data={"cart": CART, "total": total})

    # --- PRIORITY 4: ADD TO CART ---
    if any(w in text for w in ["add", "cart"]) and not "show" in text:
        clean_text = text.replace("add", "").replace("to cart", "").replace("the", "").replace("a", "").strip()
        item, status = add_to_cart_logic(clean_text)
        
        if status == "not_found":
            return AgentResponse(voice_response=f"I couldn't find '{clean_text}'.", ui_view="none", data=None)
        
        msg = f"Added {item['product_name']} to your cart."
        return AgentResponse(voice_response=msg, ui_view="cart", data={"cart": CART, "total": sum(i['quantity']*i['unit_price'] for i in CART)})

    # --- PRIORITY 5: DIRECT BUY (Single Item) ---
    if "buy" in text:
        clean_text = text.replace("buy", "").replace("order", "").strip()
        item, status = add_to_cart_logic(clean_text)
        if status == "not_found":
             return AgentResponse(voice_response="Product not found.", ui_view="none", data=None)
        
        order, _ = checkout_cart()
        msg = f"Direct purchase successful. You bought {item['product_name']}."
        return AgentResponse(voice_response=msg, ui_view="order_success", data=order)

    # --- PRIORITY 6: BROWSE (Default) ---
    if "catalog" in text or text == "":
        products = list_products("")
        msg = f"Showing full catalog."
        return AgentResponse(voice_response=msg, ui_view="catalog", data=products)

    query = text.replace("show me", "").replace("search", "").strip()
    products = list_products(query)
    if not products:
        return AgentResponse(voice_response="No items found.", ui_view="none", data=None)
    
    msg = f"Found {len(products)} items."
    return AgentResponse(voice_response=msg, ui_view="catalog", data=products)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
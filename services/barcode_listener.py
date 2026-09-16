import keyboard
import time
import threading
from plyer import notification
import json
import os

SHARED_STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "shared_state.json")

def load_state():
    try:
        with open(SHARED_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"barcode_rules": {}, "service_rules": {}, "cart": {"items": {}, "services": {}, "total_item_count": 0}}

def save_state(state):
    try:
        with open(SHARED_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving state: {e}")

buffer = ""
last_time = time.time()

def show_notification(title, msg):
    try:
        notification.notify(
            title=title,
            message=msg,
            app_name="FoodBank ERP",
            timeout=3
        )
    except Exception as e:
        print(f"Notification error: {e}")

def process_barcode(barcode):
    state = load_state()
    rules = state.get("barcode_rules", {})
    services = state.get("service_rules", {})
    cart = state.get("cart", {"items": {}, "services": {}, "total_item_count": 0})
    
    # 1. 서비스 물품 확인
    if barcode in services:
        svc_name = services[barcode]["service_name"]
        req_qty = services[barcode]["required_qty"]
        current_svc_qty = cart["services"].get(svc_name, 0)
        
        if current_svc_qty < req_qty:
            current_svc_qty += 1
            cart["services"][svc_name] = current_svc_qty
            state["cart"] = cart
            save_state(state)
            show_notification(f"🎁 서비스 스캔: {svc_name}", f"({current_svc_qty}/{req_qty}) 스캔 완료")
        else:
            show_notification(f"❌ 초과: {svc_name}", f"이미 할당량({req_qty}개)을 모두 채웠습니다.")
        return

    # 2. 일반 묶음 품목 확인
    if barcode in rules:
        product = rules[barcode]["product"]
        item_group = rules[barcode]["item"]
        req_qty = rules[barcode]["required_qty"]
        
        item_cart = cart["items"].setdefault(item_group, {"count": 0, "full_items": 0})
        
        # 5품목 초과 사전 검사
        if cart["total_item_count"] >= 5 and item_cart["count"] % req_qty == 0:
             show_notification("❌ [제한 초과]", "전체 5품목을 이미 모두 채웠습니다.")
             return
        
        # 품목 수량 1 증가
        item_cart["count"] += 1
        
        # N개가 차면 1품목(full_item) 완성
        new_full_items = item_cart["count"] // req_qty
        remainder = item_cart["count"] % req_qty
        
        if new_full_items > item_cart["full_items"]:
            # 품목이 새로 1개 완성됨
            item_cart["full_items"] = new_full_items
            cart["total_item_count"] += 1
            
            show_notification(
                f"✅ 품목 완성: {item_group}",
                f"({product} {req_qty}개 스캔됨) 총 {cart['total_item_count']}/5 품목"
            )
        else:
            show_notification(
                f"📦 부분 스캔: {product}",
                f"{remainder}/{req_qty} 개 스캔 (1품목 완성을 위해 {req_qty - remainder}개 더 필요)"
            )
            
        state["cart"] = cart
        save_state(state)
        return

    # 3. 등록되지 않은 바코드
    # show_notification("⚠️ 미등록 바코드", f"[{barcode}] 등록된 규칙이 없습니다.")
    pass

def on_key_event(e):
    global buffer, last_time
    if e.event_type == keyboard.KEY_DOWN:
        current_time = time.time()
        # 바코드 스캐너는 매우 짧은 간격으로 키를 입력함
        if current_time - last_time > 0.05:
            buffer = ""
            
        last_time = current_time
        
        if e.name == "enter":
            if len(buffer) > 3: # 최소 4자리 이상을 바코드로 간주
                # 별도 스레드에서 처리하여 후킹 차단 방지
                threading.Thread(target=process_barcode, args=(buffer,)).start()
            buffer = ""
        elif len(e.name) == 1:
            buffer += e.name

print("바코드 리스너가 시작되었습니다. 전역(백그라운드)에서 입력을 대기합니다...")
keyboard.hook(on_key_event)
keyboard.wait()

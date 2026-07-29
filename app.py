"""
مساعد - بوت واتساب لتوزيع طلبات الصيانة على العمال
"""

import os
import json
import time
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client

app = Flask(__name__)

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID else None

with open(os.path.join(os.path.dirname(__file__), "workers.json"), "r", encoding="utf-8") as f:
    WORKERS = json.load(f)

customer_state = {}
worker_pending = {}


def send_whatsapp(to_number, body):
    if not client:
        print(f"[محاكاة] إلى {to_number}: {body}")
        return
    client.messages.create(from_=TWILIO_WHATSAPP_NUMBER, to=to_number, body=body)


def services_list_text():
    return "\n".join(f"- {s}" for s in WORKERS.keys())


@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    from_number = request.values.get("From", "")

    resp = MessagingResponse()

    if from_number in worker_pending:
        pending = worker_pending.pop(from_number)
        customer_phone = pending["customer_phone"]
        state = customer_state.get(customer_phone)

        if state and state.get("request_id") == pending["request_id"]:
            worker_name = pending["worker_name"]
            state["responses"].append({"name": worker_name, "phone": from_number, "reply": incoming_msg})
            resp.message("تم استلام ردك ✅ راح يوصل للعميل.")
            send_customer_update(customer_phone, state)

        return str(resp)

    state = customer_state.get(from_number)

    if not state:
        customer_state[from_number] = {"stage": "awaiting_service", "responses": []}
        resp.message(
            "أهلاً بك في مساعد 👋\n"
            "وش نوع الخدمة اللي تحتاجها؟ اكتب اسم الخدمة من

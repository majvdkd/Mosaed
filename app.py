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
        print("simulated message to " + to_number)
        return
    client.messages.create(from_=TWILIO_WHATSAPP_NUMBER, to=to_number, body=body)


def services_list_text():
    lines = []
    for s in WORKERS.keys():
        lines.append("- " + s)
    return "\n".join(lines)


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
            resp.message("تم استلام ردك، راح يوصل للعميل")
            send_customer_update(customer_phone, state)

        return str(resp)

    state = customer_state.get(from_number)

    if not state:
        customer_state[from_number] = {"stage": "awaiting_service", "responses": []}
        greeting = "أهلاً بك في مساعد. وش نوع الخدمة اللي تحتاجها؟ اكتب اسم الخدمة من القائمة:"
        resp.message(greeting + "\n\n" + services_list_text())
        return str(resp)

    if state["stage"] == "awaiting_service":
        matched_service = None
        for service in WORKERS:
            if service in incoming_msg or incoming_msg in service:
                matched_service = service
                break

        if not matched_service:
            msg = "ما قدرت افهم نوع الخدمة، تاكد تكتب الاسم بالضبط من القائمة:"
            resp.message(msg + "\n\n" + services_list_text())
            return str(resp)

        request_id = from_number + "-" + str(int(time.time()))
        state.update({
            "stage": "waiting_workers",
            "service": matched_service,
            "request_id": request_id,
            "responses": [],
        })

        workers_for_service = WORKERS.get(matched_service, [])
        if not workers_for_service:
            resp.message("عذرا، ما فيه عمال متاحين حاليا لخدمة " + matched_service)
            return str(resp)

        for worker in workers_for_service:
            worker_pending[worker["phone"]] = {
                "customer_phone": from_number,
                "request_id": request_id,
                "worker_name": worker["name"],
            }
            msg_to_worker = "طلب جديد من مساعد. نوع الخدمة: " + matched_service + ". رجاء رد بسعرك ووقت وصولك."
            send_whatsapp(worker["phone"], msg_to_worker)

        resp.message("تم ارسال طلبك لعمال " + matched_service + " المتاحين. بمجرد ما يردون بنرسل لك القائمة.")
        return str(resp)

    if state["stage"] == "waiting_workers":
        resp.message("طلبك قيد المعالجة، بنرسل لك تحديث بمجرد وصول ردود العمال")
        return str(resp)

    return str(resp)


def send_customer_update(customer_phone, state):
    lines = ["عمال " + state["service"] + " اللي ردوا:"]
    for r in state["responses"]:
        worker_number = r["phone"].replace("whatsapp:", "").replace("+", "")
        wa_link = "https://wa.me/" + worker_number
        lines.append(r["name"] + ": " + r["reply"] + " - " + wa_link)
    send_whatsapp(customer_phone, "\n".join(lines))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

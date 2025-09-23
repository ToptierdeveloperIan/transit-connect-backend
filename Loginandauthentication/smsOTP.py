import requests
from decouple import config

def send_sms_otp(otp, phoneno):

    url = "https://sms.textsms.co.ke/api/services/sendsms/"
    payload = {
        "apikey": config("TEXT_SMS_API_KEY"),
        "partnerID": "14555",
        "message": f"Your NEXA verification code is {otp}. Please do not share this code. It will expire in 10 minutes.",
        "shortcode": "TEXTSMS",
        "mobile": phoneno,
    }

    # Try form-data first, most gateways expect this
    response = requests.post(url, data=payload)

    print("Status Code:", response.status_code)
    try:
        print(response.json())
    except Exception:
        print("Raw response:", response.text)

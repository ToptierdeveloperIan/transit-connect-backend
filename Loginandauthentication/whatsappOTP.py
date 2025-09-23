import requests
from decouple import config


def normalize_phone_number(number: str, default_country_code: str = "254") -> str:
    """
    Converts a local or international phone number to international format.

    Examples:
    "0769640633"      -> "254769640633"
    "+254769640633"   -> "254769640633"
    "254769640633"    -> "254769640633"

    Args:
        number (str): The phone number input from the user.
        default_country_code (str): The country code to use if the number is local.

    Returns:
        str: Normalized phone number in international format.
    """
    # Remove spaces, dashes, parentheses
    number = number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    # Remove leading "+"
    if number.startswith("+"):
        number = number[1:]

    # If number starts with 0 (local format), replace it with country code
    if number.startswith("0"):
        number = default_country_code + number[1:]

    return number


def sendOTP(ReceiverNo,otp):


    url = "https://graph.facebook.com/v18.0/797091776816113/messages"

    access_token=config("whatsapp_access_token")


    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    body = {
        "messaging_product": "whatsapp",
        "to": ReceiverNo,
        "type": "text",
        "text": {
            "body": f"Your OTP is: {otp}"
        }
    }

    try:
        response = requests.post(url, headers=headers, json=body)
        if response.status_code == 200:
            print("OTP sent successfully!")
            return {"status": "success", "otp": otp}
        else:
            print("Failed to send OTP:", response.text)
            return {"status": "failed", "response": response.text}
    except Exception as e:
        print("Error occurred:", str(e))
        return {"status": "error", "error": str(e)}

# Example usage:
# sendOTP("2547XXXXXXXX")  # Replace with test number from your WhatsApp Test Account

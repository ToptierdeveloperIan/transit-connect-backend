import base64
import requests
from datetime import datetime
from decouple import config


# Toggle between sandbox and production by changing these URLs
MPESA_AUTH_URL = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
MPESA_STK_PUSH_URL = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
MPESA_B2C_URL = 'https://sandbox.safaricom.co.ke/mpesa/b2c/v3/paymentrequest'


def _cfg():
    """Load M-Pesa credentials lazily so missing env vars don't break startup."""
    return {
        'consumer_key': config('MPESA_CONSUMER_KEY'),
        'consumer_secret': config('MPESA_CONSUMER_SECRET'),
        'shortcode': config('MPESA_SHORTCODE'),
        'passkey': config('MPESA_PASSKEY'),
        'initiator_name': config('MPESA_INITIATOR_NAME'),
        # Security credential: your Initiator password encrypted with Safaricom's
        # public certificate. Generate it from the Daraja portal under Test Credentials.
        'security_credential': config('MPESA_SECURITY_CREDENTIAL'),
        'b2c_shortcode': config('MPESA_B2C_SHORTCODE'),
        # Callback/result URLs — must be publicly reachable (use ngrok during development)
        'stk_callback_url': config('MPESA_STK_CALLBACK_URL'),
        'b2c_result_url': config('MPESA_B2C_RESULT_URL'),
        'b2c_timeout_url': config('MPESA_B2C_TIMEOUT_URL'),
    }


def get_access_token():
    """Fetch a short-lived OAuth token from Daraja."""
    cfg = _cfg()
    response = requests.get(
        MPESA_AUTH_URL,
        auth=(cfg['consumer_key'], cfg['consumer_secret']),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()['access_token']


def _stk_password_and_timestamp():
    """Return (base64_password, timestamp) for an STK Push request."""
    cfg = _cfg()
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    raw = cfg['shortcode'] + cfg['passkey'] + timestamp
    password = base64.b64encode(raw.encode()).decode('utf-8')
    return password, timestamp


def initiate_stk_push(phone_number, amount, account_reference, transaction_desc):
    """
    Trigger an STK Push (Lipa Na M-Pesa Online) request.

    Args:
        phone_number    : Customer phone in 2547XXXXXXXX format.
        amount          : Amount to charge (will be rounded to nearest integer).
        account_reference: Short label shown on the customer's M-Pesa confirmation (e.g. booking ID).
        transaction_desc: Description shown in the M-Pesa prompt.

    Returns:
        dict: Raw Daraja API response.
              On success → contains 'CheckoutRequestID' and 'MerchantRequestID'.
              On failure → contains 'errorCode' and 'errorMessage'.
    """
    cfg = _cfg()
    access_token = get_access_token()
    password, timestamp = _stk_password_and_timestamp()

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }

    payload = {
        'BusinessShortCode': cfg['shortcode'],
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': 'CustomerPayBillOnline',
        'Amount': int(amount),
        'PartyA': phone_number,
        'PartyB': cfg['shortcode'],
        'PhoneNumber': phone_number,
        'CallBackURL': cfg['stk_callback_url'],
        'AccountReference': account_reference,
        'TransactionDesc': transaction_desc,
    }

    response = requests.post(MPESA_STK_PUSH_URL, json=payload, headers=headers, timeout=15)
    return response.json()


def initiate_b2c(phone_number, amount, command_id='BusinessPayment', remarks='Payment', occasion=''):
    """
    Send money from the business to a customer/driver phone (B2C).

    Args:
        phone_number : Recipient phone in 2547XXXXXXXX format.
        amount       : Amount to send.
        command_id   : 'BusinessPayment' | 'SalaryPayment' | 'PromotionPayment'.
        remarks      : Short description of the transaction (max 100 chars).
        occasion     : Optional additional info.

    Returns:
        dict: Raw Daraja API response.
              On success → contains 'ConversationID' and 'OriginatorConversationID'.
              On failure → contains 'errorCode' and 'errorMessage'.
    """
    cfg = _cfg()
    access_token = get_access_token()

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }

    payload = {
        'InitiatorName': cfg['initiator_name'],
        'SecurityCredential': cfg['security_credential'],
        'CommandID': command_id,
        'Amount': int(amount),
        'PartyA': cfg['b2c_shortcode'],
        'PartyB': phone_number,
        'Remarks': remarks[:100],
        'QueueTimeOutURL': cfg['b2c_timeout_url'],
        'ResultURL': cfg['b2c_result_url'],
        'Occasion': occasion,
    }

    response = requests.post(MPESA_B2C_URL, json=payload, headers=headers, timeout=15)
    return response.json()

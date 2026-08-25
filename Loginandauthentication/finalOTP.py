import smtplib

from .whatsappOTP import  normalize_phone_number
from random import randint
import redis, json
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os
from .emailOTP import API_KEY
from.smsOTP import send_sms_otp

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

class OTP:

    redis = r  # Redis instance

    @staticmethod
    def GenerateOTP():
        return str(randint(100000, 999999))

    @staticmethod
    def send_otp(channel, phone_number, otp):
        if channel == "sms":
            send_sms_otp(otp, phone_number)
            print(f"Sending OTP {otp} to {phone_number} via SMS")


        else:
            print(f"Unknown channel {channel}, OTP: {otp}")

    @staticmethod
    def resend_otp(phone_number):

            """Resend OTP respecting the original verification channel"""
            phone_number = normalize_phone_number(phone_number)
            key = f"user_otp:{phone_number}"

            stored_data = OTP.redis.get(key)
            if not stored_data:
                return {"success": False, "message": "No existing OTP request found."}

            user_data = json.loads(stored_data)
            channel = user_data.get('verification_channel', 'sms')
            otp = OTP.GenerateOTP()
            user_data['otp'] = otp  # update OTP in Redis

            # Resend via the correct channel
            if channel == "Email":
                email = user_data.get('email')
                if not email:
                    return {"success": False, "message": "Email not found for resending OTP"}
                OTP.send_email_otp(email, otp)
            else:
                OTP.send_otp(channel, phone_number, otp)

            # Save updated OTP back to Redis
            r.set(key, json.dumps(user_data), ex=300)
            return {"success": True, "message": "OTP resent successfully."}

    @staticmethod
    def send_email_otp(email, otp):
        message = Mail(
            from_email='Nexasupport@NexaKenya.co.ke',
            to_emails=email,
            subject='Your Nexa OTP Code',
            html_content=f'<p>Your OTP code is: <strong>{otp}</strong></p>'
        )
        sg = SendGridAPIClient(API_KEY)
        response = sg.send(message)
        print(f"Sent OTP {otp} to {email} via Email. Status: {response.status_code}")

    @staticmethod
    def android_generate_and_send_otp(phone_number, first_name=None, second_name=None):
        # Normalize the phone number
        phone_number = normalize_phone_number(phone_number)

        # Generate OTP
        otp = OTP.GenerateOTP()

        # Prepare Redis data
        redis_data = {
            "first_name": first_name,
            "second_name": second_name,
            "phone_number": phone_number,
            "otp": otp,
            "verification_channel": "sms",  # SMS only
        }

        # Save to Redis with 5-minute expiry
        r.set(f"user_otp:{phone_number}", json.dumps(redis_data), ex=300)

        # Send OTP via SMS
        OTP.send_otp("sms", phone_number, otp)

        print(f"✅ OTP {otp} generated and sent to {phone_number} via SMS")
        return {"phone_number": phone_number, "otp": otp, "message": "OTP sent successfully"}
    @staticmethod
    def save_user_otp(user_data):
        verification_channel = user_data.get('verificationMethod', 'sms')
        otp = OTP.GenerateOTP()

        phone_number = user_data.get('phone_number')
        if not phone_number:
            raise ValueError("Phone number is required")
        phone_number = normalize_phone_number(phone_number)

        redis_data = {
            "first_name": user_data.get('first_name'),
            "second_name": user_data.get('second_name'),
            "phone_number": phone_number,
            "otp": otp,
            "verification_channel": verification_channel,
            "email": user_data.get('email') if verification_channel== "Email" else None
        }

        r.set(f"user_otp:{phone_number}", json.dumps(redis_data), ex=300)

        if verification_channel == "Email":
            email = user_data.get('email')
            if not email:
                raise ValueError("Email is required for Email OTP")
            redis_data["email"] = email
            OTP.send_email_otp(email, otp)
        else:
            OTP.send_otp(verification_channel, phone_number, otp)

    @staticmethod
    def verify_otp(phone_number, otp_code):
        phone_number = normalize_phone_number(phone_number)
        key1 = f"user_otp:{phone_number}"

        stored_data = r.get(key1)
        if not stored_data:
            return {"code": 404, "message": "OTP not found or expired"}

        redis_data = json.loads(stored_data)
        stored_otp = str(redis_data.get("otp"))

        if stored_otp != str(otp_code):
            return {"code": 400, "message": "Invalid OTP"}

            # correct OTP
        return {"code": 200, "message": "OTP verified successfully"}

    @staticmethod
    def android_verify_otp(phone_number, otp_code):
        phone_number = normalize_phone_number(phone_number)
        key1 = f"user_otp:{phone_number}"

        stored_data = r.get(key1)
        if not stored_data:
            return {"code": 404, "message": "OTP not found or expired"}

        redis_data = json.loads(stored_data)
        stored_otp = str(redis_data.get("otp"))

        if stored_otp == str(otp_code):
            r.delete(key1)
            return {"code": 200, "message": "OTP verified successfully"}
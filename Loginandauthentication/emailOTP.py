from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from decouple import config


FROM_EMAIL = config("SENDGRID_FROM_EMAIL", default="Nexasupport@NexaKenya.co.ke")


def get_sendgrid_client():
    return SendGridAPIClient(config("SENDGRID_API_KEY"))


def send_email(to_email, subject, html_content, from_email=FROM_EMAIL):
    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=subject,
        html_content=html_content,
    )
    response = get_sendgrid_client().send(message)
    return response

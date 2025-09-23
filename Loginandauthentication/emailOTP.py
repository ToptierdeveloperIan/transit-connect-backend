import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from decouple import config
API_KEY=config('EMAIL_API_KEY')

message = Mail(
    from_email='nexasupport@nexakenya.co.ke',
    to_emails='otienoian229@gmail.com',
    subject='Sending with Twilio SendGrid is Fun',
    html_content='<strong>and easy to do anywhere, even with us</strong>')
try:
    sg = SendGridAPIClient(API_KEY)
    # sg.set_sendgrid_data_residency("eu")
    # uncomment the above line if you are sending mail using a regional EU subuser
    response = sg.send(message)
    print(response.status_code)
    print(response.body)
    print(response.headers)
except Exception as e:
    print(e.message)
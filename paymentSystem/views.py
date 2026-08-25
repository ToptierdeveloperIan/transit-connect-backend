from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction

from .event_service import emit_payment_event
from .models import STKPushTransaction, B2CTransaction, PaymentEventType
from .serializers import STKPushSerializer, B2CSerializer
from .paymentEngine import initiate_stk_push, initiate_b2c


# ---------------------------------------------------------------------------
# STK Push (C2B) — rider pays for a ride
# ---------------------------------------------------------------------------

class InitiateSTKPushView(APIView):
    """
    POST /api/payments/stk/initiate/
    Authenticated rider triggers an M-Pesa STK Push on their own phone number.

    Request body:
        amount          (required) – amount in KES
        booking_id      (optional) – links the transaction to an existing booking
        account_reference (optional, max 12 chars) – defaults to "NexaRide"
        transaction_desc  (optional, max 13 chars) – defaults to "Ride Payment"
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = STKPushSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = request.user.phone_number
        amount = serializer.validated_data['amount']
        booking_id = serializer.validated_data.get('booking_id')
        account_reference = serializer.validated_data['account_reference']
        transaction_desc = serializer.validated_data['transaction_desc']

        if booking_id:
            account_reference = f"Booking-{booking_id}"

        try:
            result = initiate_stk_push(
                phone_number=phone_number,
                amount=amount,
                account_reference=account_reference,
                transaction_desc=transaction_desc,
            )
        except Exception as e:
            return Response(
                {"success": False, "message": f"Failed to reach M-Pesa: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if result.get('ResponseCode') == '0':
            with transaction.atomic():
                payment = STKPushTransaction.objects.create(
                    user=request.user,
                    booking_id=booking_id,
                    phone_number=phone_number,
                    amount=amount,
                    merchant_request_id=result['MerchantRequestID'],
                    checkout_request_id=result['CheckoutRequestID'],
                    status='pending',
                )
                payment_id = payment.checkout_request_id
                event_payload = {
                    "amount": str(amount),
                    "currency": "KES",
                    "phone_number": phone_number,
                    "booking_id": booking_id,
                }
                # These three events are persisted to the outbox in the same DB
                # transaction as the local payment row.
                emit_payment_event(
                    payment_id=payment_id,
                    event_type=PaymentEventType.PAYMENT_CREATED,
                    source='payment-api',
                    correlation_id=payment.merchant_request_id,
                    provider_reference=payment.checkout_request_id,
                    payload=event_payload,
                )
                emit_payment_event(
                    payment_id=payment_id,
                    event_type=PaymentEventType.PAYMENT_REQUESTED,
                    source='payment-api',
                    correlation_id=payment.merchant_request_id,
                    provider_reference=payment.checkout_request_id,
                    payload=event_payload,
                )
                emit_payment_event(
                    payment_id=payment_id,
                    event_type=PaymentEventType.PROVIDER_ACCEPTED,
                    source='mpesa-stk-api',
                    correlation_id=payment.merchant_request_id,
                    provider_reference=payment.checkout_request_id,
                    payload=result,
                )
            return Response({
                "success": True,
                "message": "STK Push sent. Please enter your M-Pesa PIN.",
                "checkout_request_id": result['CheckoutRequestID'],
            }, status=status.HTTP_200_OK)

        return Response({
            "success": False,
            "message": result.get('errorMessage', 'M-Pesa returned an error. Try again.'),
            "error_code": result.get('errorCode'),
        }, status=status.HTTP_400_BAD_REQUEST)


class STKPushCallbackView(APIView):
    """
    POST /api/payments/stk/callback/
    Safaricom calls this URL after the customer completes or cancels the PIN prompt.
    No authentication — Safaricom hits this directly.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        body = request.data.get('Body', {}).get('stkCallback', {})

        checkout_request_id = body.get('CheckoutRequestID')
        result_code = body.get('ResultCode')
        result_desc = body.get('ResultDesc')

        try:
            transaction = STKPushTransaction.objects.get(checkout_request_id=checkout_request_id)
        except STKPushTransaction.DoesNotExist:
            # Acknowledge receipt even if we cannot find the record
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        with transaction.atomic():
            transaction.result_code = str(result_code)
            transaction.result_desc = result_desc

            if result_code == 0:
                # Payment successful: extract receipt details from callback metadata.
                items = body.get('CallbackMetadata', {}).get('Item', [])
                metadata = {item['Name']: item.get('Value') for item in items}
                transaction.mpesa_receipt_number = metadata.get('MpesaReceiptNumber')
                transaction.status = 'success'
                event_type = PaymentEventType.PROVIDER_CONFIRMED_SUCCESS
            else:
                transaction.status = 'failed'
                event_type = PaymentEventType.PROVIDER_CONFIRMED_FAILURE

            transaction.save()
            emit_payment_event(
                payment_id=transaction.checkout_request_id,
                event_type=event_type,
                source='mpesa-stk-callback',
                correlation_id=transaction.merchant_request_id,
                provider_reference=transaction.mpesa_receipt_number or transaction.checkout_request_id,
                payload={
                    "result_code": result_code,
                    "result_desc": result_desc,
                    "raw_callback": body,
                },
            )

        # Always respond with success so Safaricom stops retrying
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})


# ---------------------------------------------------------------------------
# B2C — business pays a customer/driver
# ---------------------------------------------------------------------------

class InitiateB2CView(APIView):
    """
    POST /api/payments/b2c/initiate/
    Send money from the business account to any M-Pesa number.
    Requires staff/admin privileges — do not expose this to regular riders.

    Request body:
        phone_number  (required) – recipient phone in 2547XXXXXXXX format
        amount        (required) – amount in KES
        command_id    (optional) – BusinessPayment | SalaryPayment | PromotionPayment
        remarks       (optional, max 100 chars)
        occasion      (optional)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response(
                {"success": False, "message": "Only admins can initiate B2C payments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = B2CSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number']
        amount = serializer.validated_data['amount']
        command_id = serializer.validated_data['command_id']
        remarks = serializer.validated_data['remarks']
        occasion = serializer.validated_data['occasion']

        try:
            result = initiate_b2c(
                phone_number=phone_number,
                amount=amount,
                command_id=command_id,
                remarks=remarks,
                occasion=occasion,
            )
        except Exception as e:
            return Response(
                {"success": False, "message": f"Failed to reach M-Pesa: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if result.get('ResponseCode') == '0':
            with transaction.atomic():
                payment = B2CTransaction.objects.create(
                    user=request.user,
                    phone_number=phone_number,
                    amount=amount,
                    command_id=command_id,
                    remarks=remarks,
                    originator_conversation_id=result['OriginatorConversationID'],
                    conversation_id=result.get('ConversationID'),
                    status='pending',
                )
                payment_payload = {
                    "amount": str(amount),
                    "currency": "KES",
                    "phone_number": phone_number,
                    "command_id": command_id,
                    "remarks": remarks,
                    "occasion": occasion,
                }
                emit_payment_event(
                    payment_id=payment.originator_conversation_id,
                    event_type=PaymentEventType.PAYMENT_CREATED,
                    source='payment-api',
                    correlation_id=payment.conversation_id,
                    provider_reference=payment.originator_conversation_id,
                    payload=payment_payload,
                )
                emit_payment_event(
                    payment_id=payment.originator_conversation_id,
                    event_type=PaymentEventType.PAYMENT_REQUESTED,
                    source='payment-api',
                    correlation_id=payment.conversation_id,
                    provider_reference=payment.originator_conversation_id,
                    payload=payment_payload,
                )
                emit_payment_event(
                    payment_id=payment.originator_conversation_id,
                    event_type=PaymentEventType.PROVIDER_ACCEPTED,
                    source='mpesa-b2c-api',
                    correlation_id=payment.conversation_id,
                    provider_reference=payment.originator_conversation_id,
                    payload=result,
                )
            return Response({
                "success": True,
                "message": "B2C payment initiated.",
                "originator_conversation_id": result['OriginatorConversationID'],
                "conversation_id": result.get('ConversationID'),
            }, status=status.HTTP_200_OK)

        return Response({
            "success": False,
            "message": result.get('errorMessage', 'M-Pesa returned an error. Try again.'),
            "error_code": result.get('errorCode'),
        }, status=status.HTTP_400_BAD_REQUEST)


class B2CResultView(APIView):
    """
    POST /api/payments/b2c/result/
    Safaricom posts the B2C transaction result here after processing.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        result = request.data.get('Result', {})

        originator_conversation_id = result.get('OriginatorConversationID')
        conversation_id = result.get('ConversationID')
        result_code = result.get('ResultCode')
        result_desc = result.get('ResultDesc')

        try:
            transaction = B2CTransaction.objects.get(
                originator_conversation_id=originator_conversation_id
            )
        except B2CTransaction.DoesNotExist:
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        with transaction.atomic():
            transaction.conversation_id = conversation_id
            transaction.result_code = str(result_code)
            transaction.result_desc = result_desc

            if result_code == 0:
                # Extract result parameters
                params = {
                    p['Key']: p['Value']
                    for p in result.get('ResultParameters', {}).get('ResultParameter', [])
                }
                transaction.transaction_id = params.get('TransactionID')
                transaction.status = 'success'
                event_type = PaymentEventType.PROVIDER_CONFIRMED_SUCCESS
            else:
                transaction.status = 'failed'
                event_type = PaymentEventType.PROVIDER_CONFIRMED_FAILURE

            transaction.save()
            emit_payment_event(
                payment_id=transaction.originator_conversation_id,
                event_type=event_type,
                source='mpesa-b2c-result',
                correlation_id=conversation_id,
                provider_reference=transaction.transaction_id or transaction.originator_conversation_id,
                payload={
                    "result_code": result_code,
                    "result_desc": result_desc,
                    "raw_result": result,
                },
            )

        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})


class B2CTimeoutView(APIView):
    """
    POST /api/payments/b2c/timeout/
    Safaricom calls this when the B2C request times out in the queue.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        result = request.data.get('Result', {})
        originator_conversation_id = result.get('OriginatorConversationID')

        try:
            transaction = B2CTransaction.objects.get(
                originator_conversation_id=originator_conversation_id
            )
            with transaction.atomic():
                transaction.status = 'timeout'
                transaction.result_desc = 'Request timed out in M-Pesa queue.'
                transaction.save()
                emit_payment_event(
                    payment_id=transaction.originator_conversation_id,
                    event_type=PaymentEventType.PAYMENT_TIMEOUT_REACHED,
                    source='mpesa-b2c-timeout',
                    correlation_id=transaction.conversation_id,
                    provider_reference=transaction.originator_conversation_id,
                    payload={"raw_timeout": result},
                )
        except B2CTransaction.DoesNotExist:
            pass

        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

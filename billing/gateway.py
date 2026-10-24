"""Official payOS 1.1 SDK adapter; never log payloads or credentials."""
from django.conf import settings
from django.core.exceptions import ValidationError
from payos import PayOS
from payos.types import CreatePaymentLinkRequest

def configured():
    return all(str(value or '').strip() for value in (settings.PAYOS_CLIENT_ID,settings.PAYOS_API_KEY,settings.PAYOS_CHECKSUM_KEY))


def client():
    if not configured():
        raise ValidationError("Thanh toán payOS chưa được cấu hình. Vui lòng chọn thanh toán tại Spa.")
    return PayOS(client_id=settings.PAYOS_CLIENT_ID,api_key=settings.PAYOS_API_KEY,checksum_key=settings.PAYOS_CHECKSUM_KEY,timeout=10,max_retries=0)

def create(payment):
    base=dict(order_code=payment.order_code,amount=int(payment.amount),description=f"AN NHIEN {payment.invoice_id}",
        return_url=settings.PAYOS_RETURN_URL+f"?id={payment.invoice_id}",cancel_url=settings.PAYOS_CANCEL_URL+f"?id={payment.invoice_id}",expired_at=int(payment.expires_at.timestamp()))
    with client() as sdk:return sdk.payment_requests.create(CreatePaymentLinkRequest(**base))

def cancel(payment):
    with client() as sdk:return sdk.payment_requests.cancel(payment.order_code,"Khach chon thanh toan tai Spa / huy lich")


def get(payment):
    with client() as sdk:return sdk.payment_requests.get(payment.order_code)

def verify(payload):
    with client() as sdk:return sdk.webhooks.verify(payload)

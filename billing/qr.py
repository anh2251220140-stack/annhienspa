"""Render the stored provider payload locally; never synthesize bank data."""
import base64
import binascii
from io import BytesIO
import qrcode


def image_data(payload):
    # Reject missing/corrupt EMV payloads instead of presenting a meaningless QR.
    if not isinstance(payload,str) or not payload.startswith('000201') or len(payload)>2048:
        return ''
    try:
        if payload[-8:-4]!='6304' or binascii.crc_hqx(payload[:-4].encode('utf-8'),0xffff)!=int(payload[-4:],16):
            return ''
        qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=8,border=4)
        qr.add_data(payload,optimize=0);qr.make(fit=True)
        output=BytesIO();qr.make_image(fill_color='black',back_color='white').save(output,format='PNG')
        return 'data:image/png;base64,'+base64.b64encode(output.getvalue()).decode('ascii')
    except (ValueError,qrcode.exceptions.DataOverflowError):
        return ''

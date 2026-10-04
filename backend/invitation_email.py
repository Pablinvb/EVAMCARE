"""HTTPS transactional invitations. Never logs provider errors or tokens."""
import json
import os
from urllib.parse import urlsplit, quote
from urllib.request import Request, urlopen


def deliver(recipient, token):
    key = os.getenv('DERMASCAN_RESEND_API_KEY')
    sender = os.getenv('DERMASCAN_EMAIL_FROM')
    base = os.getenv('DERMASCAN_PUBLIC_APP_URL', 'https://pablinvb.github.io/EVAMCARE/')
    parts = urlsplit(base)
    if not key or not sender or parts.scheme != 'https' or not parts.netloc or parts.query or parts.fragment:
        return {'emailStatus': 'not_configured', 'message': 'Cuenta pendiente creada; correo no configurado. Comparte el enlace privado de activación.'}
    link = base + '#/activate-account?token=' + quote(token, safe='')
    payload = {'from': sender, 'to': [recipient], 'subject': 'EVAMCARE: activa tu cuenta',
               'text': 'Has recibido una invitación para EVAMCARE. Para establecer tu contraseña abre este enlace privado. Vence en 48 horas.\n\n' + link + '\n\nSi no esperabas esta invitación, ignora este mensaje.'}
    request = Request('https://api.resend.com/emails', data=json.dumps(payload).encode(),
                      headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json', 'User-Agent': 'EVAMCARE/0.10'}, method='POST')
    try:
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read(65536))
            if response.status != 200 or not result.get('id'):
                raise ValueError('Provider did not accept message')
    except Exception:
        return {'emailStatus': 'failed', 'message': 'La cuenta sigue pendiente. El proveedor no confirmó el envío; puedes regenerar la invitación o compartir el enlace privado.'}
    return {'emailStatus': 'accepted', 'message': 'El proveedor aceptó la invitación. Revisa la bandeja de entrada y spam; la entrega no está confirmada.'}

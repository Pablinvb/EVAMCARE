import json
import os
import unittest
from unittest.mock import MagicMock, patch
from backend.invitation_email import deliver


class InvitationEmailTests(unittest.TestCase):
    def test_missing_configuration_does_not_send(self):
        with patch.dict(os.environ, {}, clear=True), patch('backend.invitation_email.urlopen') as send:
            self.assertEqual(deliver('person@example.test', 'private-token')['emailStatus'], 'not_configured')
            send.assert_not_called()

    def test_acceptance_and_sanitized_failure(self):
        config={'DERMASCAN_RESEND_API_KEY':'test-key','DERMASCAN_EMAIL_FROM':'EVAMCARE <sender@example.test>'}
        with patch.dict(os.environ, config, clear=True), patch('backend.invitation_email.urlopen') as send:
            response=MagicMock();response.status=200;response.read.return_value=b'{"id":"test-message"}'
            send.return_value.__enter__.return_value=response
            self.assertEqual(deliver('person@example.test','test-token')['emailStatus'],'accepted')
            request=send.call_args.args[0]
            payload=json.loads(request.data)
            self.assertEqual(payload['to'],['person@example.test'])
            self.assertIn('#/activate-account?token=test-token',payload['text'])
            send.side_effect=RuntimeError('secret-key private-token')
            result=deliver('person@example.test','test-token')
            self.assertEqual(result['emailStatus'],'failed')
            self.assertNotIn('secret-key',str(result))

    def test_untrusted_app_url_does_not_send(self):
        config={'DERMASCAN_RESEND_API_KEY':'test-key','DERMASCAN_EMAIL_FROM':'sender@example.test','DERMASCAN_PUBLIC_APP_URL':'http://unsafe.test/'}
        with patch.dict(os.environ, config, clear=True), patch('backend.invitation_email.urlopen') as send:
            self.assertEqual(deliver('person@example.test','test-token')['emailStatus'],'not_configured')
            send.assert_not_called()

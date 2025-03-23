import asyncio
import ssl
import unittest
from slixmpp import ClientXMPP
from slixmpp.test.integration import SlixIntegration


class TestTLS(SlixIntegration):
    async def test_connect_direct_tls(self):
        """Check that we can force connection in direct TLS"""
        client = ClientXMPP(
            self.envjid('CI_ACCOUNT1'),
            self.envstr('CI_ACCOUNT1_PASSWORD'),
        )
        client.enable_direct_tls = True
        client.enable_starttls = False
        _, pending = await asyncio.wait(
            [asyncio.ensure_future(client.connect()),
             asyncio.ensure_future(client.wait_until('session_start'))],
            timeout=10
        )
        self.assertFalse(bool(pending))
        extra_info = client.transport.get_extra_info('peername')
        self.assertEqual(extra_info[1], 5223)
        self.assertTrue(isinstance(client.socket, ssl.SSLObject))

    async def test_connect_starttls(self):
        """Check that we can force connection in starttls"""
        client = ClientXMPP(
            self.envjid('CI_ACCOUNT1'),
            self.envstr('CI_ACCOUNT1_PASSWORD'),
        )
        client.enable_direct_tls = False
        client.enable_starttls = True
        _, pending = await asyncio.wait(
            [asyncio.ensure_future(client.connect()),
             asyncio.ensure_future(client.wait_until('session_start'))],
            timeout=10
        )
        self.assertFalse(bool(pending))
        extra_info = client.transport.get_extra_info('peername')
        self.assertEqual(extra_info[1], 5222)
        self.assertTrue(isinstance(client.socket, ssl.SSLObject))

    async def test_validate_cert_custom(self):
        """Check that we can validate the cert manually"""
        client = ClientXMPP(
            self.envjid('CI_ACCOUNT1'),
            self.envstr('CI_ACCOUNT1_PASSWORD'),
        )

        def handler(cert):
            # Abort!
            client.abort()

        with client.event_handler('ssl_cert', handler):
            _, pending = await asyncio.wait(
                [asyncio.ensure_future(client.connect()),
                 asyncio.ensure_future(client.wait_until('killed'))],
                timeout=10
            )
            self.assertFalse(bool(pending))


suite = unittest.TestLoader().loadTestsFromTestCase(TestTLS)

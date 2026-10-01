import unittest
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

from slixmpp.plugins.xep_0420 import NS, OMEMO2_PROFILE, SCEError, SCEProfile, XEP_0420

pack = XEP_0420.pack
unpack = XEP_0420.unpack

ROMEO = 'romeo@montague.lit'
JULIET = 'juliet@capulet.lit'
ROOM = 'room@conference.capulet.lit'
NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def body(text='Hello World!'):
    elem = ET.Element('{jabber:client}body')
    elem.text = text
    return elem


def envelope(inner, root_attrs=f"xmlns='{NS}'"):
    return f'<envelope {root_attrs}>{inner}</envelope>'.encode()


class TestPackUnpack(unittest.TestCase):

    def roundtrip(self, elems=None, **kw):
        data = pack(elems if elems is not None else [body()],
                    sender=ROMEO + '/phone', recipient=JULIET + '/laptop', **kw)
        return data

    def testRoundTrip(self):
        data = self.roundtrip()
        out = unpack(data, sender=ROMEO, recipient=JULIET)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].tag, '{jabber:client}body')
        self.assertEqual(out[0].text, 'Hello World!')

    def testPackedFormat(self):
        data = self.roundtrip().decode()
        self.assertTrue(data.startswith(f"<envelope xmlns='{NS}'><content>"))
        self.assertIn('<body xmlns="jabber:client">Hello World!</body>', data)
        self.assertIn(f'<from jid="{ROMEO}"/>', data)  # bare JID
        self.assertIn(f'<to jid="{JULIET}"/>', data)
        self.assertIn('<rpad>', data)

    def testSpecialCharactersEscaped(self):
        out = unpack(self.roundtrip([body('<a & "b">')]), sender=ROMEO,
                     recipient=JULIET)
        self.assertEqual(out[0].text, '<a & "b">')

    def testRpadMinimumAndRandomLength(self):
        sizes = {len(self.roundtrip([body('x')])) for _ in range(40)}
        self.assertGreater(len(sizes), 1)
        self.assertGreaterEqual(min(sizes), 200)

    def testTimeAffix(self):
        profile = SCEProfile(require_rpad=True, send_time=True)
        data = pack([body()], profile, sender=ROMEO, recipient=JULIET, now=NOW)
        self.assertIn('<time stamp="2026-01-01T12:00:00Z"/>', data.decode())
        unpack(data, profile, sender=ROMEO, recipient=JULIET, reference_time=NOW)

    def testTimeOutsideWindow(self):
        profile = SCEProfile(require_rpad=True, send_time=True)
        data = pack([body()], profile, sender=ROMEO, recipient=JULIET, now=NOW)
        late = NOW + timedelta(minutes=10)
        with self.assertRaises(SCEError):
            unpack(data, profile, sender=ROMEO, recipient=JULIET,
                   reference_time=late)
        early = NOW - timedelta(minutes=10)
        with self.assertRaises(SCEError):
            unpack(data, profile, sender=ROMEO, recipient=JULIET,
                   reference_time=early)

    def testTimeRequiredButMissing(self):
        profile = SCEProfile(require_rpad=True, require_time=True)
        with self.assertRaises(SCEError):
            unpack(envelope('<content><body xmlns="jabber:client"/></content>'
                            '<rpad>x</rpad>'), profile)

    def testNaiveTimeRejected(self):
        data = envelope('<content><body xmlns="jabber:client"/></content>'
                        '<time stamp="2026-01-01T12:00:00"/><rpad>x</rpad>')
        with self.assertRaises(SCEError):
            unpack(data, reference_time=NOW)

    def testGroupChatRequiresTo(self):
        with self.assertRaises(SCEError):
            pack([body()], sender=ROMEO, require_to=True)
        data = pack([body()], sender=ROMEO, recipient=ROOM, require_to=True)
        unpack(data, sender=ROMEO, recipient=ROOM, require_to=True)
        no_to = pack([body()], sender=ROMEO)
        with self.assertRaises(SCEError):
            unpack(no_to, sender=ROMEO, recipient=ROOM, require_to=True)

    def testFromMismatch(self):
        with self.assertRaises(SCEError):
            unpack(self.roundtrip(), sender='mallory@evil.lit', recipient=JULIET)

    def testToMismatch(self):
        with self.assertRaises(SCEError):
            unpack(self.roundtrip(), sender=ROMEO, recipient='other@capulet.lit')

    def testAffixWithoutExpectedValueFailsClosed(self):
        with self.assertRaises(SCEError):
            unpack(self.roundtrip(), recipient=JULIET)

    def testResourceIgnoredInComparison(self):
        unpack(self.roundtrip(), sender=ROMEO + '/tablet',
               recipient=JULIET + '/x')

    def testMissingRpadRejected(self):
        data = envelope('<content><body xmlns="jabber:client">hi</body></content>')
        with self.assertRaises(SCEError):
            unpack(data)

    def testLongRpadAccepted(self):
        data = envelope('<content><body xmlns="jabber:client">hi</body></content>'
                        f'<rpad>{"A" * 50000}</rpad>')
        self.assertEqual(len(unpack(data)), 1)

    def testServerProcessedElementsDropped(self):
        inner = (
            '<content>'
            '<body xmlns="jabber:client">hi</body>'
            '<store xmlns="urn:xmpp:hints"/>'
            '<stanza-id xmlns="urn:xmpp:sid:0" id="1" by="a@b"/>'
            '<origin-id xmlns="urn:xmpp:sid:0" id="2"/>'
            '<addresses xmlns="http://jabber.org/protocol/address"/>'
            '<encryption xmlns="urn:xmpp:eme:0" namespace="x"/>'
            '</content><rpad>x</rpad>'
        )
        out = unpack(envelope(inner))
        self.assertEqual([e.tag for e in out],
                         ['{jabber:client}body', '{urn:xmpp:sid:0}origin-id'])

    def testPackRefusesServerProcessed(self):
        with self.assertRaises(SCEError):
            pack([ET.Element('{urn:xmpp:hints}store')], sender=ROMEO)

    def testPackRefusesUnnamespaced(self):
        with self.assertRaises(SCEError):
            pack([ET.Element('body')], sender=ROMEO)

    def testUnnamespacedContentRejected(self):
        with self.assertRaises(SCEError):
            unpack(envelope('<content><body>hi</body></content><rpad>x</rpad>'))

    def testNestedEnvelopeRejected(self):
        inner = ('<content><envelope xmlns="urn:xmpp:sce:1"><content/></envelope>'
                 '</content><rpad>x</rpad>')
        with self.assertRaises(SCEError):
            unpack(envelope(inner))

    def testMalformedXML(self):
        for data in (b'', b'<envelope', b'not xml',
                     envelope('<content></content><rpad>x</rpad>') + b'<x/>'):
            with self.assertRaises(SCEError):
                unpack(data)

    def testWrongRootOrNamespace(self):
        for data in (b'<envelope xmlns="urn:xmpp:sce:0"><content/></envelope>',
                     b'<envelope><content/></envelope>',
                     b'<content xmlns="urn:xmpp:sce:1"/>'):
            with self.assertRaises(SCEError):
                unpack(data)

    def testMissingOrDuplicateContent(self):
        with self.assertRaises(SCEError):
            unpack(envelope('<rpad>x</rpad>'))
        with self.assertRaises(SCEError):
            unpack(envelope('<content/><content/><rpad>x</rpad>'))

    def testDuplicateAffixRejected(self):
        with self.assertRaises(SCEError):
            unpack(envelope('<content/><rpad>x</rpad><rpad>y</rpad>'))

    def testDoctypeAndEntitiesRejected(self):
        bomb = (b'<!DOCTYPE e [<!ENTITY a "aaaa">]>'
                b'<envelope xmlns="urn:xmpp:sce:1"><content>&a;</content>'
                b'<rpad>x</rpad></envelope>')
        with self.assertRaises(SCEError):
            unpack(bomb)

    def testOversizedRejected(self):
        with self.assertRaises(SCEError):
            unpack(self.roundtrip(), max_size=10)

    def testUnknownAffixIgnored(self):
        data = envelope('<content><body xmlns="jabber:client">hi</body></content>'
                        '<rpad>x</rpad><custom xmlns="urn:example"/>')
        self.assertEqual(len(unpack(data)), 1)

    def testXmlLangPreserved(self):
        elem = body()
        elem.set('{http://www.w3.org/XML/1998/namespace}lang', 'en')
        data = pack([elem], sender=ROMEO).decode()
        self.assertIn('xml:lang="en"', data)
        out = unpack(data.encode(), sender=ROMEO)
        self.assertEqual(out[0].get('{http://www.w3.org/XML/1998/namespace}lang'),
                         'en')


suite = unittest.TestLoader().loadTestsFromTestCase(TestPackUnpack)

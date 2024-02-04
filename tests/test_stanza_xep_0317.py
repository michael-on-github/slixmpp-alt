import unittest
from slixmpp import Presence
from slixmpp.test import SlixTest
import slixmpp.plugins.xep_0317 as xep_0317
from slixmpp.xmlstream import register_stanza_plugin


class TestStanzaHats(SlixTest):

    def setUp(self):
        register_stanza_plugin(Presence, xep_0317.Hats)
        register_stanza_plugin(xep_0317.Hats, xep_0317.Hats)

    def testCreateHats(self):
        raw_xml = """
          <hats xmlns="urn:xmpp:hats:0">
            <hat uri="http://example.com/hats#Teacher" title="Teacher"/>
          </hats>
        """

        hats = xep_0317.Hats()

        hat = xep_0317.Hat()
        hat['uri'] = 'http://example.com/hats#Teacher'
        hat['title'] = 'Teacher'
        hats.append(hat)

        self.check(hats, raw_xml, use_values=False)


suite = unittest.TestLoader().loadTestsFromTestCase(TestStanzaHats)

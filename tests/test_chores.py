import unittest
from pathlib import Path
from xml.etree import ElementTree


class TestChores(unittest.TestCase):
    def test_doap(self) -> None:
        implemented = {
            x.stem.split("_")[-1] for x in (ROOT / "slixmpp" / "plugins").glob("xep_*")
        }

        namespaces = {
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "xmpp": "https://linkmauve.fr/ns/xmpp-doap#",
        }

        tree = ElementTree.fromstring((ROOT / "doap.xml").read_text())

        listed = set()
        for supported_xep in tree.findall(".//xmpp:SupportedXep", namespaces):
            xep_element = supported_xep.find("xmpp:xep", namespaces)
            if xep_element is not None and xep_element.get(
                "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource"
            ):
                xep_url = xep_element.get(
                    "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource"
                )
                assert xep_url
                listed.add(
                    xep_url.split("/")[-1].removeprefix("xep-").removesuffix(".html")
                )

        self.assertEqual(implemented - UNLISTED_DOAP_XEPS, listed - UNLISTED_DOAP_XEPS)


ROOT = Path(__file__).parent.parent
# some XEPs are implemented, but not as
UNLISTED_DOAP_XEPS = {
    "0175",  # SRV records for XMPP over TLS
    "0368",  # XMPP Compliance Suites 2016
    "0478",  # Stream Limits Advertisement
}


suite = unittest.TestLoader().loadTestsFromTestCase(TestChores)

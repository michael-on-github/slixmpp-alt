# Slixmpp: The Slick XMPP Library
# This file is part of Slixmpp.
# See the file LICENSE for copying permission.
"""
Implementation of Stanza Content Encryption (XEP-0420) envelopes.

This module only deals with the plaintext envelope: building it before
encryption (:meth:`XEP_0420.pack`) and strictly validating it after
decryption (:meth:`XEP_0420.unpack`).  It performs no cryptography; the
encryption protocol (e.g. OMEMO 2) is responsible for that.
"""
from __future__ import annotations

import logging
import secrets
import string
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

from slixmpp.jid import JID, InvalidJID
from slixmpp.plugins.base import BasePlugin

log = logging.getLogger(__name__)

try:  # Hardened parser if available, same API as ElementTree.
    from defusedxml import ElementTree as _SafeET
except ImportError:  # pragma: no cover
    _SafeET = None

NS = 'urn:xmpp:sce:1'
_XML_NS = 'http://www.w3.org/XML/1998/namespace'

# Elements that are processed by the server (XEP-0420 §9): they MUST NOT be
# sent inside an envelope and MUST be discarded when found inside one.
# Keys are (namespace, local name); a name of None means "any element in
# this namespace".
SERVER_PROCESSED: frozenset[tuple[str, str | None]] = frozenset({
    ('urn:xmpp:hints', None),                          # XEP-0334
    ('urn:xmpp:sid:0', 'stanza-id'),                   # XEP-0359 (origin-id is allowed)
    ('http://jabber.org/protocol/address', None),      # XEP-0033
    ('urn:xmpp:eme:0', None),                          # XEP-0380
})

# Padding: first reach MIN_ENVELOPE_SIZE bytes, then add 0..MAX_EXTRA_PAD
# random characters (XEP-0420 §4, rpad).  The spec leaves the boundaries open.
MIN_ENVELOPE_SIZE = 200
MAX_EXTRA_PAD = 200
_PAD_ALPHABET = string.ascii_letters + string.digits
DEFAULT_MAX_SIZE = 1024 * 1024
DEFAULT_MAX_SKEW = timedelta(minutes=5)


class SCEError(ValueError):
    """The envelope is malformed or violates the encryption profile."""


@dataclass(frozen=True)
class SCEProfile:
    """Which affix elements an encryption protocol demands (XEP-0420 §4)."""
    require_rpad: bool = False
    require_time: bool = False
    require_from: bool = False
    #: Add a <time/> affix when packing.
    send_time: bool = False
    #: Add a <from/> affix when packing.
    send_from: bool = True


#: XEP-0384 §5.5.1: rpad MUST, time MAY, from SHOULD, to MUST in group chats.
OMEMO2_PROFILE = SCEProfile(require_rpad=True, send_from=True)


def _is_server_processed(tag: str) -> bool:
    ns, _, local = tag[1:].partition('}') if tag.startswith('{') else ('', '', tag)
    return (ns, None) in SERVER_PROCESSED or (ns, local) in SERVER_PROCESSED


def _serialize(elem: ET.Element, parent_ns: str = '') -> str:
    """Serialize with default-namespace declarations (no ``ns0:`` prefixes)."""
    if not elem.tag.startswith('{'):
        raise SCEError(f'element {elem.tag!r} has no namespace')
    ns, _, local = elem.tag[1:].partition('}')
    out = [f'<{local}']
    if ns != parent_ns:
        out.append(f' xmlns={quoteattr(ns)}')
    for key, value in elem.attrib.items():
        if key.startswith('{'):
            attr_ns, _, attr_local = key[1:].partition('}')
            if attr_ns != _XML_NS:
                raise SCEError(f'unsupported namespaced attribute {key!r}')
            key = f'xml:{attr_local}'
        out.append(f' {key}={quoteattr(value)}')
    if elem.text is None and len(elem) == 0:
        out.append('/>')
        return ''.join(out)
    out.append('>')
    if elem.text:
        out.append(escape(elem.text))
    for child in elem:
        out.append(_serialize(child, ns))
        if child.tail:
            out.append(escape(child.tail))
    out.append(f'</{local}>')
    return ''.join(out)


def _bare(jid: JID | str) -> str:
    try:
        return JID(jid).bare
    except InvalidJID as exc:
        raise SCEError(f'invalid JID {str(jid)!r}') from exc


def _random_pad(base_size: int) -> str:
    missing = max(0, MIN_ENVELOPE_SIZE - base_size)
    length = missing + secrets.randbelow(MAX_EXTRA_PAD + 1)
    return ''.join(secrets.choice(_PAD_ALPHABET) for _ in range(length))


def _parse_time(value: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SCEError(f'invalid <time/> stamp {value!r}') from exc
    if stamp.tzinfo is None:
        raise SCEError('<time/> stamp has no timezone')
    return stamp


class XEP_0420(BasePlugin):

    """
    XEP-0420: Stanza Content Encryption

    Builds and verifies SCE envelopes for use by encryption plugins such as
    OMEMO 2.  It does not touch stanzas itself.
    """

    name = 'xep_0420'
    description = 'XEP-0420: Stanza Content Encryption'
    dependencies: ClassVar[set[str]] = set()

    @staticmethod
    def pack(
        elements: Iterable[ET.Element],
        profile: SCEProfile = OMEMO2_PROFILE,
        *,
        sender: JID | str | None = None,
        recipient: JID | str | None = None,
        require_to: bool = False,
        now: datetime | None = None,
    ) -> bytes:
        """
        Build the plaintext envelope to be encrypted.

        :param elements: Namespaced extension elements to protect, e.g. the
            ``jabber:client`` body.  Server-processed elements are refused.
        :param sender: Sender JID (reduced to bare JID) for the <from/> affix.
        :param recipient: Recipient JID (reduced to bare JID) for <to/>.
        :param require_to: The profile demands <to/> (e.g. group chats).
        :returns: UTF-8 serialized envelope.
        """
        content = list(elements)
        for elem in content:
            if _is_server_processed(elem.tag):
                raise SCEError(f'{elem.tag} must not be sent inside an envelope')
        parts = ['<content>', *(_serialize(e, NS) for e in content), '</content>']
        if profile.send_time or profile.require_time:
            stamp = (now or datetime.now(UTC)).astimezone(UTC)
            parts.append(f'<time stamp={quoteattr(stamp.strftime("%Y-%m-%dT%H:%M:%SZ"))}/>')
        if recipient is not None:
            parts.append(f'<to jid={quoteattr(_bare(recipient))}/>')
        elif require_to:
            raise SCEError('profile requires <to/> but no recipient was given')
        if sender is not None and (profile.send_from or profile.require_from):
            parts.append(f'<from jid={quoteattr(_bare(sender))}/>')
        elif profile.require_from:
            raise SCEError('profile requires <from/> but no sender was given')
        body = ''.join(parts)
        if profile.require_rpad:
            # Pad against the size of what we are about to emit.
            wrapper = f"<envelope xmlns='{NS}'>{body}<rpad></rpad></envelope>"
            body += f'<rpad>{_random_pad(len(wrapper.encode("utf-8")))}</rpad>'
        return f"<envelope xmlns='{NS}'>{body}</envelope>".encode()

    @staticmethod
    def unpack(
        data: bytes,
        profile: SCEProfile = OMEMO2_PROFILE,
        *,
        sender: JID | str | None = None,
        recipient: JID | str | None = None,
        require_to: bool = False,
        reference_time: datetime | None = None,
        max_skew: timedelta = DEFAULT_MAX_SKEW,
        max_size: int = DEFAULT_MAX_SIZE,
    ) -> list[ET.Element]:
        """
        Parse and verify a decrypted envelope.

        Fails closed: any affix that is present is verified, and verification
        needs the matching expected value from the caller.

        :param sender: The authenticated bare sender.  For group chats this is
            the sender's *real* JID as established by the encryption layer,
            not the room occupant JID.
        :param recipient: Expected bare recipient (for MUC: the room JID).
        :param require_to: The profile demands <to/> (e.g. group chats).
        :param reference_time: Time the stanza was sent/delivered, as derived
            from the stanza itself (XEP-0203 delay, MAM).  Defaults to now.
        :returns: The extension elements of <content/>, with server-processed
            elements removed.
        :raises SCEError: On anything that is not a valid, verified envelope.
        """
        if len(data) > max_size:
            raise SCEError('envelope too large')
        lowered = data.lower()
        if b'<!doctype' in lowered or b'<!entity' in lowered:
            raise SCEError('DTD/entity declarations are not allowed')
        try:
            parser = _SafeET or ET
            root = parser.fromstring(data)
        except Exception as exc:  # ParseError or defusedxml errors
            raise SCEError(f'invalid XML: {exc}') from exc

        if root.tag != f'{{{NS}}}envelope':
            raise SCEError(f'unexpected root element {root.tag!r}')

        seen: dict[str, ET.Element] = {}
        for child in root:
            if not child.tag.startswith(f'{{{NS}}}'):
                continue  # protocol-specific affix elements are extensible
            local = child.tag[len(NS) + 2:]
            if local not in ('content', 'rpad', 'time', 'to', 'from'):
                continue
            if local in seen:
                raise SCEError(f'duplicate <{local}/> element')
            seen[local] = child

        content = seen.get('content')
        if content is None:
            raise SCEError('missing <content/>')

        if profile.require_rpad and 'rpad' not in seen:
            raise SCEError('missing required <rpad/>')
        # A longer-than-expected rpad is deliberately never rejected.

        if profile.require_time and 'time' not in seen:
            raise SCEError('missing required <time/>')
        if profile.require_from and 'from' not in seen:
            raise SCEError('missing required <from/>')
        if require_to and 'to' not in seen:
            raise SCEError('missing required <to/>')

        for name, expected in (('from', sender), ('to', recipient)):
            affix = seen.get(name)
            if affix is None:
                continue
            if expected is None:
                raise SCEError(f'<{name}/> present but no expected value given')
            jid = affix.get('jid')
            if jid is None or _bare(jid) != _bare(expected):
                raise SCEError(f'<{name}/> does not match the stanza')

        time_elem = seen.get('time')
        if time_elem is not None:
            stamp = _parse_time(time_elem.get('stamp', ''))
            ref = reference_time or datetime.now(UTC)
            if ref.tzinfo is None:
                raise SCEError('reference_time must be timezone-aware')
            if abs(stamp - ref) > max_skew:
                raise SCEError('<time/> is outside the accepted window')

        result = []
        for elem in content:
            if not elem.tag.startswith('{'):
                raise SCEError(f'content element {elem.tag!r} has no namespace')
            if elem.tag.startswith(f'{{{NS}}}'):
                # An un-namespaced child (e.g. <body/>) inherits the envelope's
                # default namespace; nested envelopes are not allowed either.
                raise SCEError(f'content element {elem.tag!r} is in the SCE namespace')
            if _is_server_processed(elem.tag):
                log.warning('Dropping server-processed element %s from envelope',
                            elem.tag)
                continue
            result.append(elem)
        return result

    @staticmethod
    def serialize(elem: ET.Element) -> str:
        """Serialize an element with default namespaces (no prefixes)."""
        return _serialize(elem)

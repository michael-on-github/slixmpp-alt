.. _use-encryption:

Use Encryption Correctly
========================

Using encryption requires some care - if done incorrectly, plaintext could
accidentally get leaked on outgoing stanzas, or decrypted content might not be
processed on incoming stanzas. This howto gives guidelines and boilerplate for
an encrypted Slixmpp client setup. The information is not specific to any
encryption mechanism; it applies to anything from `XEP-0384: OMEMO Encryption
0.3.0 <https://xmpp.org/extensions/attic/xep-0384-0.3.0.html>`_, over `XEP-0420:
Stanza Content Encryption <https://xmpp.org/extensions/xep-0420.html>`_-based
encryption mechanisms like `modern OMEMO
<https://xmpp.org/extensions/xep-0384.html>`_ or `XEP-0373: OpenPGP for XMPP
<https://xmpp.org/extensions/xep-0373.html>`_, to potential future mechanisms
like `Messaging Layer Security (MLS) <https://www.ietf.org/rfc/rfc9420>`_.

Introduction
------------

Slixmpp uses a plugin-based architecture, where plugins usually implement one
XEP's functionality. Plugins have different ways to interact with stanzas. For
example, they can register handlers using
:meth:`register_handler <slixmpp.xmlstream.xmlstream.XMLStream.register_handler>`,
which allows them to process incoming stanzas or sub-elements without many
limitations, or they can modify whole incoming and outgoing stanzas through
so-called "filters" via
:meth:`add_filter <slixmpp.xmlstream.xmlstream.XMLStream.add_filter>`.

Plugins are generally written to work with plain stanzas and elements, not
encrypted ones. That means that for the incoming direction, stanzas have to be
decrypted *before* letting the (non-encryption) plugins process them, and for
the outgoing direction, stanzas have to be encrypted *after* all of the other
plugins have performed their modifications.

Slixmpp offers API specifically for encryption use-cases, which offers solutions
for both of these requirements. For the incoming direction, Slixmpp offers a way
to *inject* decrypted stanzas and treat them as if they had just been received,
allowing all plugins to process the decrypted stanza normally. For the outgoing
direction, an additional filter stage is available that is guaranteed to run
*just* before sending stanzas out, after all processing by other plugins has
completed. That way, if set up correctly, applications can make sure that
incoming stanzas are always fully processed - whether encrypted or not - and
that no plaintext is leaked accidentally in outgoing stanzas.

The following sections show how to use the injection API for incoming encrypted
stanzas and the ``'out_sce'`` filter stage for outgoing encrypted stanzas.

Incoming - Using the Injection API
----------------------------------

The following example shows boilerplate code for a decryption setup that makes
use of the injection API. This setup makes sure that incoming stanzas are fully
processed even if encrypted.

.. code-block:: python

    from slixmpp.clientxmpp import ClientXMPP
    from slixmpp.xmlstream.handler import CoroutineCallback
    from slixmpp.xmlstream.matcher import MatchXPath
    from slixmpp.xmlstream.stanzabase import StanzaBase

    class InjectionApiExample(ClientXMPP):
        def __init__(self, ...) -> None:
            super().__init__(...)

            # Register a handler that is called for all incoming message stanzas
            self.register_handler(CoroutineCallback(
                "Messages",
                MatchXPath(f"{{{self.default_ns}}}message"),
                self.incoming_stanza_handler
            ))

            # IQs can also be encrypted, used for example by
            # https://xmpp.org/extensions/xep-0473.html
            #self.register_handler(CoroutineCallback(
            #    "IQs",
            #    MatchXPath(f"{{{self.default_ns}}}iq"),
            #    self.incoming_stanza_handler
            #))

        async def incoming_stanza_handler(self, stanza: StanzaBase) -> None:
            # Get a reference to the encryption plugin, for example OMEMO
            # (XEP-0384) or OX (XEP-0373)
            enc_plugin = self["xep_XXXX"]

            # Encryption plugins should offer a method to quickly find whether a
            # stanza is encrypted or not
            if enc_plugin.is_encrypted(stanza):
                # Try to decrypt the stanza and deal with errors
                try:
                    plain_stanza = await enc_plugin.decrypt(stanza)
                except:
                    # Error handling here!
                    return

                # Now that the stanza is decrypted, make use of the injection
                # API to fully process it as if it was newly received!
                self.recv_stanza(plain_stanza)
                return
            
            else:
                # Only plain stanzas make it here - either stanzas that were
                # decrypted before or stanzas that were unencrypted in the first
                # place.
                # If you don't have to deal with the plain stanzas, for example
                # because the content is processed by other plugins or because
                # you have more specific handlers for the subelements you care
                # about, you can omit this "else" branch.
                print(f"Plain stanza: {stanza}")

Incoming - Passing Metadata
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The above boilerplate decrypts stanzas and injects them, such that they are
fully re-processed in plain. This leads to a potential problem for some
applications: when a handler sees an unencrypted stanza, there is no indication
of whether it was originally received in plain, or whether it was decrypted and
then injected. This information can be important for some applications, for
example to display decrypted messages differently in the UI.

The following example shows how to save metadata for injected stanzas and how to
retrieve that metadata later on when the injected stanza appears in a handler.
It builds on the example above, omitting some of its code for brevity.

.. code-block:: python

    from typing import Dict, NamedTuple, Optional
    import weakref

    ...

    # An example structure to hold metadata for decrypted & injected stanzas. In
    # this case it's a bit overkill, only holding a single boolean that is
    # always True. Most encryption mechanisms will return additional metadata
    # when decrypting stanzas, for example about the sender's public key, which
    # could be included here.
    class InStanzaMeta(NamedTuple):
        injected: bool

    class IncomingMetadataExample(ClientXMPP):
        def __init__(self, ...) -> None:
            super().__init__(...)

            ...

            self.injected_stanza_meta: Dict[int, InStanzaMeta] = {}

        def add_in_meta(self, stanza: StanzaBase, meta: InStanzaMeta) -> None:
            # The use of weakref here makes cleanup automatic and convenient
            stanza_id = id(stanza)
            self.injected_stanza_meta[stanza_id] = meta
            weakref.ref(
                stanza,
                lambda _: self.injected_stanza_meta.pop(stanza_id, None)
            )

        def get_in_meta(self, stanza: StanzaBase) -> Optional[InStanzaMeta]:
            return self.injected_stanza_meta.get(id(stanza), None)

        async def incoming_stanza_handler(self, stanza: StanzaBase) -> None:
            enc_plugin = self["xep_XXXX"]
            if enc_plugin.is_encrypted(stanza):
                ...

                # Add the metadata before injecting the stanza:
                self.add_in_meta(plain_stanza, InStanzaMeta(injected=True))
                self.recv_stanza(plain_stanza)
                return

            else:
                # Look for metadata stored for this stanza:
                in_meta = self.get_in_meta(stanza)
                if in_meta is None:
                    print(f"This stanza was originally unencrypted")
                else:
                    print(f"This stanza was decrypted & injected")

Outgoing - Using the ``'out_sce'`` Filter Stage
-----------------------------------------------

The ``'out_sce'`` filter stage has been added specifically to encrypt outgoing
stanzas after they have been fully processed. The following shows how it's used:

.. code-block:: python

    from typing import Optional

    from slixmpp.clientxmpp import ClientXMPP
    from slixmpp.stanza import Message
    from slixmpp.xmlstream.stanzabase import StanzaBase

    class OutSceFilterExample(ClientXMPP):
        def __init__(self, ...) -> None:
            super().__init__(...)

            self.add_filter("out_sce", self.outgoing_stanza_handler)

        async def outgoing_stanza_handler(self, stanza: StanzaBase) \
            -> Optional[StanzaBase]:
            """
            This handler has to be async. It is called for each outgoing stanza
            and is able to modify the stanza, replace it with a different stanza
            or completely drop it. This includes both stanzas sent directly by
            your application (using e.g. `StanzaBase.send()`) and stanzas sent
            by other plugins.
            """

            # In this example, only message stanzas are encrypted, though other
            # stanzas can also be encrypted, which is used for example by
            # https://xmpp.org/extensions/xep-0473.html
            if not isinstance(stanza, Message):
                return stanza

            # Get a reference to the encryption plugin, for example OMEMO
            # (XEP-0384) or OX (XEP-0373)
            enc_plugin = self["xep_XXXX"]

            # Try to encrypt the stanza and deal with errors
            try:
                # The encryption API will slightly differ between
                # implementations, but in general you will always have to pass
                # in a plain stanza and either have it encrypted in-place or
                # receive a new, encrypted version of the input.
                encrypted_stanza = await enc_plugin.encrypt(stanza)
            except:
                # Error handling here! If you don't want to send the stanza in
                # plain, you either have to raise from this method or return
                # `None`.
                raise
                # return None

            # Return the encrypted stanza to send it instead of the plain one.
            return encrypted_stanza

Outgoing - Passing Metadata
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``'out_sce'`` filter is called for all outgoing stanzas, whether they were
sent directly by the application or by a plugin, without any context. This can
be a problem for applications that don't want to encrypt all stanzas always, but
decide what to encrypt based on conditions that are not available in the
``'out_sce'`` filter handler. For example, a bot might want to respond to plain
messages in plain, instead of always attempting encryption.

To solve that, applications can add metadata to outgoing stanzas. The following
example shows a bot that responds to plain messages in plain and encrypted
messages encrypted, by attaching metadata to stanzas it sends and reacting to
that metadata in the filter handler.

.. code-block:: python

    from typing import Dict, NamedTuple, Optional
    import weakref

    ...

    # An example structure to hold metadata for outgoing stanzas.
    class OutStanzaMeta(NamedTuple):
        send_plain: bool

    class OutgoingMetadataExample(ClientXMPP):
        def __init__(self, ...) -> None:
            super().__init__(...)

            self.outgoing_stanza_meta: Dict[int, OutStanzaMeta] = {}

            self.register_handler(CoroutineCallback(
                "Messages",
                MatchXPath(f"{{{self.default_ns}}}message"),
                self.incoming_stanza_handler
            ))
            self.add_filter("out_sce", self.outgoing_stanza_handler)

        def add_out_meta(self, stanza: StanzaBase, meta: OutStanzaMeta) -> None:
            # The use of weakref here makes cleanup automatic and convenient
            stanza_id = id(stanza)
            self.outgoing_stanza_meta[stanza_id] = meta
            weakref.ref(
                stanza,
                lambda _: self.outgoing_stanza_meta.pop(stanza_id, None)
            )

        def get_out_meta(self, stanza: StanzaBase) -> Optional[OutStanzaMeta]:
            return self.outgoing_stanza_meta.get(id(stanza), None)

        async def incoming_stanza_handler(self, stanza: StanzaBase) -> None:
            mfrom = stanza["from"]

            enc_plugin = self["xep_XXXX"]

            if enc_plugin.is_encrypted(stanza):
                reply = self.make_message(mto=mfrom, mtype="chat")
                reply["body"] = "Received encrypted stanza."
                self.add_out_meta(reply, OutStanzaMeta(send_plain=False))
                reply.send()

            else:
                reply = self.make_message(mto=mfrom, mtype="chat")
                reply["body"] = "Received plain stanza."
                self.add_out_meta(reply, OutStanzaMeta(send_plain=True))
                reply.send()

        async def outgoing_stanza_handler(self, stanza: StanzaBase) \
            -> Optional[StanzaBase]:
            if not isinstance(stanza, Message):
                return stanza

            # Look for metadata stored for this stanza:
            out_meta = self.get_out_meta(stanza)

            # If there is metadata attached to this stanza, and the metadata
            # requests the stanza to be sent in plain, return it unmodified.
            if out_meta is not None and out_meta.send_plain:
                return stanza

            enc_plugin = self["xep_XXXX"]

            # Otherwise, run the usual encryption logic...
            try:
                encrypted_stanza = await enc_plugin.encrypt(stanza)
            except:
                # Error handling here!
                raise

            return encrypted_stanza

.. note::

    It is recommended to structure the code such that encryption is opt-out
    rather than opt-in. For example, in the code above, all stanzas are
    encrypted unless explicitly opted out by setting ``send_plain=True`` in the
    metadata.

.. warning::

    This example is incomplete, it doesn't even attempt to decrypt the incoming
    stanzas. Only use it as a reference for how to add metadata to outgoing
    stanzas.

Full Examples
-------------

A fully-fledged OMEMO-encrypted echo bot example with MUC support, part of the
OMEMO plugin for Slixmpp:
https://github.com/Syndace/slixmpp-omemo/blob/main/examples/echo_client.py

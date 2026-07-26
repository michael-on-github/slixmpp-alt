Getting Started (with examples)
-------------------------------

Before starting…
################

Slixmpp is a library for using the XMPP protocol, so if you are not very familiar
with the core XMPP concepts, here are a few that are essential to
understand before diving in:

Entities
~~~~~~~~

XMPP has **clients**, **servers**, and **components**.

* Clients: user-facing XMPP software (Conversations, Gajim, Poezio…), or bots. They talk to servers.
* Servers: XMPP servers (Prosody, Ejabberd, Openfire…). Clients connect to them and they connect to servers.
* Components: Additional software on the server side that provides additional features.

Slixmpp allows you to write clients and components easily, but we do not
implement an XMPP server.


JIDs
~~~~
A JID, for Jabber ID, is the address of an entity over XMPP and can have three
primary forms:

* ``server``, a **bare** JID without a user part, for components and servers.
* ``user@server``, a **bare** JID with a user part.
* ``user@server/resource``, a **full** JID including a client resource.

Slixmpp provides a ``JID`` class for creating and validating those addresses
easily.

XEPs
~~~~

A XEP (for *XMPP Extension Protocol*) is a document standardizing XMPP features
and interactions. This is the key to XMPP’s extensibility.

Slixmpp implements a hefty number of those documents, and most of those are
implemented as **plugins**, which will only be loaded at the developer’s
request.

Some of those plugins may require extra dependencies.

Payloads
~~~~~~~~

There are three main types of payloads in XMPP, called **stanzas**, those are:

* ``<message/>``, containing a message to another entity, represented by the ``Message`` class.
* ``<presence/>``, containing presence information, represented by the ``Presence`` class.
* ``<iq/>``, containing a query (of type ``set`` or ``get``),
  which the remote entity must answer with another IQ having the same identifier
  (either with type ``error`` or ``result``). Represented by the ``Iq`` class.


The identifier of a stanza is the ``id`` attribute of its top-level element,
e.g. ``<message id="some-id" />``. An ``Iq`` must have an identifier.




.. toctree::
    :maxdepth: 3

    echobot
    sendlogout
    component
    presence
    muc
    scheduler
    iq

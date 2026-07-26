Send a Message Every 5 Minutes
==============================

Slixmpp has a simple :meth:`~slixmpp.xmlstream.xmlstream.XMLStream.schedule()` method which
allows you to schedule events in the future, either as a one-off or repeatedly.


Example
-------

Building up from the very simple ``send_client`` in the ``examples/`` directory,
we can use ``schedule`` to easily reach the goal:


.. code-block:: python

    class RepeatSendMsgBot(slixmpp.ClientXMPP):

        """
        A basic Slixmpp bot that will send a message every 5 minutes.
        """

        def __init__(self, jid, password, recipient, message):
            slixmpp.ClientXMPP.__init__(self, jid, password)

            # The message we wish to send, and the JID that
            # will receive it.
            self.recipient = recipient
            self.msg = message

            # The session_start event will be triggered when
            # the bot establishes its connection with the server
            # and the XML streams are ready for use. We want to
            # listen for this event so that we we can initialize
            # our roster.
            self.add_event_handler("session_start", self.start)

        def _send_message(self):
            """Send the message."""
            self.send_message(mto=self.recipient, mbody=self.msg, mtype='chat')

        async def start(self, event):
            """
            Process the session_start event.

            Typical actions for the session_start event are
            requesting the roster and broadcasting an initial
            presence stanza.

            Arguments:
                event -- An empty dictionary. The session_start
                         event does not provide any additional
                         data.
            """
            self.send_presence()
            await self.get_roster()
            # Use schedule() to send a message every 5 minutes (300 seconds),
            # the schedule needs a name so that it can be cancelled in the
            # future.
            self.schedule(name="send_msg", seconds=300,
                          callback=self._send_message, repeat=True)



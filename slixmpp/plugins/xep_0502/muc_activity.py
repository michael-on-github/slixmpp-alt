# Slixmpp: The Slick XMPP Library
# Copyright (C) 2025 Mathieu Pasquet
# This file is part of Slixmpp.
# See the file LICENSE for copying permission.

from typing import Optional
from slixmpp import JID
from slixmpp.plugins import BasePlugin
from slixmpp.exceptions import IqError, IqTimeout


class XEP_0502(BasePlugin):
    """
    XEP-0502: MUC Activity Indicator
    """

    name = "xep_0502"
    description = "XEP-0502: MUC Activity Indicator"
    dependencies = {"xep_0030", "xep_0128"}
    namespace = 'urn:xmpp:muc-activity'

    async def get_activity(self, jid: JID, **iqargs) -> Optional[float]:
        """
        Return the activity of a room, or None if the activity is not found
        """
        try:
            info_iq = await self.xmpp.plugin['xep_0030'].get_info(
                jid=jid,
                **iqargs,
            )
        except (IqError, IqTimeout):
            return None
        disco = info_iq.get_plugin('disco_info', check=True)
        if not disco:
            return None
        if not 'forms' in disco:
            return None
        forms = disco['forms']
        if not forms:
            return None
        field = '{%s}message-activity' % self.namespace
        for form in forms:
            values = form.get_values()
            result = values.get(field, None)
        return result

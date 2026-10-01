# Slixmpp: The Slick XMPP Library
# This file is part of Slixmpp.
# See the file LICENSE for copying permission.
from slixmpp.plugins.base import register_plugin
from slixmpp.plugins.xep_0420.sce import (
    NS,
    OMEMO2_PROFILE,
    XEP_0420,
    SCEError,
    SCEProfile,
)

register_plugin(XEP_0420)

__all__ = ['NS', 'OMEMO2_PROFILE', 'XEP_0420', 'SCEError', 'SCEProfile']

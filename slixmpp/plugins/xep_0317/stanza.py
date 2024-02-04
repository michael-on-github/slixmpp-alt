from slixmpp.xmlstream import ElementBase

NS = 'urn:xmpp:hats:0'


class Hats(ElementBase):
    """
    Hats element, container for multiple hats:

    .. code-block::xml


      <hats xmlns='urn:xmpp:hats:0'>
        <hat title='Host' uri='http://schemas.example.com/hats#host' xml:lang='en-us'>
            <badge xmlns="urn:example:badges" fgcolor="#000000" bgcolor="#58C5BA"/>
        </hat>
        <hat title='Presenter' uri='http://schemas.example.com/hats#presenter' xml:lang='en-us'>
            <badge xmlns="urn:example:badges" fgcolor="#000000" bgcolor="#EC0524"/>
        </hat>
      </hats>

    """

    name = 'hats'
    namespace = NS
    plugin_attrib = 'hats'


class Hat(ElementBase):
    """
    Hat element, has a title and url, may contain arbitrary sub-elements.

    .. code-block::xml

        <hat title='Host' uri='http://schemas.example.com/hats#host' xml:lang='en-us'>
            <badge xmlns="urn:example:badges" fgcolor="#000000" bgcolor="#58C5BA"/>
        </hat>

    """
    name = 'hat'
    namespace = NS
    plugin_attrib = 'hat'
    interfaces = {'title', 'uri'}

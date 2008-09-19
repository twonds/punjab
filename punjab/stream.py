"""

"""
from twisted.words import domish


class PunjabElementStream(domish.ExpatElementStream):
    """

    We need to store the raw unicode data to bypass serialization.

    """
    
    def _onStartElement(self, name, attrs):
        # Generate a qname tuple from the provided name
        qname = name.split(" ")
        if len(qname) == 1:
            qname = ('', name)

        # Process attributes
        for k, v in attrs.items():
            if k.find(" ") != -1:
                aqname = k.split(" ")
                attrs[(aqname[0], aqname[1])] = v
                del attrs[k]

        # Construct the new element
        e = domish.Element(qname, self.defaultNsStack[-1], attrs, self.localPrefixes)
        self.localPrefixes = {}

        # Document already started
        if self.documentStarted == 1:
            if self.currElem != None:
                self.currElem.children.append(e)
                e.parent = self.currElem
            self.currElem = e

        # New document
        else:
            self.documentStarted = 1
            self.DocumentStartEvent(e)

    def _onEndElement(self, _):
        # Check for null current elem; end of doc
        if self.currElem is None:
            self.DocumentEndEvent()
            
        # Check for parent that is None; that's
        # the top of the stack
        elif self.currElem.parent is None:
            self.ElementEvent(self.currElem)
            self.currElem = None

        # Anything else is just some element in the current
        # packet wrapping up
        else:
            self.currElem = self.currElem.parent

    def _onCdata(self, data):
        if self.currElem != None:
            self.currElem.addContent(data)

    def _onStartNamespace(self, prefix, uri):
        # If this is the default namespace, put
        # it on the stack
        if prefix is None:
            self.defaultNsStack.append(uri)
        else:
            self.localPrefixes[prefix] = uri

    def _onEndNamespace(self, prefix):
        # Remove last element on the stack
        if prefix is None:
            self.defaultNsStack.pop()

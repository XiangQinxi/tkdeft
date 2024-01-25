class DObject(object):
    """
    基础对象
    """

    from easydict import EasyDict

    attributes = EasyDict(
        {
            "class": "DObject"
        }
    )

    def dconfigure(self, **kwargs):
        for attribute in self.attributes:
            if attribute in kwargs:
                self.attributes[attribute] = kwargs.pop(attribute)

    dconfig = dconfigure

    def dcget(self, key):
        if key in self.attributes:
            return self.attributes[key]
        else:
            return None

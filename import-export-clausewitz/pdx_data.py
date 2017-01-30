import io
from . import (tree, utils)

class PdxFile():
    """Class representing a Paradox Clausewitz Engine .mesh File."""
    def __init__(self, filename):
        self.filename = filename
        self.__file_reference__ = None
        self.rawData = []
        self.nodes = []

    def read(self):
        """Read and Parse the specified File."""
        self.__file_reference__ = io.open(self.filename, "rb")
        self.rawData = self.__file_reference__.read()

        self.__parse__()

    def __parse__(self):
        data = self.rawData.lstrip(b"@@b@")

        buffer = utils.BufferReader(data)

        while not buffer.IsEOF():
            char = buffer.NextChar()

            if char == "!":
                self.nodes.append(self.read_property(buffer))
            elif char == "[":
                self.nodes.append(self.read_object(buffer, 1))

        #self.dataTree = tree.Tree(rootNode)
        #self.ReadObject(rootNode, buffer, -1)

        #self.dataTree.print()
        print(self.nodes)

        for i in range(1, len(self.nodes)):
            try:
                print(self.nodes[i].name)
                print(self.nodes[i].properties)
                print(self.nodes[i].depth)
            finally:
                pass

        self.__file_reference__.close()

    def read_property(self, buffer: utils.BufferReader):
        """Read a .mesh Property using the provided Buffer"""
        name = ""
        property_data = []

        lower_bound = buffer.GetCurrentOffset()

        name_length = buffer.NextInt8()

        for i in range(0, name_length):
            name += buffer.NextChar()

        name = utils.TranslatePropertyName(name)

        char = buffer.NextChar()

        if char == "i":
            data_count = buffer.NextUInt32()

            for i in range(0, data_count):
                property_data.append(buffer.NextInt32())
        elif char == "f":
            data_count = buffer.NextUInt32()

            for i in range(0, data_count):
                property_data.append(buffer.NextFloat32())
        elif char == "s":
            value = ""
            stringType = buffer.NextUInt32()
            dataCount = buffer.NextUInt32()

            value = utils.ReadNullByteString(buffer)

            property_data = value

        upper_bound = buffer.GetCurrentOffset()

        if name == "pdxasset":
            result = PdxAsset()
            result.bounds = (lower_bound, upper_bound)
        else:
            result = PdxProperty(name, (lower_bound, upper_bound))
            result.value = property_data

        return result

    def read_object(self, buffer: utils.BufferReader, depth):
        """Reads object Data"""
        char = buffer.NextChar()
        object_properties = []

        if char == "[":
            return self.read_object(buffer, depth + 1)
        else:
            object_name = char + utils.ReadNullByteString(buffer)

            while not buffer.IsEOF():
                char = buffer.NextChar(True)

                if char == "!":
                    buffer.NextChar()
                    object_properties.append(self.read_property(buffer))
                elif char == "[":
                    break

            return PdxObject(object_name, object_properties, depth)

class PdxAsset():
    def __init__(self):
        self.bounds = (0,0)
        self.name = "pdxasset"
        self.value = 0

class PdxMesh():
    def __init__(self, name, blenderName):
        self.bounds = (0,0)
        self.name = name
        self.blenderName = blenderName
        self.blenderMesh = None
        self.verts = []
        self.faces = []
        self.tangents = []
        self.normals = []
        self.locators = []
        self.uv_coords = []
        self.material = None

class PdxProperty():
    """Temporary class to hold the Values of a parsed Property until it gets mapped to the object"""
    def __init__(self, name, bounds):
        self.name = name
        self.bounds = bounds
        self.value = []

class PdxObject():
    """Temporary object"""
    def __init__(self, name, properties, depth):
        self.name = name
        self.properties = properties
        self.depth = depth

class PdxLocator():
    def __init__(self, name, pos):
        self.bounds = (0,0)
        self.name = name
        self.pos = pos        
    
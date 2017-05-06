import io
import struct
from . import (utils)

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
                self.nodes.append(self.read_object(buffer, 0, None))

        print("Parsed")

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
        print("Property: " + name)

        char = buffer.NextChar()

        if char == "i":
            data_count = buffer.NextUInt32()

            for i in range(0, data_count):
                temp = buffer.NextInt32()
                property_data.append(temp)
                #print("Integer: " + str(temp))

            if name == "pdxasset":
                print("PDXAsset: " + str(property_data))
        elif char == "f":
            data_count = buffer.NextUInt32()

            for i in range(0, data_count):
                temp = buffer.NextFloat32()
                property_data.append(temp)
                #if name == "min" or name == "max":
                    #print("Float: " + str(temp))
        elif char == "s":
            value = ""
            stringType = buffer.NextUInt32()
            dataCount = buffer.NextUInt32()

            value = utils.ReadNullByteString(buffer)
            #print("String: " + value)

            property_data = value

        upper_bound = buffer.GetCurrentOffset()

        if name == "pdxasset":
            result = PdxAsset()
            result.bounds = (lower_bound, upper_bound)
        else:
            result = PdxProperty(name, (lower_bound, upper_bound))
            result.value = property_data

        return result

    def read_object(self, buffer: utils.BufferReader, depth, prev_obj):
        """Reads object Data"""
        char = buffer.NextChar()
        object_properties = []
        sub_objects = []

        if char == "[":
            depth_temp = 1
            
            while buffer.NextChar(True) == '[':
                buffer.NextChar()
                depth_temp += 1
                
            return self.read_object(buffer, depth_temp, prev_obj)
        else:
            object_name = char + utils.ReadNullByteString(buffer)
            print((" " * ((depth - 1) * 4)) + "Object Name: " + object_name)

            if object_name == "object":
                result = PdxWorld(sub_objects)
            elif object_name == "mesh":
                result = PdxMesh()
            elif object_name == "locator":
                result = PdxLocators()
            else:
                result = PdxObject(object_name, [], depth)

            while not buffer.IsEOF():
                char = buffer.NextChar(True)

                if char == "!":
                    buffer.NextChar()
                    object_properties.append(self.read_property(buffer))
                elif char == "[":
                    if depth < utils.PreviewObjectDepth(buffer):
                        if isinstance(prev_obj, PdxLocators) or isinstance(prev_obj, PdxMesh):
                            sub_objects.append(self.read_object(buffer, 0, prev_obj))
                        else:
                            sub_objects.append(self.read_object(buffer, 0, result))
                    else:
                        break

            #temp = ""
            #for i in range(0, depth):
            #    temp += "-"
            #print(temp + "Sub Objects: ", len(sub_objects))

            if object_name == "object":
                result = PdxWorld(sub_objects)
            elif object_name == "mesh":
                if len(object_properties) == 2:
                    result = PdxCollisionMesh()
                    result.verts = utils.TransposeCoordinateArray3D(object_properties[0].value)
                    #print("Verts: " + str(len(object_properties[0].value)))
                    result.faces = utils.TransposeCoordinateArray3D(object_properties[1].value)
                    #print("Faces: " + str(len(object_properties[1].value)))
                    result.meshBounds = sub_objects[0]
                    result.material = sub_objects[1]
                elif len(object_properties) == 5:
                    result = PdxMesh()
                    result.verts = utils.TransposeCoordinateArray3D(object_properties[0].value)
                    #print("Verts: " + str(len(object_properties[0].value)))
                    result.faces = utils.TransposeCoordinateArray3D(object_properties[4].value)
                    #print("Faces: " + str(len(object_properties[4].value)))
                    result.normals = utils.TransposeCoordinateArray3D(object_properties[1].value)
                    #print("Normals: " + str(len(object_properties[1].value)))
                    result.tangents = object_properties[2].value
                    #print("Tangents: " + str(len(object_properties[2].value)))
                    result.uv_coords = utils.TransposeCoordinateArray2D(object_properties[3].value)
                    #print("UV-Map: " + str(len(object_properties[3].value)))
                    result.meshBounds = sub_objects[0]
                    result.material = sub_objects[1]
                else:
                    print("ERROR ::: Invalid Mesh-Property Count! (" + str(len(object_properties)) + ")")
            elif object_name == "locator":
                result = PdxLocators()
                result.locators = sub_objects
            elif object_name == "aabb":
                result = PdxBounds(object_properties[0].value, object_properties[1].value)
            elif object_name == "material":
                if len(object_properties) == 1:
                    print("PdxCollisionMaterial")
                    result = PdxCollisionMaterial()
                    result.shaders = object_properties[0].value
                    if result.shaders != "Collision":
                        print("Error! ::: Collision Shader not set Correctly!")
                elif len(object_properties) == 4:
                    result = PdxMaterial()
                    result.shaders = object_properties[0].value
                    result.diffs = object_properties[1].value
                    result.normals = object_properties[2].value
                    result.specs = object_properties[3].value
                else:
                    print("ERROR ::: Invalid Material-Property Count! (" + str(len(object_properties)) + ")")
            else:
                print("Else: " + object_name)
                if isinstance(prev_obj, PdxLocators):
                    result = PdxLocator(object_name, object_properties[0].value)
                elif isinstance(prev_obj, PdxWorld):# and object_name.endswith("MeshShape"):
                    print("World contains: " + str(len(sub_objects)) + "|" + str(sub_objects))
                    result = PdxShape(object_name)
                    result.mesh = sub_objects[0]
                else:
                    result = PdxObject(object_name, object_properties, depth)

            return result

class PdxAsset():
    def __init__(self):
        self.bounds = (0,0)
        self.name = "pdxasset"
        self.value = 0

    def get_binary_data(self):
        result = bytearray()

        result.extend(struct.pack("cb" + str(len(self.name)) + "s", b'!', len(self.name), self.name.encode('UTF-8')))
        result.extend(struct.pack("cb", b'i', 2))
        result.extend(struct.pack(">iibbb", 1, 0, 0, 0, 0))

        print(result)
        return result

class PdxMesh():
    def __init__(self):
        self.meshBounds = None
        self.verts = []
        self.faces = []
        self.tangents = []
        self.normals = []
        self.uv_coords = []
        self.material = None

    def get_binary_data(self):
        result = bytearray()

        result.extend(struct.pack("7sb", b'[[[mesh', 0))
        result.extend(struct.pack("cb2sI", b'!', 1, b'pf', len(self.verts) * 3))

        for i in range(0, len(self.verts)):
            result.extend(struct.pack("fff", self.verts[i][0], self.verts[i][1], self.verts[i][2]))

        result.extend(struct.pack("cb2sI", b'!', 1, b'nf', len(self.normals) * 3))

        for i in range(0, len(self.normals)):
            result.extend(struct.pack("fff", self.normals[i][0], self.normals[i][1], self.normals[i][2]))

        result.extend(struct.pack("cb3s", b'!', 2, b'taf'))
        result.extend(struct.pack("I", len(self.tangents) * 4))

        print(len(self.tangents) * 4)

        for i in range(0, len(self.tangents)):
            for j in range(0, 4):
                result.extend(struct.pack("f", self.tangents[i][j]))
            

        result.extend(struct.pack("cb3s", b'!', 2, b'u0f'))
        result.extend(struct.pack("I", len(self.uv_coords) * 2))

        for i in range(0, len(self.uv_coords)):
            result.extend(struct.pack("f", self.uv_coords[i][0]))
            result.extend(struct.pack("f", self.uv_coords[i][1]))

        print("UV-Map-Export: " + str(len(self.uv_coords)))

        result.extend(struct.pack("cb4s", b'!', 3, b'trii'))
        result.extend(struct.pack("I", len(self.faces) * 3))

        for i in range(0, len(self.faces)):
            result.extend(struct.pack("III", self.faces[i][0],  self.faces[i][1],  self.faces[i][2]))

        result.extend(self.meshBounds.get_binary_data())
        result.extend(self.material.get_binary_data())

        return result

class PdxCollisionMesh():
    def __init__(self):
        self.meshBounds = None
        self.verts = []
        self.faces = []
        self.material = None

    def get_binary_data(self):
        result = bytearray()

        result.extend(struct.pack("7sb", b'[[[mesh', 0))
        result.extend(struct.pack("cb2sI", b'!', 1, b'pf', len(self.verts) * 3))

        for i in range(0, len(self.verts)):
            result.extend(struct.pack("fff", self.verts[i][0], self.verts[i][1], self.verts[i][2]))

        result.extend(struct.pack("cb4s", b'!', 3, b'trii'))
        result.extend(struct.pack("I", len(self.faces) * 3))

        for i in range(0, len(self.faces)):
            result.extend(struct.pack("III", self.faces[i][0],  self.faces[i][1],  self.faces[i][2]))

        result.extend(self.meshBounds.get_binary_data())
        result.extend(self.material.get_binary_data())

        return result

class PdxMaterial():
    def __init__(self):
        self.shaders = ""
        self.diffs = ""
        self.normals = ""
        self.specs = ""

    def get_binary_data(self):
        result = bytearray()

        result.extend(struct.pack("12sb", b'[[[[material', 0))
        result.extend(struct.pack("cb7s", b'!', 6, b'shaders'))
        result.extend(struct.pack("II", 1, len(self.shaders) + 1))
        result.extend(struct.pack(str(len(self.shaders)) + "sb", self.shaders.encode("UTF-8"), 0))
        
        result.extend(struct.pack("cb5s", b'!', 4, b'diffs'))
        result.extend(struct.pack("II", 1, len(self.diffs) + 1))
        result.extend(struct.pack(str(len(self.diffs)) + "sb", self.diffs.encode("UTF-8"), 0))
        
        result.extend(struct.pack("cb2s", b'!', 1, b'ns'))
        result.extend(struct.pack("II", 1, len(self.normals) + 1))
        result.extend(struct.pack(str(len(self.normals)) + "sb", self.normals.encode("UTF-8"), 0))

        result.extend(struct.pack("cb5s", b'!', 4, b'specs'))
        result.extend(struct.pack("II", 1, len(self.specs) + 1))
        result.extend(struct.pack(str(len(self.specs)) + "sb", self.specs.encode("UTF-8"), 0))

        return result

class PdxCollisionMaterial():
    def __init__(self):
        self.shaders = "Collision"

    def get_binary_data(self):
        result = bytearray()

        result.extend(struct.pack("12sb", b'[[[[material', 0))
        result.extend(struct.pack("cb7s", b'!', 6, b'shaders'))
        result.extend(struct.pack("II", 1, len(self.shaders) + 1))
        result.extend(struct.pack(str(len(self.shaders)) + "sb", self.shaders.encode("UTF-8"), 0))

        return result

class PdxProperty():
    """Temporary class to hold the Values of a parsed Property until it gets mapped to the object"""
    def __init__(self, name, bounds):
        self.name = name
        self.bounds = bounds
        self.value = []

    def get_binary_data(self):
        return bytearray()

class PdxWorld():
    def __init__(self, objects):
        self.objects = objects

    def get_binary_data(self):
        result = bytearray()

        result.extend(struct.pack("7sb", b'[object', 0))

        for i in range(0, len(self.objects)):
            result.extend(self.objects[i].get_binary_data())
        
        return result

class PdxShape():
    def __init__(self, name):
        self.name = name
        self.mesh = None

    def get_binary_data(self):
        result = bytearray()

        result.extend(struct.pack("2s", b'[['))
        result.extend(struct.pack(str(len(self.name)) + "sb", self.name.encode('UTF-8'), 0))
        
        result.extend(self.mesh.get_binary_data())

        return result

class PdxBounds():
    def __init__(self, min, max):
        self.min = min
        self.max = max

    def get_binary_data(self):
        result = bytearray()
        
        result.extend(struct.pack("8sb", b'[[[[aabb', 0))

        result.extend(struct.pack("cb4s", b'!', 3, b'minf'))
        result.extend(struct.pack("Ifff", 3, self.min[0], self.min[1], self.min[2]))
        result.extend(struct.pack("cb4s", b'!', 3, b'maxf'))
        result.extend(struct.pack("Ifff", 3, self.max[0], self.max[1], self.max[2]))

        return result

class PdxObject():
    """Temporary object"""
    def __init__(self, name, properties, depth):
        self.name = name
        self.properties = properties
        self.depth = depth

    def get_binary_data(self):
        return bytearray()

class PdxLocators():
    def __init__(self):
        self.bounds = (0,0)
        self.locators = []

    def get_binary_data(self):
        result = bytearray()

        result.extend(struct.pack("8sb", b'[locator', 0))

        for i in range(0, len(self.locators)):
            result.extend(self.locators[i].get_binary_data())

        return result

class PdxLocator():
    def __init__(self, name, pos):
        self.bounds = (0,0)
        self.name = name
        self.pos = pos

    def get_binary_data(self):
        result = bytearray()

        result.extend(struct.pack("2s", b'[['))
        result.extend(struct.pack(str(len(self.name)) + "sb", self.name.encode('UTF-8'), 0))
        result.extend(struct.pack("cb2sifff", b'!', 1, b'pf', 3, -self.pos[0], self.pos[2], self.pos[1]))
        result.extend(struct.pack("cb2sifff", b'!', 1, b'qf', 3, 0.0, 0.0, 0.0))

        return result
    
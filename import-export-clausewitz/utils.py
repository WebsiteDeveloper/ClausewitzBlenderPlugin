import struct

class BufferReader:
    def __init__(self, buffer):
        self.buffer = buffer
        self.__offset__ = 0

    def IsEOF(self, lookaheadByteCount=0):
        return ((self.__offset__ + lookaheadByteCount) >= len(self.buffer))

    def NextInt8(self, lookahead=False):
        if lookahead:
            return self.buffer[self.__offset__]
        else:
            self.__offset__ += 1
            return self.buffer[self.__offset__ - 1]

    def NextInt32(self, lookahead=False):
        if lookahead:
            return struct.unpack_from("i", self.buffer, self.__offset__)[0]
        else:
            self.__offset__ += 4
            return struct.unpack_from("i", self.buffer, self.__offset__ - 4)[0]

    def NextUInt32(self, lookahead=False):
        if lookahead:
            return struct.unpack_from("I", self.buffer, self.__offset__)[0]
        else:
            self.__offset__ += 4
            return struct.unpack_from("I", self.buffer, self.__offset__ - 4)[0]

    def NextFloat32(self, lookahead=False):
        if lookahead:
            return struct.unpack_from("f", self.buffer, self.__offset__)[0]
        else:
            self.__offset__ += 4
            return struct.unpack_from("f", self.buffer, self.__offset__ - 4)[0]

    def NextChar(self, lookahead=False):
        if lookahead:
            return chr(self.buffer[self.__offset__])
        else:
            self.__offset__ += 1
            return chr(self.buffer[self.__offset__ - 1])

    def GetCurrentOffset(self):
        return self.__offset__

    def SetCurrentOffset(self, offset):
        self.__offset__ = offset

def PreviewObjectDepth(buffer: BufferReader, startDepth=0):
    offsetTemp = buffer.GetCurrentOffset()

    while buffer.NextChar() == "[":
        startDepth += 1

    buffer.SetCurrentOffset(offsetTemp)

    return startDepth

def ReadNullByteString(buffer: BufferReader):
    stringValue = ""
        
    char = buffer.NextChar()
        
    while char != "\x00":
        stringValue += char
        char = buffer.NextChar()

    return stringValue

def my_range(start, end, step):
    while start <= end:
        yield start
        start += step

def TranslatePropertyName(originalName: str):
    if originalName == "p":
        return "vertices"
    elif originalName == "n":
        return "normals"
    elif originalName == "ta":
        return "tangents"
    elif originalName == "u0":
        return "uv_map"
    elif originalName == "tri":
        return "faces"

    return originalName

def TransposeCoordinateArray4D(data):
    result = []

    if len(data) % 4 == 0:
        for i in my_range(0, len(data) - 4, 4):
            result.append((data[i], data[i + 1], data[i + 2], data[i + 3]))

        return result
    else:
        return result

def TransposeCoordinateArray3D(data):
    result = []

    if len(data) % 3 == 0:
        for i in my_range(0, len(data) - 3, 3):
            result.append((data[i], data[i + 1], data[i + 2]))

        return result
    else:
        return result

def TransposeCoordinateArray2D(data):
    result = []

    if len(data) % 2 == 0:
        for i in my_range(0, len(data) - 2, 2):
            result.append([data[i], data[i + 1]])

        return result
    else:
        return result
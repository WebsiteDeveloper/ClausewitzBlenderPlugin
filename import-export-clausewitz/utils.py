import struct

class BufferReader:
    def __init__(self, buffer):
        self.buffer = buffer
        self.offset = 0

    def IsEOF(self):
        return (self.offset >= len(self.buffer))

    def NextInt8(self):
        self.offset += 1
        return self.buffer[self.offset - 1]

    def NextInt32(self):
        self.offset += 4
        return struct.unpack_from("i", self.buffer, self.offset - 4)[0]

    def NextUInt32(self):
        self.offset += 4
        return struct.unpack_from("I", self.buffer, self.offset - 4)[0]

    def NextFloat32(self):
        self.offset += 4
        return struct.unpack_from("f", self.buffer, self.offset - 4)[0]

    def NextChar(self):
        self.offset += 1
        return chr(self.buffer[self.offset - 1])

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

def TransposeCoordinateArray(data):
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
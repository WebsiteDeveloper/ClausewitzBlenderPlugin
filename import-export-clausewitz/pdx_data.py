class PdxMesh():
    def __init__(self, name, blenderName):
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

class Locator():
    def __init__(self, name, pos):
        self.name = name
        self.pos = pos        
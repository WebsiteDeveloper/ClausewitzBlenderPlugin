import bpy
import bmesh
import os
import io
from pathlib import Path
from . import (pdx_data, tree, utils)

class PdxFileImporter:
    def __init__(self, filename):
        self.file = pdx_data.PdxFile(filename)
        self.file.read()

    def AddBlenderMesh(self):
        meshNode = self.file.dataTree.search("mesh")

        if not meshNode.hasSubNode("uv_map"):
            meshNode = meshNode.search("mesh", False)

        if self.file.filename.find("/") != -1:
            meshName = self.file.filename.rsplit("/", 1)[1].replace(".mesh", "")  #self.dataTree.rootNode.searchForParentNode(meshNode.id).name
        elif self.file.filename.find("\\") != -1:
            meshName = self.file.filename.rsplit("\\", 1)[1].replace(".mesh", "")  #self.dataTree.rootNode.searchForParentNode(meshNode.id).name
        else:
            meshName = "ClausewitzMesh"

        mesh = pdx_data.PdxMesh(meshNode.value, meshName)

        obName = mesh.blenderName + "_object"

        mesh.blenderMesh = bpy.data.meshes.new(mesh.blenderName)
        obj = bpy.data.objects.new(obName, mesh.blenderMesh)

        scn = bpy.context.scene
        scn.objects.link(obj)
        scn.objects.active = obj
        obj.select = True

        mesh.verts = utils.TransposeCoordinateArray(meshNode.search("vertices", False).value)
        mesh.faces = utils.TransposeCoordinateArray(meshNode.search("faces", False).value)
        mesh.uv_coords = utils.TransposeCoordinateArray2D(meshNode.search("uv_map", False).value)

        mesh.blenderMesh.from_pydata(mesh.verts, [], mesh.faces)
        
        bm = bmesh.new()
        bm.from_mesh(mesh.blenderMesh)

        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        bm.faces.index_update()
        
        uv_layer = bm.loops.layers.uv.new(mesh.blenderName + "_uv")
        for face in bm.faces:
            for loop in face.loops:
                loop[uv_layer].uv[0] = mesh.uv_coords[loop.vert.index][0]
                loop[uv_layer].uv[1] = 1 - mesh.uv_coords[loop.vert.index][1]

        mat = bpy.data.materials.new(name=mesh.blenderName + "Material")
        
        obj.data.materials.append(mat)
        
        tex = bpy.data.textures.new(meshName + "_text", 'IMAGE')
        tex.type = 'IMAGE'

        imageFile = Path(os.path.join(os.path.dirname(self.file.filename), meshNode.search("diff", False).value[0]))

        altImageFile = Path(os.path.join(os.path.dirname(self.file.filename), meshName + "_diffuse.dds"))
        
        if imageFile.is_file():
            imageFile.resolve()
            image = bpy.data.images.load(str(imageFile))
            tex.image = image
        elif altImageFile.is_file():
            altImageFile.resolve()
            image = bpy.data.images.load(str(altImageFile))
            tex.image = image
        else:
            print("No Texture File was found.")

        slot = mat.texture_slots.add()
        slot.texture = tex
        slot.bump_method = 'BUMP_ORIGINAL'
        slot.mapping = 'FLAT'
        slot.mapping_x = 'X'
        slot.mapping_y = 'Y'
        slot.texture_coords = 'UV'
        slot.use = True
        slot.uv_layer = uv_layer.name

        bm.to_mesh(mesh.blenderMesh)

        #Locator Add Block
        locatorNode = meshNode.search("locator", False)
        
        locators = locatorNode.subNodes[0].Flatten()
         
        for i in range(0, len(locators)):
            o = bpy.data.objects.new(locators[i].name, None)
            o.parent = obj
            bpy.context.scene.objects.link(o)
            o.empty_draw_size = 2
            o.empty_draw_type = 'PLAIN_AXES'
            o.location = (locators[i].subNodes[0].value[0], locators[i].subNodes[0].value[1], locators[i].subNodes[0].value[2])
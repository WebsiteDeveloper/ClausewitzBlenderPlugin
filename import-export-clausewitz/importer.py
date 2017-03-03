import bpy
import bmesh
import mathutils
import math
import os
import io
from pathlib import Path
from . import (pdx_data, utils)

class PdxFileImporter:
    def __init__(self, filename):
        self.file = pdx_data.PdxFile(filename)
        self.file.read()

    def import_mesh(self):
        eul = mathutils.Euler((0.0, 0.0, math.radians(180.0)), 'XYZ')
        eul2 = mathutils.Euler((math.radians(90.0), 0.0, 0.0), 'XYZ')
        mat_rot = eul.to_matrix() * eul2.to_matrix()

        shape = self.file.nodes[1].objects[0]

        mesh_name = shape.name # + "_mesh"

        mesh = bpy.data.meshes.new(mesh_name)
        obj = bpy.data.objects.new(shape.name, mesh)

        scn = bpy.context.scene
        scn.objects.link(obj)
        scn.objects.active = obj
        obj.select = True

        mesh.from_pydata(shape.mesh.verts, [], shape.mesh.faces)

        bm = bmesh.new()
        bm.from_mesh(mesh)

        for vert in bm.verts:
            vert.co = vert.co * mat_rot

        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        bm.faces.index_update()

        uv_layer = bm.loops.layers.uv.new(shape.name + "_uv")
        for face in bm.faces:
            for loop in face.loops:
                loop[uv_layer].uv[0] = shape.mesh.uv_coords[loop.vert.index][0]
                loop[uv_layer].uv[1] = 1 - shape.mesh.uv_coords[loop.vert.index][1]

        mat = bpy.data.materials.new(name=shape.name + "_material")
        
        obj.data.materials.append(mat)

        tex = bpy.data.textures.new(shape.name + "_tex", 'IMAGE')
        tex.type = 'IMAGE'

        img_file = Path(os.path.join(os.path.dirname(self.file.filename), shape.mesh.material.diffs))
        altImageFile = Path(os.path.join(os.path.dirname(self.file.filename), os.path.basename(self.file.filename).replace(".mesh", "") + "_diffuse.dds"))

        if img_file.is_file():
            img_file.resolve()
            image = bpy.data.images.load(str(img_file))
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

        bm.to_mesh(mesh)

        #Locator Add Block
        locators_obj = self.file.nodes[1].objects[1]

        locators = locators_obj.locators
         
        for i in range(0, len(locators)):
            o = bpy.data.objects.new(locators[i].name, None)
            o.parent = obj
            bpy.context.scene.objects.link(o)
            o.empty_draw_size = 2
            o.empty_draw_type = 'PLAIN_AXES'
            o.location = mathutils.Vector((locators[i].pos[0], locators[i].pos[1], locators[i].pos[2])) * mat_rot

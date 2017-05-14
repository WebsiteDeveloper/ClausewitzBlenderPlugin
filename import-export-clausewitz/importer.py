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
        print("------------------------------------")
        print("Importing: " + filename + "\n\n\n\n\n")
        self.file = pdx_data.PdxFile(filename)
        self.file.read()

    def import_mesh(self):
        eul = mathutils.Euler((0.0, 0.0, math.radians(180.0)), 'XYZ')
        eul2 = mathutils.Euler((math.radians(90.0), 0.0, 0.0), 'XYZ')
        mat_rot = eul.to_matrix() * eul2.to_matrix()

        for node in self.file.nodes:
            if isinstance(node, pdx_data.PdxAsset):
                print("Importer: PDXAsset")#TODOs
            elif isinstance(node, pdx_data.PdxWorld):
                for shape in node.objects:
                    if isinstance(shape, pdx_data.PdxShape):
                        name = shape.name

                        for shapeObject in shape.objects:
                            if isinstance(shapeObject, pdx_data.PdxMesh):
                                mesh = bpy.data.meshes.new(name)
                                obj = bpy.data.objects.new(name, mesh)
                                
                                scn = bpy.context.scene
                                scn.objects.link(obj)
                                scn.objects.active = obj
                                obj.select = True
                                
                                mesh.from_pydata(shapeObject.verts, [], shapeObject.faces)

                                bm = bmesh.new()
                                bm.from_mesh(mesh)

                                for vert in bm.verts:
                                    vert.co = vert.co * mat_rot

                                bm.verts.ensure_lookup_table()
                                bm.verts.index_update()
                                bm.faces.index_update()

                                if shapeObject.material.shader == "Collision":
                                    obj.draw_type = "WIRE"
                                else:
                                    uv_layer = bm.loops.layers.uv.new(name + "_uv")

                                    for face in bm.faces:
                                        for loop in face.loops:
                                            loop[uv_layer].uv[0] = shapeObject.uv_coords[loop.vert.index][0]
                                            loop[uv_layer].uv[1] = 1 - shapeObject.uv_coords[loop.vert.index][1]

                                    mat = bpy.data.materials.new(name=name + "_material")
                                    obj.data.materials.append(mat)

                                    tex = bpy.data.textures.new(shape.name + "_tex", 'IMAGE')
                                    tex.type = 'IMAGE'

                                    img_file = Path(os.path.join(os.path.dirname(self.file.filename), shapeObject.material.diffs))
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
                            elif isinstance(shapeObject, pdx_data.PdxSkeleton):
                                print("Importer: PdxSkeleton")
                                amt = bpy.data.armatures.new(name)
                                obj = bpy.data.objects.new(name, amt)

                                scn = bpy.context.scene
                                scn.objects.active = obj
                                obj.select = True

                                names = [""] * len(shapeObject.joints)

                                for joint in shapeObject.joints:
                                    print(joint.index)
                                    names[joint.index] = joint.name

                                bpy.ops.object.mode_set(mode='EDIT')

                                for joint in shapeObject.joints:
                                    bone = amt.edit_bones.new(joint.name)

                                    if joint.parent >= 0:
                                        parent = parent = amt.edit_bones[names[joint.index]]
                                        bone.parent = parent
                                        bone.head = parent.tail
                                        bone.use_connect = False
                                    else:         
                                        bone.head = (0,0,0)

                                    bone.tail = (0, 0, 0)
                            else:
                                print("ERROR ::: Invalid Object in Shape: " + str(shapeObject))
                    else:
                        print("ERROR ::: Invalid Object in World: " + str(shape))
            elif isinstance(node, pdx_data.PdxLocators):
                for locator in node.locators:
                    obj = bpy.data.objects.new(locator.name, None)
                    bpy.context.scene.objects.link(obj)
                    obj.empty_draw_size = 2
                    obj.empty_draw_type = 'PLAIN_AXES'
                    obj.location = mathutils.Vector((locator.pos[0], locator.pos[1], locator.pos[2])) * mat_rot
            else:
                print("ERROR ::: Invalid node found: " + str(node))
import bpy
import bmesh
import mathutils
import math
import os
import io
import random
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
        mat_rot.resize_4x4()

        for node in self.file.nodes:
            if isinstance(node, pdx_data.PdxAsset):
                print("Importer: PDXAsset")#TODOs
                print("PDXAsset Version " + str(node.version[0]) + "." + str(node.version[1]))
            elif isinstance(node, pdx_data.PdxWorld):
                for shape in node.objects:
                    bpy.ops.object.select_all(action='DESELECT')
                    if isinstance(shape, pdx_data.PdxShape):
                        name = shape.name

                        mesh = bpy.data.meshes.new(name)
                        obj = bpy.data.objects.new(name, mesh)
                        
                        scn = bpy.context.scene
                        scn.objects.link(obj)
                        scn.objects.active = obj
                        obj.select = True

                        collisionShape = False

                        if isinstance(shape.skeleton, pdx_data.PdxSkeleton):
                            amt = bpy.data.armatures.new(name)
                            amtObj = bpy.data.objects.new(name, amt)
                            amtObj.parent = obj
                                
                            scn = bpy.context.scene
                            scn.objects.link(amtObj)
                            scn.objects.active = amtObj
                            amtObj.select = True
                            
                            names = [""] * len(shape.skeleton.joints)

                            for joint in shape.skeleton.joints:
                                names[joint.index] = joint.name

                            bpy.ops.object.mode_set(mode='EDIT')
                            
                            for joint in shape.skeleton.joints:
                                bone = amt.edit_bones.new(joint.name)

                                transformationMatrix = mathutils.Matrix()
                                transformationMatrix[0][0:4] = joint.transform[0], joint.transform[3], joint.transform[6], joint.transform[9]
                                transformationMatrix[1][0:4] = joint.transform[1], joint.transform[4], joint.transform[7], joint.transform[10]
                                transformationMatrix[2][0:4] = joint.transform[2], joint.transform[5], joint.transform[8], joint.transform[11]
                                transformationMatrix[3][0:4] = 0, 0, 0, 1

                                #print(transformationMatrix.decompose())

                                if joint.parent >= 0:
                                    parent = amt.edit_bones[names[joint.parent]] 
                                    bone.parent = parent
                                    bone.use_connect = True 
                                else:          
                                    bone.head = (0,0,0)

                                temp_transform = transformationMatrix #.inverted()
                                components = temp_transform.decompose()

                                mat_temp = components[1].to_matrix()
                                mat_temp.resize_4x4()

                                bone.tail = -components[0] * mat_temp * mat_rot
                            bpy.ops.object.mode_set(mode='OBJECT')

                        for meshData in shape.meshes:
                            if isinstance(meshData, pdx_data.PdxMesh):
                                sub_mesh = bpy.data.meshes.new(name)
                                sub_object = bpy.data.objects.new(name, sub_mesh)

                                scn = bpy.context.scene
                                scn.objects.link(sub_object)
                                scn.objects.active = sub_object
                                sub_object.select = True

                                sub_mesh.from_pydata(meshData.verts, [], meshData.faces)

                                bm = bmesh.new()
                                bm.from_mesh(sub_mesh)

                                for vert in bm.verts:
                                    vert.co = vert.co * mat_rot

                                bm.verts.ensure_lookup_table()
                                bm.verts.index_update()
                                bm.faces.index_update()

                                if meshData.material.shader == "Collision":
                                    collisionShape = True
                                else:
                                    uv_layer = bm.loops.layers.uv.new(name + "_uv")

                                    for face in bm.faces:
                                        for loop in face.loops:
                                            loop[uv_layer].uv[0] = meshData.uv_coords[loop.vert.index][0]
                                            loop[uv_layer].uv[1] = 1 - meshData.uv_coords[loop.vert.index][1]

                                    mat = bpy.data.materials.new(name=name + "_material")
                                    mat.diffuse_color = (random.random(), random.random(), random.random())
                                    sub_object.data.materials.append(mat)

                                    tex = bpy.data.textures.new(shape.name + "_tex", 'IMAGE')
                                    tex.type = 'IMAGE'

                                    img_file = Path(os.path.join(os.path.dirname(self.file.filename), meshData.material.diff))
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

                                bm.to_mesh(sub_mesh)
                            else:
                                print("ERROR ::: Invalid Object in Shape: " + str(meshData))

                        scn.objects.active = obj
                        bpy.ops.object.join()

                        if collisionShape:
                            obj.draw_type = "WIRE"

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
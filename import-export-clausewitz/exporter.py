from pathlib import Path
import os
import io
import math

import bpy
import bmesh
import mathutils
from . import (pdx_data, utils)

class PdxFileExporter:
    """File Exporter Class"""
    def __init__(self, filename):
        self.filename = filename

    def export_mesh(self, name):
        objects = []

        eul = mathutils.Euler((0.0, 0.0, math.radians(180.0)), 'XYZ')
        eul2 = mathutils.Euler((math.radians(90.0), 0.0, 0.0), 'XYZ')
        mat_rot = eul.to_matrix() * eul2.to_matrix()
        mat_rot.invert_safe()

        transform_mat = bpy.data.objects[name].matrix_world * mat_rot.to_4x4()

        objects.append(pdx_data.PdxAsset())

        world = pdx_data.PdxWorld([])

        if name.endswith("MeshShape"):
            shape = pdx_data.PdxShape(name)
        else:
            shape = pdx_data.PdxShape(name + ":MeshShape")

        mesh = pdx_data.PdxMesh()
        shape.mesh = mesh

        blender_mesh = bpy.data.meshes[name]

        bm = bmesh.new()
        bm.from_mesh(blender_mesh)
        bmesh.ops.triangulate(bm, faces=bm.faces)

        for vert in bm.verts:
            vert.co = vert.co * transform_mat

        bm.verts.index_update()
        bm.faces.index_update()
        bm.verts.ensure_lookup_table()

        normals = []
        verts = []
        tangents = []

        for i in range(0, len(bm.verts)):
            verts.append(bm.verts[i].co)
            bm.verts[i].normal_update()
            normal_temp = bm.verts[i].normal
            normal_temp.normalize()
            normals.append(normal_temp)

        bm.faces.ensure_lookup_table()

        for i in range(0, len(bm.verts)):
            tangents.append((0.0, 0.0, 0.0, 0.0))

        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        bm.faces.index_update()

        uv_coords = []
        uv_layer = bm.loops.layers.uv.active

        for face in bm.faces:
            for loop in face.loops:
                uv_coords.append((0, 0))

        for face in bm.faces:
            for loop in face.loops:
                uv_coords[loop.vert.index] = loop[uv_layer].uv
                uv_coords[loop.vert.index][1] = 1 - uv_coords[loop.vert.index][1]

        max_index = 0

        #Trim data, remove empty bytes
        for i in range(0, len(uv_coords)):
            #print(uv_coords[i])
            if uv_coords[i][0] == 0.0 and uv_coords[i][1] == 0.0:
                max_index = i - 1
                break

        del uv_coords[max_index:(len(uv_coords) - 1)]

        faces = []

        for face in bm.faces:
            temp = []

            for loop in face.loops:
                temp.append(loop.vert.index)

            faces.append(temp)

        mesh.verts = verts
        mesh.normals = normals
        mesh.tangents = tangents
        mesh.uv_coords = uv_coords
        mesh.faces = faces
        mesh.meshBounds = pdx_data.PdxBounds((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        mesh.material = pdx_data.PdxMaterial()

        diff_file = ""

        if len(bpy.data.objects[name].material_slots) > 0:
            for mat_slot in bpy.data.objects[name].material_slots:
                for mtex_slot in mat_slot.material.texture_slots:
                    if mtex_slot:
                        if hasattr(mtex_slot.texture, 'image'):
                            if mtex_slot.texture.image is None:
                                bpy.ops.error.message('INVOKE_SCREEN',
                                                      message="The Texture Image file is not loaded")
                            else:
                                diff_file = os.path.basename(mtex_slot.texture.image.filepath)
        else:
            diff_file = os.path.basename(bpy.data.meshes[name].uv_textures[0].data[0].image.filepath)

        mesh.material.shaders = "PdxMeshShip"
        mesh.material.diffs = diff_file
        mesh.material.specs = "test_spec"
        mesh.material.normals = "test_normal"

        locators_array = []

        for i in range(0, len(bpy.data.objects)):
            if bpy.data.objects[i].type == 'EMPTY':
                temp = pdx_data.PdxLocator(bpy.data.objects[i].name, bpy.data.objects[i].location)
                locators_array.append(temp)

        locators = pdx_data.PdxLocators()
        locators.locators = locators_array

        world.objects.append(shape)
        world.objects.append(locators)
        objects.append(world)

        result_file = io.open(self.filename, 'wb')

        result_file.write(b'@@b@')
        for i in range(0, len(objects)):
            result_file.write(objects[i].get_binary_data())

        result_file.close()

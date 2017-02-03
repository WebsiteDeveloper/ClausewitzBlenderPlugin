import bpy
import bmesh
import os
import io
from pathlib import Path
from . import (pdx_data, utils)

class PdxFileExporter:
    def __init__(self, filename):
        self.filename = filename

    def export_mesh(self, name):
        objects = []
        
        objects.append(pdx_data.PdxAsset())
        
        world = pdx_data.PdxWorld([])
        shape = pdx_data.PdxShape(name)

        mesh = pdx_data.PdxMesh()
        shape.mesh = mesh

        blender_mesh = bpy.data.meshes[name]

        bm = bmesh.new()
        bm.from_mesh(blender_mesh)
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        bm.faces.index_update()
        bm.verts.ensure_lookup_table()

        normals = []
        verts = []
        tangents = []

        for i in range(0, len(bm.verts)):
            verts.append(bm.verts[i].co)
            bm.verts[i].normal_update()

            normals.append(bm.verts[i].normal)

        bm.faces.ensure_lookup_table()

        for i in range(0, len(bm.faces)):
            tangents.append(bm.faces[i].calc_tangent_edge_pair().to_4d())
            tangents.append(bm.faces[i].calc_tangent_edge_pair().to_4d())
            tangents.append(bm.faces[i].calc_tangent_edge_pair().to_4d())

        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        bm.faces.index_update()

        print("Edges: " + str(len(bm.edges)))

        uv_coords = []
        uv_layer = bm.loops.layers.uv.active

        for face in bm.faces:
            for loop in face.loops:
                uv_coords.append((0,0))

        for face in bm.faces:
            for loop in face.loops:
                uv_coords[loop.vert.index] = loop[uv_layer].uv

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
        mesh.material = pdx_data.PdxMaterial()

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

        f = io.open(self.filename, 'wb')

        f.write(b'@@b@')
        for i in range(0, len(objects)):
            f.write(objects[i].get_binary_data())

        f.close()
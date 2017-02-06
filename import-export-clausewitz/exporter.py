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
            bm.verts[i].normal.normalize()
            normals.append((0.0, 0.0, 0.0)) #bm.verts[i].normal)
            #print(bm.verts[i].normal[0], " - ", bm.verts[i].normal[1], " - ", bm.verts[i].normal[2])

        bm.faces.ensure_lookup_table()

        for i in range(0, len(bm.verts)):
            tangents.append((0.0, 0.0, 0.0, 0.0))
        #for face in bm.faces:
        #    for loop in face.loops:
        #         tangents.append((0.0, 0.0, 0.0, 0.0))

        #for i in range(0, len(bm.faces)):
         #   tangents.append((0.0, 0.0, 0.0, 0.0)) #bm.faces[i].calc_tangent_edge_pair().to_4d())
            #tangents.append(bm.faces[i].calc_tangent_edge_pair().to_4d())
            #tangents.append(bm.faces[i].calc_tangent_edge_pair().to_4d())

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
                uv_coords[loop.vert.index][1] = 1 - uv_coords[loop.vert.index][1]

        max_index = 0

        print(len(uv_coords))

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

        for mat_slot in bpy.data.objects[name].material_slots:
            for mtex_slot in mat_slot.material.texture_slots:
                if mtex_slot:
                    if hasattr(mtex_slot.texture , 'image'):
                        print(mtex_slot.texture.name)
                        diff_file = os.path.split(mtex_slot.texture.image.filepath)[1]

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

        f = io.open(self.filename, 'wb')

        f.write(b'@@b@')
        for i in range(0, len(objects)):
            f.write(objects[i].get_binary_data())

        f.close()
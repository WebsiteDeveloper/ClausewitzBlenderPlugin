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

        verts = []

        for i in range(0, len(bm.verts)):
            verts.append(bm.verts[i].co)
            print(bm.verts[i].co)

        mesh.verts = verts


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
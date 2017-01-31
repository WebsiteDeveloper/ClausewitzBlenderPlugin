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

        world.objects.append(shape)
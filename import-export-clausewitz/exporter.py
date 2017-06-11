from pathlib import Path
import os
import io
import math
import mathutils

import bpy
import bmesh

from . import (pdx_data, utils)

class PdxFileExporter:
    """File Exporter Class"""
    def __init__(self, filename):
        self.filename = filename

    def get_skinning_data(self, obj, bone_ids):
        utils.Log.info("Getting Skin Data...")
        #Skin Data Layout:  { VertexIndex: [ {BoneIndex: Weight}, ... ], ... }
        blender_skin = {}

        for index, vertex in enumerate(obj.data.vertices):
            skinning_data_for_vertex = []

            for group in vertex.groups:
                if obj.vertex_groups[group.group].name in bone_ids:
                    skinning_data_for_vertex.append({bone_ids[obj.vertex_groups[group.group].name]: group.weight})

            blender_skin[index] = skinning_data_for_vertex
            #utils.Log.debug(blender_skin)

        bones_per_vertex = 4
        #Bones Per Vertex for now constant 4
        #for i in blender_skin:
        #   bones_per_vertex = max(len(blender_skin[i]), bones_per_vertex)
        #
        #utils.Log.debug("BPV: " + str(bones_per_vertex))

        return {'blender_skin': blender_skin, 'bones_per_vertex': 4}

    def get_material_list(self, obj):
        materials = {}

        utils.Log.info("Collecting Materials...")
        for mat_slot in obj.material_slots:
            material = mat_slot.material
            if material is not None:
                materials[len(materials)] = material.name
        
        return materials

    def get_Skin(self, skin_data):
        skin = None

        if skin_data is not None:
            skin = pdx_data.PdxSkin()
            indices = []
            weights = []

            for index, data in skin_data['blender_skin'].items():
                if index not in stray_vertices_indices:
                    temp_indices = [-1] * skin_data['bones_per_vertex']
                    temp_weights = [0] * skin_data['bones_per_vertex']

                    for i in range(0, len(data)):
                        temp_indices[i] = next(iter(data[i].keys()))
                        temp_weights[i] = data[i][temp_indices[i]]

                    indices.extend(temp_indices)
                    weights.extend(temp_weights)

            skin.bonesPerVertice = skin_data['bones_per_vertex']
            skin.indices = indices
            skin.weight = weights

            utils.Log.debug(len(skin.indices))
            utils.Log.debug(len(skin.weight))

        return skin

    #Exports one face into the global arrays
    def handle_BMesh_Face(self, face):
        #Indices of the Face
        indices = []

        for v in face.verts:
            #Calculate Vertex Position
            vert = v.co * self.transform_mat

            # TODO Auto Edge Split on sharp Edges (For now in workflow before Export)
            #Caluculate Normal Vector (Depending on Face smoothness)
            if face.smooth:
                normal = v.normal * self.transform_mat
            else:
                normal = face.normal * self.transform_mat
            normal.normalize()

            #Caluculate Tangent Vector
            tangent = v.link_faces[0].calc_tangent_vert_diagonal().to_4d() * self.transform_mat

            #Getting all UV Layers
            loops = face.loops

            #Caluculate UV Vector
            for loop in loops:
                if loop.vert == v:
                    uv = loop[self.uv_active].uv.copy()
                    uv[1] = 1 - uv[1]

            #Round Values (because of the compare)
            for i in range(2):
                uv[i] = round(uv[i], 6)
            for i in range(3):
                vert[i] = round(vert[i], 6)
                normal[i] = round(normal[i], 6)
            for i in range(4):
                tangent[i] = round(tangent[i], 6)

            #Freezing the vectors so they can be hashed
            vert.freeze()
            utils.Log.debug("Vert: " + str(vert))
            normal.freeze()
            utils.Log.debug("Normal: " + str(normal))
            tangent.freeze()
            utils.Log.debug("Tangent: " + str(tangent))
            uv.freeze()
            utils.Log.debug("UV: " + str(uv))

            #Reading old Vertex-Index from indexMap
            oldIndex = self.indexMap.get((vert,normal,tangent,uv))

            #Checking if Vertex already exists
            if oldIndex is not None:
                #Vertex exists -> Old index is used
                utils.Log.debug("Old Index: " + str(oldIndex))

                indices.append(oldIndex)
            else:
                #Vertex does not yet exist
                index = len(self.verts)
                utils.Log.debug("New Index: " + str(index))

                indices.append(index)

                self.verts.append(vert)
                self.normals.append(normal)
                self.tangents.append(tangent)
                self.uv_coords.append(uv)

                #Needed for Speed
                self.indexMap[(vert,normal,tangent,uv)] = index

        #Face should be Triangulated, but if not it ignores the face and continues
        if len(indices) == 3:
            self.faces.append((indices[0], indices[1], indices[2]))
        else:
            #TODO Auto-Triangulation (Recursive Algorithm)
            utils.Log.critical("Face has " + str(len(indices)) + " vertices!")

    #Exports one BMesh into X PdxMeshes (Splitted on Material and Size)
    def splitMeshes(self, obj, boneIDs=None):
        utils.Log.info("Exporting \"" + obj.name + "\"!")

        #Array of splitted PdxMeshes
        result_meshes = []

        #Raw Blender Mesh
        mesh = obj.data

        #Skinnning Data
        if boneIDs != None:
            skin_data = self.get_skinning_data(obj, boneIDs)

        #Material List (for splitting along them)
        materials = self.get_material_list(obj)

        #Base Bmesh Generation
        bMesh = bmesh.new()
        bMesh.from_mesh(mesh)

        bMesh.faces.ensure_lookup_table()
        bMesh.verts.ensure_lookup_table()
        bMesh.verts.index_update()
        bMesh.faces.index_update()

        bpy.context.window_manager.progress_begin(0, len(bMesh.faces))
        #Handling all Materials Seperate for Export
        for index,material in materials.items():
            bm = bMesh.copy()
            utils.Log.info("Compiling Mesh for Material \"" + material + "\"!")

            self.verts = []
            self.faces = []

            self.normals = []
            self.tangents = []
            self.uv_coords = []

            self.indexMap = {}

            bm.verts.index_update()
            bm.faces.index_update()
            bm.verts.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            self.uv_active = bm.loops.layers.uv.active

            for face in bm.faces:
                if face.material_index == index:
                    self.handle_BMesh_Face(face)
                bpy.context.window_manager.progress_update(len(self.faces))

            utils.Log.info("Vert: " + str(len(self.verts)))
            utils.Log.info("Norm: " + str(len(self.normals)))
            utils.Log.info("Tang: " + str(len(self.tangents)))
            utils.Log.info("Text: " + str(len(self.uv_coords)))
            utils.Log.info("Face: " + str(len(self.faces)))

            bb_min = [math.inf, math.inf, math.inf]
            bb_max = [-math.inf, -math.inf, -math.inf]

            for i in range(len(self.verts)):
                for j in range(3):
                    bb_min[j] = min([self.verts[i][j], bb_min[j]])
                    bb_max[j] = max([self.verts[i][j], bb_max[j]])

            utils.Log.info("Generating PdxMeshes...")

            result_mesh = pdx_data.PdxMesh()

            result_mesh.verts = self.verts
            result_mesh.faces = self.faces

            result_mesh.normals = self.normals
            result_mesh.tangents = self.tangents
            result_mesh.uv_coords = self.uv_coords

            if boneIDs != None:
                result_mesh.skin = self.get_Skin(self, skin_data)
            result_mesh.meshBounds = pdx_data.PdxBounds(bb_min, bb_max)
            result_mesh.material = pdx_data.PdxMaterial()

            diff_file = "test_diff"

            if len(obj.material_slots) > 0:
                mat = obj.material_slots[material].material

                for mtex_slot in mat.texture_slots:
                    if mtex_slot:
                        if hasattr(mtex_slot.texture, 'image'):
                            if mtex_slot.texture.image is None:
                                utils.Log.warning("Texture Image File not loaded")
                            else:
                                diff_file = os.path.basename(mtex_slot.texture.image.filepath)
            else:
                diff_file = os.path.basename(mesh.uv_textures[0].data[0].image.filepath)

            result_mesh.material.shader = "PdxMeshShip"
            result_mesh.material.diff = diff_file
            result_mesh.material.spec = diff_file.replace("diff", "spec")
            result_mesh.material.normal = diff_file.replace("diff", "normal")

            result_meshes.append(result_mesh)

            utils.Log.info("Cleaning up BMesh...")
            bm.free()

        bpy.context.window_manager.progress_end()
        utils.Log.info("Return resulting Meshes...")
        return result_meshes

    def export_mesh(self):
        #Rotation Matrix to Transform from Y-Up Space to Z-Up Space
        mat_rot = mathutils.Matrix.Rotation(math.radians(90.0), 4, 'X')

        pdxObjects = []
        pdxObjects.append(pdx_data.PdxAsset())

        pdxLocators = pdx_data.PdxLocators()
        pdxWorld = pdx_data.PdxWorld()

        for obj in bpy.data.objects:
            self.transform_mat = obj.matrix_world * mat_rot
            if obj.select:
                if obj.type == "MESH":
                    if obj.parent is None:
                        pdxShape = pdx_data.PdxShape(obj.name)

                        pdxShape.meshes = self.splitMeshes(obj)
                        pdxWorld.objects.append(pdxShape)
                elif obj.type == "ARMATURE":
                    if obj.parent is None:
                        #Highly Inefficient for now
                        for child in bpy.data.objects:
                            if child.parent == obj:
                                pdxSkeleton = pdx_data.PdxSkeleton()

                                boneIDs = {}

                                for i in range(len(obj.data.bones)):
                                    bone = obj.data.bones[i]
                                    boneIDs[bone.name] = i

                                for i in range(len(obj.data.bones)):
                                    bone = obj.data.bones[i]
                                    utils.Log.info("Joint: " + bone.name)
                                    utils.Log.info(str(boneIDs[bone.name]))
                                    pdxJoint = pdx_data.PdxJoint(bone.name)
                                    pdxJoint.index = boneIDs[bone.name]
                                    if bone.parent is not None:
                                        utils.Log.info("Parent: " + str(bone.parent))
                                        utils.Log.info("Parent ID: " + str(boneIDs[bone.parent.name]))
                                        pdxJoint.parent = boneIDs[bone.parent.name]
                                    else:
                                        utils.Log.info("Root Bone")

                                    #WIP
                                    pdxJoint.transform = [1, 0, 0, 0, 1, 0, 0, 0, 1, bone.tail[0], bone.tail[1], bone.tail[2]]

                                    pdxSkeleton.joints.append(pdxJoint)

                                pdxShape = pdx_data.PdxShape(obj.name)
                                pdxShape.skeleton = pdxSkeleton

                                pdxShape.meshes = self.splitMeshes(obj)
                                pdxWorld.objects.append(pdxShape)
                elif obj.type == "EMPTY":
                    if obj.parent is not None and obj.parent.name.lower() == "locators":
                        location = obj.location * self.transform_mat
                        location = (-location[0], location[1], -location[2])
                        locator = pdx_data.PdxLocator(obj.name, location)
                        obj.rotation_mode = 'QUATERNION'
                        locator.quaternion = obj.rotation_quaternion
                        #TODO locator.parent

                        pdxLocators.locators.append(locator)
                else:
                    utils.Log.info("Exporter: Invalid Type Selected: " + obj.type)

        pdxObjects.append(pdxWorld)

        if len(pdxLocators.locators) > 0:
            pdxObjects.append(pdxLocators)

        result_file = io.open(self.filename, 'w+b')

        result_file.write(b'@@b@')

        for i in range(len(pdxObjects)):
            result_file.write(pdxObjects[i].get_binary_data())

        result_file.close()
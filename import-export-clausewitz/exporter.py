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
        materials = []
        faces_for_materials = {}

        utils.Log.info("Collecting Materials...")
        for mat_slot in obj.material_slots:
            if mat_slot.material is not None:
                faces_for_materials[mat_slot.material.name] = []
                materials.append(mat_slot.material.name)

        utils.Log.debug(faces_for_materials)

        utils.Log.info("Getting Faces for Materials...")
        for face in obj.data.polygons:
            mat = None

            if len(obj.material_slots) != 0:
                slot = obj.material_slots[face.material_index]
                mat = slot.material

            if mat is not None:
                faces_for_materials[mat.name].append(face.index)
            else:
                utils.Log.notice("No Custom Material for Face: " + str(face.index) + " in Slot: " + str(face.material_index))
                faces_for_materials["Default"].append(face.index)

        return {'materials': materials, 'faces_for_materials': faces_for_materials}

    def get_bmesh_data_for_material(self, bm_complete, material_list, materials, selected_material, skin_data):
        removed_count = 0
        skin = None

        temp = bm_complete.copy()

        stray_vertices = []
        stray_vertices_indices = []

        temp.faces.ensure_lookup_table()
        temp.verts.ensure_lookup_table()
        temp.verts.index_update()
        temp.faces.index_update()

        utils.Log.info("Removing Faces...")

        materials.remove(selected_material)

        for remove_material in materials:
            for index in material_list['faces_for_materials'][remove_material]:
                temp.faces.remove(temp.faces[index - removed_count])
                temp.faces.ensure_lookup_table()
                removed_count += 1

        for vert in temp.verts:
            if len(vert.link_faces) == 0:
                stray_vertices.append(vert)
                stray_vertices_indices.append(vert.index)

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

        utils.Log.info("Remove Stray Vertices...")

        for vert in stray_vertices:
            temp.verts.remove(vert)
            temp.verts.ensure_lookup_table()

        return {'mesh': temp, 'skin': skin, 'material': selected_material}

    def handle_BMesh_Face(self, face):

        indices = []
        usedVertices = [] #For Speed

        for v in face.verts:

            vert = v.co * self.transform_mat
            #utils.Log.info("VC: " + str(v.co))

            #TODO Auto Edge Split on sharp Edges (For now in workflow before Export)
            if face.smooth:
                normal = v.normal * self.transform_mat
            else:
                normal = face.normal * self.transform_mat
            normal.normalize()

            for i in range(3):
                vert[i] = round(vert[i], 6)
                normal[i] = round(normal[i], 6)

            vert.freeze()
            #utils.Log.info("Vert: " + str(vert))
            normal.freeze()
            #utils.Log.info("Normal: " + str(normal))

            if len(v.link_faces) > 0:#For Models with stray vertices...
                tangent = v.link_faces[0].calc_tangent_vert_diagonal().to_4d() * self.transform_mat
            else:
                #This should also remove stray vertices from event getting exported!
                #Wait they are not even found because im only exporting faces! Awesome!
                utils.Log.info("Critical Error: Face has an Vertex without faces!")
                continue

            for i in range(4):
                tangent[i] = round(tangent[i], 6)

            tangent.freeze()
            #utils.Log.info("Tangent: " + str(tangent))

            for loop in v.link_loops:
                if loop.face != face:
                    continue

                uv = loop[self.uv_active].uv.copy()
                uv[1] = 1 - uv[1]

                for i in range(2):
                    uv[i] = round(uv[i], 6)

                uv.freeze()
                #utils.Log.info("UV: " + str(uv))

                oldIndex = self.indexMap.get((vert,normal,tangent,uv))

                if oldIndex is not None:
                    #utils.Log.info("Old Index: " + str(oldIndex))
                    indices.append(oldIndex)
                    continue

                index = len(self.verts)
                #utils.Log.info("New Index: " + str(index))

                if index not in indices:
                    indices.append(index)

                    self.verts.append(vert)
                    self.normals.append(normal)
                    self.tangents.append(tangent)
                    self.uv_coords.append(uv)

                    self.indexMap[(vert,normal,tangent,uv)] = index

        if len(indices) == 3:
            self.faces.append((indices[0], indices[1], indices[2]))
        else:
            utils.Log.info("Critical Error: Face has " + str(len(indices)) + " vertices!")

    #Returns Array of Pdx_Meshs
    #Takes Mesh Object
    def splitMeshes(self, obj, boneIDs=None):
        utils.Log.info("Exporting and splitting Mesh...")

        result_meshes = []
        bmeshes = []
        material_list = None
        skin_data = None

        mesh = obj.data

        utils.Log.info("Check If Mesh is Triangulated...")
        for polygon in mesh.polygons:
            if polygon.loop_total > 3:
                utils.Log.critical("Mesh is Not Triangulated...")
                return result_meshes

        if boneIDs != None:
            skin_data = self.get_skinning_data(obj, boneIDs)

        material_list = self.get_material_list(obj)

        #Base Bmesh Generation Start
        bm_complete = bmesh.new()
        bm_complete.from_mesh(mesh)

        bm_complete.faces.ensure_lookup_table()
        bm_complete.verts.ensure_lookup_table()
        bm_complete.verts.index_update()
        bm_complete.faces.index_update()
        #Base Bmesh Generation End

        utils.Log.debug(material_list['materials'])

        for material in material_list['materials']:
            #utils.Log.debug("Mat: " + material)
            utils.Log.info("Compiling Mesh...")

            self.verts = []
            self.faces = []

            self.normals = []
            self.tangents = []
            self.uv_coords = []

            self.indexMap = {}

            #TODO: Split mesh if it has more than 35000 verts (maybe check for actual Clausewitz-Engine limitation)
            bmesh_data = self.get_bmesh_data_for_material(bm_complete, material_list, list(material_list['materials']), material, skin_data)

            bm = bmesh_data['mesh']

            bm.verts.index_update()
            bm.faces.index_update()
            bm.verts.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            self.uv_active = bm.loops.layers.uv.active

            bpy.context.window_manager.progress_begin(0, len(bm.faces))
            for face in bm.faces:
                self.handle_BMesh_Face(face)
                bpy.context.window_manager.progress_update(len(self.faces))
            bpy.context.window_manager.progress_end()

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

        utils.Log.info("Return resulting Meshes...")
        return result_meshes

    def export_mesh(self, name):
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
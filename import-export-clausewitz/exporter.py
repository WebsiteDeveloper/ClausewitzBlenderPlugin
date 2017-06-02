from pathlib import Path
import os
import io
import math

import bpy
import bmesh
import mathutils

import time

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

    def handle_BMesh_Face(self, face, verts, faces, normals, tangents, uv_coords, transform_mat, uv_active):
        indices = []
        usedVertices = [] #For Speed
        print("\nExporting Face: " + str(len(faces)))

        for v in face.verts:
            vert = v.co * transform_mat
            #print("VC: " + str(v.co))

            #TODO Auto Edge Split on sharp Edges (For now in workflow before Export)
            if face.smooth:
                #print("VN: " + str(v.normal))
                normal = v.normal * transform_mat
            else:
                #print("FN: " + str(v.normal))
                normal = face.normal * transform_mat
            normal.normalize()

            for i in range(3):
                vert[i] = round(vert[i], 6)
                normal[i] = round(normal[i], 6)

            if len(v.link_faces) > 0:#For Models with stray vertices...
                tangent = v.link_faces[0].calc_tangent_vert_diagonal().to_4d() * transform_mat
            else:
                #This should also remove stray vertices from event getting exported!
                #Wait they are not even found because im only exporting faces! Awesome!
                utils.Log.info("Critical Error: Face has an Vertex without faces!")
                continue

            for loop in v.link_loops:
                if loop.face != face:
                    continue

                uv = loop[uv_active].uv.copy()
                uv[1] = 1 - uv[1]

                if vert in verts and normal in normals and tangent in tangents and uv in uv_coords:
                    #Vertice probably already exists... Need to find the index
                    #Continue when sucessfully set the index
                        
                    vExists = False
                    vIndices = [i for i, v in enumerate(verts) if v == vert]
                    nIndices = [i for i, v in enumerate(normals) if v == normal]
                    tIndices = [i for i, v in enumerate(tangents) if v == tangent]
                    uIndices = [i for i, v in enumerate(uv_coords) if v == uv]

                    for iV in vIndices:
                        if iV in nIndices and iV in tIndices and iV in uIndices:
                            if iV not in indices:
                                indices.append(iV)
                            vExists = True
                            break

                    if(vExists):
                        continue

                if len(verts) not in indices:
                    indices.append(len(verts))

                    verts.append(vert)
                    normals.append(normal)
                    tangents.append(tangent)
                    uv_coords.append(uv)

        if len(indices) == 3:
            faces.append((indices[0], indices[1], indices[2]))
        else:
            utils.Log.info("Critical Error: Face has " + str(len(indices)) + " vertices!")

    #Returns Array of Pdx_Meshs
    #Takes Mesh Object
    def splitMeshes(self, obj, transform_mat, boneIDs=None):
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

            verts = []
            faces = []

            normals = []
            tangents = []
            uv_coords = []

            #TODO: Split mesh if it has more than 35000 verts (maybe check for actual Clausewitz-Engine limitation)
            bmesh_data = self.get_bmesh_data_for_material(bm_complete, material_list, list(material_list['materials']), material, skin_data)

            bm = bmesh_data['mesh']

            bm.verts.index_update()
            bm.faces.index_update()
            bm.verts.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            uv_active = bm.loops.layers.uv.active

            for face in bm.faces:
                self.handle_BMesh_Face(face, verts, faces, normals, tangents, uv_coords, transform_mat, uv_active)

            print("Vert: " + str(len(verts)))
            print("Norm: " + str(len(normals)))
            for n in normals:
                print(n)
            print("Tang: " + str(len(tangents)))
            print("Text: " + str(len(uv_coords)))

            print("Face: " + str(len(faces)))

            bb_min = [math.inf, math.inf, math.inf]
            bb_max = [-math.inf, -math.inf, -math.inf]

            for i in range(len(verts)):
                for j in range(3):
                    bb_min[j] = min([verts[i][j], bb_min[j]])
                    bb_max[j] = max([verts[i][j], bb_max[j]])

            utils.Log.info("Generating PdxMeshes...")

            result_mesh = pdx_data.PdxMesh()

            result_mesh.verts = verts
            result_mesh.faces = faces

            result_mesh.normals = normals
            result_mesh.tangents = tangents
            result_mesh.uv_coords = uv_coords

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
            transform_mat = obj.matrix_world * mat_rot
            if obj.select:
                if obj.type == "MESH":
                    print("Found Mesh: " + obj.name)
                    if obj.parent is None:
                        pdxShape = pdx_data.PdxShape(obj.name)
                        pdxShape.meshes = self.splitMeshes(obj, transform_mat)
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
                                    print("Joint: " + bone.name)
                                    print(str(boneIDs[bone.name]))
                                    pdxJoint = pdx_data.PdxJoint(bone.name)
                                    pdxJoint.index = boneIDs[bone.name]
                                    if bone.parent is not None:
                                        print("Parent: " + str(bone.parent))
                                        print("Parent ID: " + str(boneIDs[bone.parent.name]))
                                        pdxJoint.parent = boneIDs[bone.parent.name]
                                    else:
                                        print("Root Bone")

                                    pdxJoint.transform = [1, 0, 0, 0, 1, 0, 0, 0, 1, bone.tail[0], bone.tail[1], bone.tail[2]]

                                    pdxSkeleton.joints.append(pdxJoint)

                                pdxShape = pdx_data.PdxShape(obj.name)
                                pdxShape.skeleton = pdxSkeleton
                                pdxShape.meshes = self.splitMeshes(obj.children[0], transform_mat, boneIDs)

                                pdxWorld.objects.append(pdxShape)
                elif obj.type == "EMPTY":
                    if obj.parent is not None and obj.parent.name.lower() == "locators":
                        locator = pdx_data.PdxLocator(obj.name, obj.location * transform_mat)
                        obj.rotation_mode = 'QUATERNION'
                        locator.quaternion = obj.rotation_quaternion
                        #TODO locator.parent

                        pdxLocators.locators.append(locator)
                else:
                    print("Exporter: Invalid Type Selected: " + obj.type)

        pdxObjects.append(pdxWorld)

        if len(pdxLocators.locators) > 0:
            pdxObjects.append(pdxLocators)

        result_file = io.open(self.filename, 'w+b')

        result_file.write(b'@@b@')

        for i in range(len(pdxObjects)):
            result_file.write(pdxObjects[i].get_binary_data())

        result_file.close()




















































"""

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

        for i in range(len(bm.verts)):
            verts.append(bm.verts[i].co)
            bm.verts[i].normal_update()
            normal_temp = bm.verts[i].normal * transform_mat
            normal_temp.normalize()
            #temp_y = normal_temp[1]
            #normal_temp[1] = normal_temp[2]
            #normal_temp[2] = temp_y
            normals.append(normal_temp)

        bm.faces.ensure_lookup_table()
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

        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        bm.faces.index_update()

        for i in range(len(bm.verts)):
            if len(bm.verts[i].link_faces) > 0:#For Models with stray vertices...
                tangents.append(bm.verts[i].link_faces[0].calc_tangent_vert_diagonal().to_4d() * transform_mat)#(0.0, 0.0, 0.0, 0.0))
            else:
                tangents.append((0.0, 0.0, 0.0, 0.0))

        #Trim data, remove empty bytes
        for i in range(len(uv_coords)):
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

        bb_min = [math.inf, math.inf, math.inf]
        bb_max = [-math.inf, -math.inf, -math.inf]

        for i in range(len(verts)):
            for j in range(3):
                bb_min[j] = min([verts[i][j], bb_min[j]])
                bb_max[j] = max([verts[i][j], bb_max[j]])

        mesh.verts = verts
        mesh.normals = normals
        mesh.tangents = tangents
        mesh.uv_coords = uv_coords
        mesh.faces = faces
        mesh.meshBounds = pdx_data.PdxBounds(bb_min, bb_max)
        mesh.material = pdx_data.PdxMaterial()

        diff_file = ""

        if len(bpy.data.objects[name].material_slots) > 0:
            for mat_slot in bpy.data.objects[name].material_slots:
                for mtex_slot in mat_slot.material.texture_slots:
                    if mtex_slot:
                        if hasattr(mtex_slot.texture, 'image'):
                            if mtex_slot.texture.image is None:
                                bpy.ops.error.message('INVOKE_SCREEN', message="The Texture Image file is not loaded")
                            else:
                                diff_file = os.path.basename(mtex_slot.texture.image.filepath)
        else:
            diff_file = os.path.basename(bpy.data.meshes[name].uv_textures[0].data[0].image.filepath)

        mesh.material.shader = "PdxMeshShip"
        mesh.material.diff = diff_file
        mesh.material.spec = "test_spec"
        mesh.material.normal = "test_normal"

        #Collision Mesh
        collisionObject = None
        collisionShape = None

        for o in bpy.data.objects:
            if o.type == "MESH" and o.draw_type == "WIRE":
                collisionObject = o

        if collisionObject is None:
            print("WARNING ::: No Collision Mesh found. Only using Bounding Box!")
        else:
            print("Collision Shape Name: " + collisionObject.name)
            collisionShape = pdx_data.PdxShape(collisionObject.name)

            collisionMesh = pdx_data.PdxCollisionMesh()
            collisionShape.mesh = collisionMesh

            collision_blender_mesh = bpy.data.meshes[collisionObject.name]

            cbm = bmesh.new()
            cbm.from_mesh(collision_blender_mesh)
            bmesh.ops.triangulate(cbm, faces=cbm.faces)

            for vert in cbm.verts:
                vert.co = vert.co * transform_mat

            cbm.verts.index_update()
            cbm.faces.index_update()
            cbm.verts.ensure_lookup_table()

            cverts = []

            for i in range(len(cbm.verts)):
                cverts.append(cbm.verts[i].co)

            cbm.faces.ensure_lookup_table()
            cbm.verts.ensure_lookup_table()
            cbm.verts.index_update()
            cbm.faces.index_update()

            cfaces = []

            for face in cbm.faces:
                temp = []

                for loop in face.loops:
                    temp.append(loop.vert.index)

                cfaces.append(temp)

            cbb_min = [math.inf, math.inf, math.inf]
            cbb_max = [-math.inf, -math.inf, -math.inf]

            for i in range(len(cverts)):
                for j in range(3):
                    cbb_min[j] = min([cverts[i][j], cbb_min[j]])
                    cbb_max[j] = max([cverts[i][j], cbb_max[j]])

            collisionMesh.verts = cverts
            collisionMesh.faces = cfaces
            collisionMesh.meshBounds = pdx_data.PdxBounds(cbb_min, cbb_max)
            collisionMesh.material = pdx_data.PdxMaterial()

        world.objects.append(shape)
        if collisionShape is not None:
            world.objects.append(collisionShape)
        world.objects.append(locators)
        objects.append(world)


"""
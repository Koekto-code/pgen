bl_info = {
    "name": "Planet Generator",
    "author": "Koekto-code",
    "version": (0, 1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Add > Mesh > Planet",
    "description": "Procedurally generated planet surface",
    "warning": "",
    "doc_url": "",
    "category": "Add Mesh",
}

# @todo add feature of making terrain on existing sphere

import bpy
import bmesh
from bpy_extras import object_utils

from bpy.props import (
    BoolProperty,
    IntProperty,
    FloatProperty,
    FloatVectorProperty,
)
from . lib.noise import pnoise3, snoise3

### Linear math ====================================================================

class vec3:
    def __init__(self, x, y=None, z=None):
        if isinstance(x, vec3):
            self.x, self.y, self.z = float(x.x), float(x.y), float(x.z)
        elif hasattr(x, '__getitem__'):
            self.x = float(x[0])
            self.y = float(x[1])
            self.z = float(x[2])
        elif not (y is None or z is None):
            self.x, self.y, self.z = float(x), float(y), float(z)
        else:
            self.x, self.y, self.z = float(x), float(x), float(x)
    
    def __neg__(self):
        return vec3(-x, -y, -z)
    
    def __add__(self, v):
        if isinstance(v, vec3):
            return vec3(self.x + v.x, self.y + v.y, self.z + v.z)
        if isinstance(v, list) or isinstance(v, tuple):
            return self + vec3(v)
    
    def __sub__(self, v):
        if isinstance(v, vec3):
            return vec3(self.x + v.x, self.y + v.y, self.z + v.z)
        if isinstance(v, list) or isinstance(v, tuple):
            return self - vec3(v)
    
    def __mul__(self, v):
        if isinstance(v, vec3):
            return vec3(self.x * v.x, self.y * v.y, self.z * v.z)
        return self * vec3(v)
    
    def __truediv__(self, v):
        if isinstance(v, vec3):
            return vec3(self.x / v.x, self.y / v.y, self.z / v.z)
        return self / vec3(v)
    
    def data(self):
        return [self.x, self.y, self.z]

def length(v: vec3):
    return (v.x ** 2 + v.y ** 2 + v.z ** 2) ** 0.5

def normalize(v):
    return v / length(v)

def dot(a: vec3, b: vec3):
    return a.x * b.x + a.y * b.y + a.z * b.z

def cos(a: vec3, b: vec3):
    return dot(a, b) / (length(a) * length(b))

### Terrain generation =============================================================

# hardcoded octahedron to begin with
hc_octahedron_verts = [vec3(v) for v in [
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (-1.0, 0.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.0, 0.0, -1.0)
]]
hc_octahedron_faces = [
    (1, 0, 4),
    (2, 1, 4),
    (3, 2, 4),
    (0, 3, 4),  
    (2, 3, 5),
    (3, 0, 5),
    (0, 1, 5),
    (1, 2, 5)
]

# make 4 triangles from each one
def surface_subdivide(verts, faces, radius):
    alr_subdiv_edges = dict()
    newfaces = []
    
    for i in range(len(faces)):
        j, k, l = faces[i][0], faces[i][1], faces[i][2]
        
        if (j, k) in alr_subdiv_edges:
            jkv = alr_subdiv_edges[(j, k)]
        elif (k, j) in alr_subdiv_edges:
            jkv = alr_subdiv_edges[(k, j)]
        else:
            jkv = len(verts)
            alr_subdiv_edges[(j, k)] = len(verts)
            verts.append(normalize(verts[j] + verts[k]) * radius)
        
        if (k, l) in alr_subdiv_edges:
            klv = alr_subdiv_edges[(k, l)]
        elif (l, k) in alr_subdiv_edges:
            klv = alr_subdiv_edges[(l, k)]
        else:
            klv = len(verts)
            alr_subdiv_edges[(k, l)] = len(verts)
            verts.append(normalize(verts[k] + verts[l]) * radius)
        
        if (j, l) in alr_subdiv_edges:
            jlv = alr_subdiv_edges[(j, l)]
        elif (l, j) in alr_subdiv_edges:
            jlv = alr_subdiv_edges[(l, j)]
        else:
            jlv = len(verts)
            alr_subdiv_edges[(j, l)] = len(verts)
            verts.append(normalize(verts[j] + verts[l]) * radius)
        
        newfaces.append([jkv, klv, k]) #todo clockwise triangles
        newfaces.append([klv, jlv, l]) #todo clockwise triangles
        newfaces.append([jlv, jkv, j]) #todo clockwise triangles
        newfaces.append([jkv, klv, jlv])
    
    return newfaces

# generate an octasphere as raw mesh data
def ohdr_generate(
    subdiv: int,
    radius: float
) -> tuple[list]:
    ohdr_verts = [v * radius for v in hc_octahedron_verts]
    ohdr_faces = list(hc_octahedron_faces)
    
    for i in range(subdiv):
        ohdr_faces = surface_subdivide(ohdr_verts, ohdr_faces, radius)
    
    return (ohdr_verts, ohdr_faces)

# convert mesh data to format acceptable by .from_pydata() of blender's mesh
def ohdr_pydata(
    ohdr_verts: list[vec3],
    ohdr_faces: list[tuple[int]]
) -> tuple[list]:
    return (
        [tuple(v.data()) for v in ohdr_verts],
        [tuple(f) for f in ohdr_faces]
    )

# apply an offset to each vertex of the sphere
# so that it looks like a planet's terrain
def surface_form(
    ohdr_verts: list[vec3],
    radius: float, # the actual radius of the sphere
    n_offset: tuple[float],
    ter_infl: float,
    nfunc=snoise3
):
    for i in range(len(ohdr_verts)):
        vd = (vec3(n_offset) + ohdr_verts[i] / radius).data()
        va = 0.0
        va += nfunc(vd[0], vd[1], vd[2], 1)
        va += nfunc(vd[0], vd[1], vd[2], 3)
        va += nfunc(vd[0], vd[1], vd[2], 7) * 0.7
        va += nfunc(vd[0], vd[1], vd[2], 11) * 0.5
        va += nfunc(vd[0], vd[1], vd[2], 15) * 0.47
        va += nfunc(vd[0], vd[1], vd[2], 21) * 0.3
        
        # add nice hills
        va += va * (va - 0.8)
        
        va += nfunc(vd[0], vd[1], vd[2], 33)
        va *= ter_infl
        
        ohdr_verts[i] *= 1.0 + va

### Interfaces =====================================================================

class AddPlanetOperator(bpy.types.Operator, object_utils.AddObjectHelper):
    bl_idname = "pgen.planet_add"
    bl_label = "Add Planet"
    bl_options = {'REGISTER', 'UNDO'}
    
    __updatecond = True
    def __setupdate(self, context):
        AddPlanetOperator.__updatecond = True

    subdiv: IntProperty(
        name="Subdivisions",
        description="Octasphere subdivisions",
        min=0, max=24,
        default=3,
        update=__setupdate
    )
    radius: FloatProperty(
        name="Radius",
        description="Initial radius of the sphere",
        min=0.01,
        default=1.0,
        update=__setupdate
    )
    n_offset: FloatVectorProperty(
        name="Noise offset",
        subtype="TRANSLATION",
        description="Offset in 3D noise space",
        default=(0.0, 0.0, 0.0),
    )
    ter_infl: FloatProperty(
        name="Terrain influence",
        description="Specifies the influence of noise at the sphere",
        min=-1.0, max=1.0,
        default=0.025,
    )
    use_simplex: BoolProperty(
        name="Use simplex",
        description="Switch between perlin/simplex noise",
        default=True,
    )
    
    def invoke(self, context, o_lala):
        print('FALSE')
        AddPlanetOperator.__updatecond = True
        return self.execute(context)

    def execute(self, context):
        if AddPlanetOperator.__updatecond:
            AddPlanetOperator.__updatecond = False
            self.mv, self.mf = ohdr_generate(
                self.subdiv,
                self.radius
            )
        mv = list(self.mv)
        surface_form(
            mv,
            self.radius,
            self.n_offset,
            self.ter_infl,
            snoise3 if self.use_simplex else pnoise3
        )
        mv, mf = ohdr_pydata(mv, self.mf)
        
        mesh = bpy.data.meshes.new("Planet")
        mesh.from_pydata(mv, [], mf)
        object_utils.object_data_add(context, mesh, operator=self)

        return {"FINISHED"}

def menu_func(self, context):
    self.layout.operator(AddPlanetOperator.bl_idname, text="Planet", icon="SPHERE")

### ================================================================================

def register():
    bpy.utils.register_class(AddPlanetOperator)
    bpy.types.VIEW3D_MT_mesh_add.append(menu_func)

def unregister():
    bpy.utils.unregister_class(AddPlanetOperator)
    bpy.types.VIEW3D_MT_mesh_add.remove(menu_func)

if __name__ == "__main__":
    register()

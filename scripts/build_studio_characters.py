"""Original LINK character family. Run with Blender 5.x --background --python this_file.

Authored Y-up to match the runtime directly. All four use the same named armature;
face morphs and rigidly weighted accessories keep the runtime rig inexpensive.
"""
import bpy, math, json, sys
from pathlib import Path
from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assets/source/characters'
RUNTIME = ROOT / 'frontend/public/assets/models/studio'
PREVIEW = ROOT / 'docs/design/20261022/model-previews'
for directory in (SOURCE, RUNTIME, PREVIEW):
    directory.mkdir(parents=True, exist_ok=True)
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ONLY = next((x.split('=')[1] for x in ARGS if x.startswith('only=')), None)
RENDER = 'no-render' not in ARGS
MESHES, BINDINGS = [], []
SKIN = None

def material(name, color, roughness=.55, metal=0):
    mat = bpy.data.materials.new(name); mat.diffuse_color = (*color, 1); mat.use_nodes=True
    bsdf=next((node for node in mat.node_tree.nodes if node.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf:
        bsdf=mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        output=mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
        mat.node_tree.links.new(bsdf.outputs['BSDF'],output.inputs['Surface'])
    bsdf.inputs['Base Color'].default_value=(*color,1)
    bsdf.inputs['Roughness'].default_value=roughness; bsdf.inputs['Metallic'].default_value=metal
    return mat

def finish(obj, name, mat, bone=None):
    obj.name=name
    if mat: obj.data.materials.append(mat)
    if obj.type == 'MESH':
        for polygon in obj.data.polygons: polygon.use_smooth=True
        MESHES.append(obj)
        if bone: BINDINGS.append((obj,bone))
    return obj

def ball(name, pos, scale, mat, bone=None, segments=24, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1, location=pos)
    obj=bpy.context.object; obj.scale=scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj,name,mat,bone)

def box(name,pos,size,mat,bevel=.025,bone=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=pos)
    obj=bpy.context.object; obj.scale=size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mod=obj.modifiers.new('Rounded edges','BEVEL'); mod.width=bevel; mod.segments=3
    bpy.ops.object.modifier_apply(modifier=mod.name)
    mod=obj.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return finish(obj,name,mat,bone)

def tube(name,points,radius,mat,bone=None,res=3):
    curve=bpy.data.curves.new(name,'CURVE'); curve.dimensions='3D'; curve.resolution_u=4
    curve.bevel_depth=radius; curve.bevel_resolution=res
    spline=curve.splines.new('BEZIER'); spline.bezier_points.add(len(points)-1)
    for point,co in zip(spline.bezier_points,points):
        point.co=co; point.handle_left_type='AUTO'; point.handle_right_type='AUTO'
    obj=bpy.data.objects.new(name,curve); bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active=obj; obj.select_set(True)
    for other in bpy.context.selected_objects:
        if other != obj: other.select_set(False)
    bpy.ops.object.convert(target='MESH')
    return finish(bpy.context.object,name,mat,bone)

def limb(name,a,b,radius,mat,bone=None):
    mid=(Vector(a)+Vector(b))*.5
    obj=ball(name,mid,(radius,(Vector(b)-Vector(a)).length*.5+radius*.55,radius),mat,bone,20,12)
    obj.rotation_mode='QUATERNION'; obj.rotation_quaternion=(Vector(b)-Vector(a)).to_track_quat('Y','Z')
    return obj

def aim(obj, target):
    direction=(Vector(target)-obj.location).normalized()
    right=direction.cross(Vector((0,1,0))).normalized()
    up=right.cross(direction).normalized()
    obj.rotation_mode='QUATERNION'
    obj.rotation_quaternion=Matrix((right,up,-direction)).transposed().to_quaternion()

def hair_lock(name, points, width, mat, bone):
    a,b,c=map(Vector,points); verts=[]; faces=[]; rows=12; sides=8
    for i in range(rows):
        t=i/(rows-1); center=(1-t)**2*a+2*(1-t)*t*b+t*t*c
        tangent=(2*(1-t)*(b-a)+2*t*(c-b)).normalized()
        across=tangent.cross(Vector((0,0,1))).normalized()
        normal=across.cross(tangent).normalized()
        radius=width*(.45+.8*math.sin(t*math.pi))*(1-t**3)+.001
        for j in range(sides):
            angle=j/sides*math.tau
            verts.append(tuple(center+across*math.cos(angle)*radius+normal*math.sin(angle)*radius*.32))
    for i in range(rows-1):
        for j in range(sides):
            a=i*sides+j; b=i*sides+(j+1)%sides
            faces.append((a,b,b+sides,a+sides))
    faces.extend([tuple(range(sides-1,-1,-1)),tuple((rows-1)*sides+j for j in range(sides))])
    mesh=bpy.data.meshes.new(name); mesh.from_pydata(verts,[],faces); mesh.update()
    obj=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(obj)
    return finish(obj,name,mat,bone)

def patch(name,vertices,mat,bone):
    mesh=bpy.data.meshes.new(name); mesh.from_pydata(vertices,[],[tuple(range(len(vertices)))]); mesh.update()
    obj=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(obj)
    mod=obj.modifiers.new('Fabric thickness','SOLIDIFY'); mod.thickness=.01
    bpy.context.view_layer.objects.active=obj; bpy.ops.object.modifier_apply(modifier=mod.name)
    return finish(obj,name,mat,bone)

def cloth_texture(mat,base):
    # Baked 128px cloth weave replaces per-thread geometry.
    image=bpy.data.images.new(mat.name+' weave',width=128,height=128)
    pixels=[]
    for y in range(128):
        for x in range(128):
            weave=1+.035*math.sin(x*math.pi/2)*math.sin(y*math.pi/2)+.012*math.sin(x*.31+y*.47)
            pixels.extend([min(1,c*weave) for c in base]+[1])
    image.pixels=pixels; image.pack()
    node=mat.node_tree.nodes.new('ShaderNodeTexImage'); node.image=image
    mat.node_tree.links.new(node.outputs['Color'],next((node for node in mat.node_tree.nodes if node.type == 'BSDF_PRINCIPLED'), None).inputs['Base Color'])

def skirt(name, y, z, mat, bone):
    vertices=[]; faces=[]; segments=40
    for height,radius in [(y+.12,.20),(y+.10,.21),(y-.10,.27),(y-.12,.27)]:
        for i in range(segments):
            a=i/segments*math.tau; r=radius*(1+.035*math.cos(a*10))
            vertices.append((r*math.cos(a),height,z+r*.72*math.sin(a)))
    for row in range(3):
        for i in range(segments):
            j=(i+1)%segments;faces.append((row*segments+i,row*segments+j,(row+1)*segments+j,(row+1)*segments+i))
    faces.extend([tuple(range(segments-1,-1,-1)),tuple(3*segments+i for i in range(segments))])
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);return finish(obj,name,mat,bone)

def rig(seated):
    data=bpy.data.armatures.new('LINK_shared_rig'); arm=bpy.data.objects.new('LINK_Rig',data)
    bpy.context.collection.objects.link(arm); bpy.context.view_layer.objects.active=arm; arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    joints={'root':((0,0,0),(0,.3,0),None),
        'pelvis':((0,.64,-.17),(0,.86,-.15),'root'),
        'torso':((0,.86,-.15),(0,1.2,-.12),'pelvis'),
        'head':((0,1.2,-.12),(0,1.72,-.12),'torso')}
    if not seated:
        joints['pelvis']=((0,.83,0),(0,1.02,0),'root')
        joints['torso']=((0,1.02,0),(0,1.36,0),'pelvis')
        joints['head']=((0,1.36,0),(0,1.9,0),'torso')
    for side,sign in [('L',-1),('R',1)]:
        shoulder=(sign*.27,1.14,-.12) if seated else (sign*.27,1.30,0)
        elbow=(sign*.34,.96,.08) if seated else (sign*.37,1.03,.02)
        wrist=(sign*.23,.95,.37) if seated else (sign*.38,.83,.08)
        hip=(sign*.13,.64,-.17) if seated else (sign*.13,.83,0)
        knee=(sign*.14,.54,.20) if seated else (sign*.14,.46,.01)
        foot=(sign*.14,.14,.25) if seated else (sign*.14,.14,.03)
        joints['upper_arm_'+side]=(shoulder,elbow,'torso')
        joints['forearm_'+side]=(elbow,wrist,'upper_arm_'+side)
        joints['hand_'+side]=(wrist,tuple(Vector(wrist)+Vector((0,-.02,.12))),'forearm_'+side)
        joints['hip_'+side]=(hip,knee,'pelvis')
        joints['knee_'+side]=(knee,foot,'hip_'+side)
        joints['foot_'+side]=(foot,tuple(Vector(foot)+Vector((0,0,.16))),'knee_'+side)
    for name,(head,tail,parent) in joints.items():
        bone=data.edit_bones.new(name); bone.head=head; bone.tail=tail
        if parent: bone.parent=data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT'); arm.show_in_front=True
    return arm,joints

def furniture(wood,steel,cream,purple):
    box('Desk_top',(0,.87,.39),(1.03,.075,.53),wood,.035)
    box('Desk_apron',(0,.76,.17),(.91,.14,.04),wood,.014)
    for x in [-.43,.43]:
        for z in [.21,.57]:
            limb('Desk_leg',(x,.82,z),(x,.055,z+.025),.024,steel)
            ball('Desk_foot',(x,.035,z+.025),(.036,.025,.034),steel,segments=12,rings=8)
    box('Chair_seat',(0,.53,-.21),(.55,.07,.48),wood,.035)
    box('Chair_back',(0,.92,-.44),(.57,.43,.07),wood,.06)
    for x in [-.22,.22]:
        for z in [-.39,-.03]:
            limb('Chair_leg',(x,.52,z),(x,.045,z-.035),.022,steel)
        limb('Chair_back_rail',(x,.55,-.43),(x,1.08,-.46),.018,steel)
        for y in [.79,1.02]: ball('Chair_rivet',(x,y,-.396),(.014,.014,.006),steel,segments=12,rings=8)
    book=box('Workbook_cover',(-.02,.92,.39),(.49,.015,.32),purple,.008)
    box('Workbook_pages',(-.02,.932,.39),(.47,.017,.30),cream,.008)
    tube('Workbook_binding',[(-.02,.944,.25),(-.02,.946,.39),(-.02,.944,.53)],.003,purple)
    for z in [.29,.33,.37,.41,.45,.49]:
        tube('Workbook_rule',[(-.22,.944,z),(-.06,.944,z)],.001,steel,res=0)
        tube('Workbook_rule',[(.02,.944,z),(.18,.944,z)],.001,steel,res=0)
    limb('Pencil',(.32,.923,.24),(.39,.923,.48),.009,purple)
    ball('Pencil_tip',(.395,.923,.495),(.006,.006,.015),steel,segments=12,rings=8)

def build(kind):
    global MESHES,BINDINGS,SKIN
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    MESHES=[]; BINDINGS=[]
    seated=kind!='assistant'
    skin=material('Peach porcelain',(.91,.62,.45),.48)
    next(node for node in skin.node_tree.nodes if node.type == 'BSDF_PRINCIPLED').inputs['Subsurface Weight'].default_value=.07
    blush=material('Soft cheek',(.88,.38,.32),.72)
    cream=material('Warm ivory',(.94,.89,.78),.54)
    ink=material('Warm ink',(.045,.022,.035),.23)
    iris=material('Chestnut iris',(.24,.09,.045),.22)
    white=material('Eye whites',(.98,.965,.91),.18)
    glint=material('Eye catchlight',(1,1,1),.1)
    purple=material('Lilac',(.49,.34,.68),.55)
    mint=material('Mint enamel',(.30,.69,.60),.3)
    steel=material('Satin chair frame',(.28,.32,.37),.43,.55)
    wood=material('Honey oak',(.57,.32,.13),.48)
    colors={'ming':(.34,.62,.49),'yu':(.95,.65,.22),'lin':(.32,.52,.77),'assistant':(.56,.41,.72)}
    top=material('Woven uniform',colors[kind],.7); cloth_texture(top,colors[kind])
    bottom=material('Tailored hem',(.32,.20,.48) if kind!='lin' else (.10,.16,.29),.7)
    tights=material('Plum tights',(.09,.065,.12),.8)
    hair_color={'ming':(.028,.014,.034),'yu':(.16,.037,.014),'lin':(.055,.024,.012),'assistant':(.055,.018,.06)}[kind]
    hair=material('Sculpted hair',hair_color,.65)
    hair_hi=material('Hair ridges',tuple(c*1.4+.015 for c in hair_color),.43)
    arm,joints=rig(seated)
    head_y=1.60 if seated else 1.77
    head_z=-.12 if seated else 0
    face=ball('Continuous_face',(0,head_y,head_z),(.39,.405,.33),skin,'head',40,28)
    for v in face.data.vertices:
        if v.co.y<-.08: v.co.x*=1+.22*(v.co.y+.08)
    # Eyes have an exported blink morph. Mouth openness is audio-driven in runtime.
    for side,sign in [('L',-1),('R',1)]:
        x=sign*.148; ey=head_y+.012; ez=head_z+.294
        for name,offset,scale,mat in [
            ('eye_white',(.0,0,0),(.101,.124,.038),white),
            ('eye_iris',(0,-.005,.036),(.064,.086,.018),iris),
            ('eye_pupil',(0,-.002,.05),(.040,.065,.011),ink),
            ('eye_glint',(-.025,.036,.06),(.023,.027,.009),glint),
            ('eye_glint_small',(.027,-.035,.056),(.009,.011,.006),glint)]:
            obj=ball(name+'_'+side,(x+offset[0],ey+offset[1],ez+offset[2]),scale,mat,'head',20,12)
            obj.shape_key_add(name='Basis'); blink=obj.shape_key_add(name='blink')
            for v in blink.data: v.co.y*=.035
        tube('Upper_eyelid_'+side,[(x-.10,ey+.025,ez+.018),(x-.07,ey+.105,ez+.018),(x+.025,ey+.125,ez+.023),(x+.10,ey+.05,ez+.02)],.009,hair,'head',1)
        tube('Brow_'+side,[(x-.075,head_y+.19,head_z+.26),(x,head_y+.207,head_z+.28),(x+.075,head_y+.182,head_z+.26)],.008,hair,'head',1)
        ball('Ear_'+side,(sign*.38,head_y-.065,head_z),(.064,.10,.057),skin,'head',20,12)
        ball('Ear_inner_'+side,(sign*.413,head_y-.06,head_z+.03),(.018,.058,.025),blush,'head',16,10)
        ball('Cheek_'+side,(sign*.243,head_y-.14,head_z+.259),(.062,.027,.006),blush,'head',16,10)
    ball('Nose',(0,head_y-.10,head_z+.325),(.032,.033,.035),skin,'head',20,12)
    mouth=ball('Mouth',(0,head_y-.225,head_z+.277),(.063,.013,.009),ink,'head',24,12)
    for vertex in mouth.data.vertices: vertex.co.y+=.012*(vertex.co.x/.063)**2
    mouth.shape_key_add(name='Basis'); opened=mouth.shape_key_add(name='open')
    for v in opened.data: v.co.y*=4.0
    ball('Lower_lip',(0,head_y-.244,head_z+.27),(.046,.01,.006),blush,'head',16,10)
    # Back cap plus overlapping swept, tapered locks, with sparse ridge geometry.
    ball('Hair_cap',(0,head_y+.10,head_z-.09),(.409,.363,.302),hair,'head',32,20)
    if kind=='assistant': ball('Bob_back',(0,head_y-.08,head_z-.17),(.412,.37,.24),hair,'head',28,20)
    for i in range(9):
        x=-.35+i*.084
        start=(x*.5+.09,head_y+.42,head_z-.06)
        mid=(x*.95+.04,head_y+.32,head_z+.33)
        end=(x-.03,head_y+.16+.05*math.cos(i*.7),head_z+.29)
        hair_lock('Swept_hair_%02d'%i,[start,mid,end],.087,hair if i%3 else hair_hi,'head')
    for sign in [-1,1]:
        if kind=='yu':
            ball('Hair_bun',(sign*.355,head_y+.32,head_z-.08),(.15,.15,.14),hair,'head',24,16)
            for i in range(4):
                tube('Bun_ridge',[(sign*.28,head_y+.34+i*.018,head_z+.03),(sign*.39,head_y+.43-i*.013,head_z+.04),(sign*.47,head_y+.32,head_z-.01)],.006,hair_hi,'head',1)
            ball('Hair_tie',(sign*.35,head_y+.28,head_z+.055),(.06,.025,.035),top,'head',16,10)
        else:
            end_y=head_y-.24 if kind=='assistant' else head_y-.08
            for i in range(3):
                tube('Temple_lock',[(sign*(.33+i*.02),head_y+.22,head_z-.06),(sign*.39,head_y+.02,head_z-.02),(sign*(.32+i*.02),end_y,head_z+.04)],.037,hair,'head',2)
    if kind in ['ming','lin']:
        glasses=purple if kind=='ming' else material('Slate frames',(.16,.28,.46),.4)
        lens=material('Clear lenses',(.79,.9,1),.07)
        bsdf=next(node for node in lens.node_tree.nodes if node.type == 'BSDF_PRINCIPLED'); bsdf.inputs['Alpha'].default_value=.035
        lens.surface_render_method='DITHERED'
        for sign in [-1,1]:
            x=sign*.151; pts=[]
            for i in range(17):
                a=i/16*math.tau; pts.append((x+.127*math.cos(a),head_y+.005+.141*math.sin(a),head_z+.369))
            tube('Eyeglass_frame',pts,.010,glasses,'head',1)
            ball('Transparent_lens',(x,head_y+.005,head_z+.363),(.118,.133,.008),lens,'head',24,16)
            tube('Glasses_temple',[(sign*.27,head_y+.055,head_z+.36),(sign*.38,head_y+.055,head_z+.17),(sign*.39,head_y+.03,head_z)],.009,glasses,'head',1)
        tube('Glasses_bridge',[(-.026,head_y+.026,head_z+.37),(0,head_y+.042,head_z+.38),(.026,head_y+.026,head_z+.37)],.010,glasses,'head',1)
    torso_y=1.005 if seated else 1.17
    torso_z=-.14 if seated else 0
    ball('Shirt',(0,torso_y,torso_z),(.245,.265,.16),top,'torso',32,20)
    ball('Neck',(0,torso_y+.235,torso_z),(.082,.105,.075),skin,'head',20,12)
    if kind!='assistant':
        for sign in [-1,1]:
            patch('Collar',[(sign*.02,torso_y+.235,torso_z+.08),(sign*.14,torso_y+.19,torso_z+.118),(sign*.08,torso_y+.105,torso_z+.155)],cream,'torso')
    if kind=='lin':
        ball('Ivory_vest',(0,torso_y-.02,torso_z+.025),(.25,.218,.158),cream,'torso',24,16)
        tube('Vest_V',[(-.14,torso_y+.17,torso_z+.14),(0,torso_y+.045,torso_z+.187),(.14,torso_y+.17,torso_z+.14)],.012,top,'torso',1)
    for y in [torso_y+.04,torso_y-.04,torso_y-.12]:
        ball('Button',(0,y,torso_z+.161),(.013,.013,.008),cream,'torso',12,8)
    # Each articulated limb is bound to the shared armature; fingertips stay above the desk.
    for side,sign in [('L',-1),('R',1)]:
        shoulder,elbow,_=joints['upper_arm_'+side]; _,wrist,_=joints['forearm_'+side]
        limb('Sleeve_'+side,shoulder,tuple(Vector(shoulder).lerp(Vector(elbow),.58 if seated else .99)),.09 if seated else .075,top,'upper_arm_'+side)
        limb('Upper_arm_'+side,tuple(Vector(shoulder).lerp(Vector(elbow),.48)),elbow,.066,skin if seated else top,'upper_arm_'+side)
        limb('Forearm_'+side,elbow,wrist,.061,skin if seated else top,'forearm_'+side)
        palm=tuple(Vector(wrist)+Vector((0,0,.045) if seated else (0,-.055,0)))
        ball('Palm_'+side,palm,(.064,.034,.07) if seated else (.052,.061,.033),skin,'hand_'+side,16,12)
        if not seated: limb('Cuff_'+side,tuple(Vector(wrist)+Vector((0,.04,0))),tuple(Vector(wrist)+Vector((0,.013,0))),.063,cream,'forearm_'+side)
        for i in range(4):
            a=(wrist[0]+(i-1.5)*.027,wrist[1]-.005,wrist[2]+.075)
            b=(a[0],a[1]-.006,a[2]+.062-(abs(i-1.5)*.008))
            if not seated:
                a=(wrist[0]+(i-1.5)*.022,wrist[1]-.095,wrist[2])
                b=(a[0],a[1]-.05+abs(i-1.5)*.008,a[2]+.005)
            limb('Finger_'+side,a,b,.013,skin,'hand_'+side)
        limb('Thumb_'+side,(wrist[0]+sign*.05,wrist[1],wrist[2]+.02),(wrist[0]+sign*.083,wrist[1]-.005,wrist[2]+.065),.018,skin,'hand_'+side)
        hip,knee,_=joints['hip_'+side]; _,foot,_=joints['knee_'+side]
        limb('Shorts_'+side,hip,tuple(Vector(hip).lerp(Vector(knee),.7 if seated else .2)),.105 if seated else .068,bottom,'hip_'+side)
        limb('Thigh_'+side,tuple(Vector(hip).lerp(Vector(knee),.55 if seated else .18)),knee,.077 if seated else .063,skin if seated else tights,'hip_'+side)
        limb('Shin_'+side,knee,foot,.064 if seated else .056,skin if seated else tights,'knee_'+side)
        ball('Sock_'+side,(foot[0],.18,foot[2]),(.066,.075,.067),cream,'foot_'+side,16,12)
        ball('Sneaker_'+side,(foot[0],.085,foot[2]+.07),(.098,.067,.16),cream,'foot_'+side,24,14)
        box('Sole_'+side,(foot[0],.034,foot[2]+.065),(.20,.035,.30),bottom,.025,'foot_'+side)
        for i in range(3):
            z=foot[2]+.07+i*.028
            tube('Shoelace_'+side,[(foot[0]-.047,.141,z),(foot[0],.15,z+.006),(foot[0]+.047,.141,z)],.004,top,'foot_'+side,1)
    if kind in ['yu','assistant']:
        skirt('Pleated_skirt',.67 if seated else .85,-.10 if seated else 0,bottom,'pelvis')
    if kind=='assistant':
        for sign in [-1,1]:
            patch('Blazer_lapel',[(sign*.02,1.36,.07),(sign*.17,1.32,.12),(sign*.09,1.16,.172),(sign*.02,1.22,.17)],cream,'torso')
            box('Blazer_pocket',(sign*.145,1.05,.137),(.095,.047,.015),top,.009,'torso')
            ball('Ear_cup',(sign*.43,head_y-.04,head_z),(.07,.12,.095),cream,'head',24,16)
            ball('Headset_cover',(sign*.48,head_y-.04,head_z+.015),(.025,.082,.067),purple,'head',20,12)
        tube('Headset_band',[(-.43,head_y-.02,-.015),(-.39,head_y+.35,-.06),(0,head_y+.47,-.07),(.39,head_y+.35,-.06),(.43,head_y-.02,-.015)],.024,cream,'head',2)
        tube('Microphone_boom',[(.46,head_y-.12,.06),(.36,head_y-.27,.24),(.16,head_y-.26,.31)],.011,purple,'head',2)
        ball('Microphone',(.145,head_y-.26,.315),(.043,.023,.023),ink,'head',16,12)
    for obj in MESHES:
        if not obj.data.shape_keys and len(obj.data.polygons)>100:
            bpy.context.view_layer.objects.active=obj
            mod=obj.modifiers.new('Runtime topology','DECIMATE'); mod.ratio=.68
            bpy.ops.object.modifier_apply(modifier=mod.name)
    for obj,bone in BINDINGS:
        group=obj.vertex_groups.new(name=bone); group.add(list(range(len(obj.data.vertices))),1,'REPLACE')
        mod=obj.modifiers.new('LINK rig','ARMATURE'); mod.object=arm; obj.parent=arm
    if seated: furniture(wood,steel,cream,purple)
    # Merge rigid material surfaces, retaining named bone weights and separate face morphs.
    for dynamic in [True,False]:
        batch=[obj for obj in bpy.context.scene.objects if obj.type=='MESH' and not obj.data.shape_keys and (obj.parent==arm)==dynamic]
        if len(batch)>1:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in batch: obj.select_set(True)
            bpy.context.view_layer.objects.active=batch[0]
            bpy.ops.object.join()
            joined=bpy.context.object; joined.name='Character_surfaces' if dynamic else 'Desk_and_chair'
    MESHES=[obj for obj in bpy.context.scene.objects if obj.type=='MESH']
    # Render accessories, desk and character are exported together, without lights/camera.
    for obj in bpy.context.selected_objects: obj.select_set(False)
    arm.select_set(True)
    for obj in MESHES: obj.select_set(True)
    bpy.context.view_layer.objects.active=arm
    out=RUNTIME/(kind+'.glb')
    bpy.ops.export_scene.gltf(filepath=str(out),export_format='GLB',use_selection=True,export_yup=False,export_animations=False,export_skins=True,export_morph=True,export_extras=True)
    for obj in MESHES:
        if obj.data.shape_keys:
            for key in obj.data.shape_keys.key_blocks: key.value=0
    tris=sum(sum(len(poly.vertices)-2 for poly in obj.data.polygons) for obj in MESHES)
    info={'id':kind,'triangles':tris,'bytes':out.stat().st_size,'rig':list(joints),'morphs':['blink','open'],'axis':'Y up / +Z front'}
    (RUNTIME/(kind+'.json')).write_text(json.dumps(info,indent=2),encoding='utf8')
    print('ASSET '+json.dumps(info),flush=True)
    scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True
    scene.render.resolution_x=720; scene.render.resolution_y=900; scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'; scene.render.image_settings.color_mode='RGBA'; scene.render.film_transparent=True
    scene.world.color=(.35,.35,.35)
    for name,pos,power,size in [('Key',(-3,4,4),360,4),('Fill',(3,2,3),220,3),('Rim',(0,4,-3),400,3)]:
        data=bpy.data.lights.new(name,'AREA'); data.energy=power; data.shape='DISK'; data.size=size
        obj=bpy.data.objects.new(name,data); scene.collection.objects.link(obj); obj.location=pos
        aim(obj,(0,1,0))
    data=bpy.data.cameras.new('Preview'); camera=bpy.data.objects.new('Preview',data); scene.collection.objects.link(camera); scene.camera=camera
    data.type='ORTHO'; data.ortho_scale=2.55
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE/(kind+'.blend')))
    if RENDER:
        for view,pos in [('front',(0,1.5,5)),('side',(5,1.5,0)),('back',(0,1.5,-5))]:
            camera.location=pos; aim(camera,(0,1.04,0))
            scene.render.filepath=str(PREVIEW/(kind+'-'+view+'.png')); bpy.ops.render.render(write_still=True)
        camera.location=(1.8,1.7,5); aim(camera,(0,1.05,0))
        scene.render.filepath=str(RUNTIME/(kind+'-poster.png')); bpy.ops.render.render(write_still=True)
    return info

results=[]
for character in ['ming','yu','lin','assistant']:
    if not ONLY or ONLY==character: results.append(build(character))
(SOURCE/'manifest.json').write_text(json.dumps(results,indent=2),encoding='utf8')

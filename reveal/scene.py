"""Overwatch reveal - scene build. Run headless:
   Blender --background --python scene.py -- [--still N] [--res W H] [--samples N]

Dark studio, one hero object, a slow rising orbit. The light comes up before
the screen does, so the form reads first and the panel is the payoff.
"""
import bpy, sys, math, os
from mathutils import Vector

A = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
def opt(name, n=1, d=None):
    if name in A:
        i = A.index(name); return A[i+1:i+1+n]
    return d

HERE = os.path.dirname(os.path.abspath(__file__))
CASE = os.path.join(HERE, "..", "case")
MM   = 0.001                      # STLs are in mm; work in metres

# ---------------------------------------------------------------- scene
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
# Cycles rendered this at 2 min a frame on the M4 - eight hours for the
# sequence, which is not a trade worth making for a product shot lit this
# simply. EEVEE with raytraced shadows and screen-space reflections gets
# most of the way at about a second.
ENGINE = (opt("--engine", 1, ["EEVEE"]))[0].upper()
if ENGINE.startswith("C"):
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'GPU'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = (d.type == 'METAL')
    sc.cycles.use_denoising = True
    sc.cycles.samples = int((opt("--samples", 1, ["96"]))[0])
else:
    sc.render.engine = 'BLENDER_EEVEE'
    ee = sc.eevee
    ee.taa_render_samples = int((opt("--samples", 1, ["64"]))[0])
    for attr, val in [("use_raytracing", True), ("use_shadows", True),
                      ("use_bloom", True), ("use_gtao", True),
                      ("use_volumetric_shadows", True)]:
        if hasattr(ee, attr):
            setattr(ee, attr, val)
    if hasattr(ee, "ray_tracing_options"):
        ee.ray_tracing_options.use_denoise = True
sc.render.film_transparent = False
sc.view_settings.view_transform = 'AgX'      # filmic highlights, no clipping
sc.view_settings.look = 'AgX - Medium High Contrast'

SHOT = (opt("--shot", 1, ["reveal"]))[0]
PORTRAIT = "--portrait" in A
r = opt("--res", 2, ["1080", "1920"] if PORTRAIT else ["1920", "1080"])
sc.render.resolution_x, sc.render.resolution_y = int(r[0]), int(r[1])
sc.render.fps = 30

# ---------------------------------------------------------------- import
def load(name):
    bpy.ops.wm.stl_import(filepath=os.path.join(CASE, name))
    o = bpy.context.selected_objects[0]
    o.name = name.replace("overwatch_", "").replace(".stl", "")
    return o

front, back = load("overwatch_front.stl"), load("overwatch_back.stl")

# The model is Y-up (it was built to be looked at face-on); Blender is Z-up.
# The back is modelled in its own print orientation, so it is placed the way
# assembled() places it: flipped and seated into the cavity.
BODY_H, BODY_D, BACK_T = 55.6, 19.6, 2.4
back.rotation_euler = (math.pi, 0, 0)
back.location = (0, BODY_H, BODY_D + BACK_T)
bpy.context.view_layer.update()

grp = bpy.data.objects.new("rig", None); sc.collection.objects.link(grp)
for o in (front, back):
    o.parent = grp
grp.rotation_euler = (math.pi/2, 0, 0)
grp.scale = (MM, MM, MM)
bpy.context.view_layer.update()

# sit it on the floor, centred
bb = [grp.matrix_world @ Vector(c) for o in (front, back) for c in o.bound_box]
lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
grp.location = (-(lo.x+hi.x)/2, -(lo.y+hi.y)/2, -lo.z)
bpy.context.view_layer.update()
H = hi.z - lo.z; W = hi.x - lo.x
print("OBJECT %.0f x %.0f mm" % (W*1000, H*1000))

# ---------------------------------------------------------------- materials
def mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    return m, m.node_tree.nodes["Principled BSDF"], m.node_tree

def layer_lines(nt, bsdf, depth=0.00018):
    """0.2 mm layers, running across the part the way it printed - the front
    prints face down, so the lines lie in planes of constant depth, which is
    world Y once the rig is stood up. Tiny, but it is the difference between
    a render of a 3D print and a render of an injection moulding."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    wav = nt.nodes.new("ShaderNodeTexWave"); wav.wave_type = 'BANDS'
    wav.bands_direction = 'Y'; wav.inputs['Scale'].default_value = 1.0
    wav.inputs['Distortion'].default_value = 0.0
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs['Strength'].default_value = 0.09
    bump.inputs['Distance'].default_value = depth
    mapn = nt.nodes.new("ShaderNodeMapping")
    mapn.inputs['Scale'].default_value = (1, 5000, 1)   # 0.2 mm period
    nt.links.new(tc.outputs['Object'], mapn.inputs['Vector'])
    nt.links.new(mapn.outputs['Vector'], wav.inputs['Vector'])
    nt.links.new(wav.outputs['Color'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

m_body, b, nt = mat("body")
b.inputs['Base Color'].default_value = (0.62, 0.135, 0.075, 1)   # the orange
b.inputs['Roughness'].default_value = 0.46
b.inputs['Specular IOR Level'].default_value = 0.42
layer_lines(nt, b)
front.data.materials.append(m_body)

m_back, b2, nt2 = mat("back")
b2.inputs['Base Color'].default_value = (0.055, 0.058, 0.065, 1)
b2.inputs['Roughness'].default_value = 0.52
layer_lines(nt2, b2)
back.data.materials.append(m_back)

# ---------------------------------------------------------------- the panel
SCR_W, SCR_H = 57.6*MM, 43.2*MM
bpy.ops.mesh.primitive_plane_add(size=1)
scr = bpy.context.object; scr.name = "screen"

# Placed in world space rather than parented: the case never moves in this
# shot, only the camera, so parenting only bought a matrix to get wrong.
#
# A size=1 plane spans -0.5..0.5, so the scale IS the dimension - it was
# halved before, which is why the vents in the back plate were visible past
# the edges of the picture.
scr.scale = (SCR_W, SCR_H, 1)
scr.location = grp.matrix_world @ Vector((45.8, 29.8, 2.1))   # window centre

# Face +Y (the case's front) with the texture's up along +Z. A plain X
# rotation gives one or the other, never both, so it is X then Z.
scr.rotation_euler = (math.pi/2, 0, math.pi)

m_scr = bpy.data.materials.new("screen"); m_scr.use_nodes = True
nts = m_scr.node_tree; bs = nts.nodes["Principled BSDF"]

# One tall texture holding all three pages, and a Mapping node that shows a
# third of it. Sliding the mapping IS the swipe - no texture swapping, no
# second material, and the transition is whatever easing the keys have.
# The strip is stacked bottom-up because UV v=0 is the bottom of an image,
# so offset 0 / 1/3 / 2/3 walks gauges -> spotify -> launcher, which is the
# order ui_pages.c walks them in.
img = bpy.data.images.load(os.path.join(HERE, "screen_strip.png"))
tc  = nts.nodes.new("ShaderNodeTexCoord")
mapn = nts.nodes.new("ShaderNodeMapping")
mapn.inputs['Scale'].default_value = (1.0, 1.0/3.0, 1.0)
tex = nts.nodes.new("ShaderNodeTexImage"); tex.image = img
tex.interpolation = 'Cubic'; tex.extension = 'EXTEND'
nts.links.new(tc.outputs['UV'], mapn.inputs['Vector'])
nts.links.new(mapn.outputs['Vector'], tex.inputs['Vector'])
nts.links.new(tex.outputs['Color'], bs.inputs['Emission Color'])
bs.inputs['Base Color'].default_value = (0.01, 0.012, 0.016, 1)
bs.inputs['Roughness'].default_value = 0.14
bs.inputs['Emission Strength'].default_value = 0.0
scr.data.materials.append(m_scr)

PAGE = mapn.inputs['Location']          # y = 0 | 1/3 | 2/3
def page_key(frame, idx):
    PAGE.default_value = (0.0, idx/3.0, 0.0)
    PAGE.keyframe_insert("default_value", frame=frame)

# ---------------------------------------------------------------- finger
# A single finger, not a hand. A modelled hand that is not very good is worse
# than no hand at all; a finger entering frame soft and slightly out of focus
# reads as a hand without claiming to be one.
finger = None
if SHOT == "hand":
    from mathutils import Vector as V
    finger = bpy.data.objects.new("finger", None)
    sc.collection.objects.link(finger)

    bpy.ops.mesh.primitive_cylinder_add(radius=0.0062, depth=0.090, vertices=48)
    shaft = bpy.context.object
    shaft.location = (0, 0, -0.045)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.0062, segments=48, ring_count=24)
    tip = bpy.context.object
    tip.scale = (1, 1, 0.92)

    m_skin, bsk, _ = mat("skin")
    bsk.inputs['Base Color'].default_value = (0.32, 0.135, 0.085, 1)
    bsk.inputs['Roughness'].default_value = 0.52
    if 'Subsurface Weight' in bsk.inputs:
        bsk.inputs['Subsurface Weight'].default_value = 0.22
        bsk.inputs['Subsurface Radius'].default_value = (0.012, 0.005, 0.003)
    for o in (shaft, tip):
        o.data.materials.append(m_skin)
        o.parent = finger
        bpy.ops.object.shade_smooth({'object': o, 'selected_objects': [o]}) if False else None

    # point the tip into the panel and slightly up, the way a thumb arrives
    d = V((-0.22, -1.0, 0.40)).normalized()
    finger.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()

# ---------------------------------------------------------------- studio
bpy.ops.mesh.primitive_plane_add(size=2.4, location=(0, 0, 0))
floor = bpy.context.object; floor.name = "floor"
m_f, bf, _ = mat("floor")
bf.inputs['Base Color'].default_value = (0.0035, 0.004, 0.005, 1)
# 0.42 was still glossy enough to mirror the rim lights as a broad pool in
# the corner of frame - and a specular highlight ignores base colour, which
# is why darkening the floor three times did nothing. Roughness and specular
# level are the two knobs that actually reach it.
bf.inputs['Roughness'].default_value = 0.62
bf.inputs['Specular IOR Level'].default_value = 0.18
bf.inputs['Metallic'].default_value = 0.0
floor.data.materials.append(m_f)

w = sc.world = bpy.data.worlds.new("w"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs['Color'].default_value = (0.008, 0.009, 0.012, 1)
w.node_tree.nodes["Background"].inputs['Strength'].default_value = 1.0

# Every light is AIMED by a constraint at the object's centre rather than by
# a hand-written euler. The hand-set angles put a bright pool of floor in the
# bottom corner of the opening frame - the sort of thing that reads as a
# mistake rather than as lighting.
aim = bpy.data.objects.new("aim", None); sc.collection.objects.link(aim)
aim.location = (0, 0, H*0.52)

def area(name, loc, size, power, color=(1,1,1)):
    d = bpy.data.lights.new(name, 'AREA'); d.size = size; d.energy = power
    d.color = color
    o = bpy.data.objects.new(name, d); sc.collection.objects.link(o)
    o.location = loc
    c = o.constraints.new('TRACK_TO'); c.target = aim
    c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return o

# Key high front-left; rims high and behind. Lights near floor level blast it
# edge-on and the whole frame goes milky, which is the opposite of the look.
key  = area("key",  (-0.46,  0.54, 0.50), 0.70, 11)
rim  = area("rim",  ( 0.66, -0.52, 0.44), 0.45, 30, (0.60, 0.74, 1.00))
rim2 = area("rim2", (-0.68, -0.46, 0.38), 0.40, 16, (1.00, 0.70, 0.48))
fill = area("fill", ( 0.38,  0.80, 0.26), 1.10, 2.2)

# ---------------------------------------------------------------- camera
cam_d = bpy.data.cameras.new("cam"); cam_d.lens = 80
# In portrait the sensor must be fitted to WIDTH. On AUTO Blender fits the
# larger dimension, which in 9:16 is the height - and the barbell, which is
# the widest thing and the whole silhouette, runs off both edges.
cam_d.sensor_fit = 'HORIZONTAL'
cam_d.dof.use_dof = True; cam_d.dof.aperture_fstop = 3.2
cam = bpy.data.objects.new("cam", cam_d); sc.collection.objects.link(cam)
sc.camera = cam

pivot = bpy.data.objects.new("pivot", None); sc.collection.objects.link(pivot)
pivot.location = (0, 0, H*0.50)
cam.parent = pivot
trk = cam.constraints.new('TRACK_TO'); trk.target = pivot
trk.track_axis = 'TRACK_NEGATIVE_Z'; trk.up_axis = 'UP_Y'
cam_d.dof.focus_object = pivot

# ---------------------------------------------------------------- comp
# Blender 5 moved the compositor into a node GROUP on the scene - no
# scene.node_tree, no Composite node - and turned every node setting into a
# SOCKET rather than a property. So this is all inputs[...], not setattr.
#
# One node earns its place: the bloom. A lit panel without a halo reads as a
# bright sticker rather than as a screen, and that is the whole payoff shot.
sc.use_nodes = True
ng = bpy.data.node_groups.new("overwatch_comp", "CompositorNodeTree")
sc.compositing_node_group = ng
ng.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
# The RENDER LAYERS node, not the group input. Blender 5's scene compositing
# group has an Image input socket that looks like it should carry the render
# and does not - wire the group input to the output and you get black frames,
# which is a quiet way to lose an afternoon.
rl    = ng.nodes.new("CompositorNodeRLayers"); rl.location = (-400, 0)
glare = ng.nodes.new("CompositorNodeGlare"); glare.location = (0, 0)
g_out = ng.nodes.new("NodeGroupOutput"); g_out.location = ( 380, 0)

def put(node, name, val):
    if name in node.inputs:
        try:
            node.inputs[name].default_value = val
            return True
        except Exception as e:
            print("  socket %s: %s" % (name, str(e)[:60]))
    return False

put(glare, "Type", 'Bloom')
put(glare, "Quality", 'High')
put(glare, "Threshold", 0.55)
put(glare, "Strength", 0.85)
put(glare, "Size", 8.5)
put(glare, "Smoothness", 0.30)

ng.links.new(rl.outputs['Image'], glare.inputs['Image'])
ng.links.new(glare.outputs['Image'], g_out.inputs[0])

# A little motion blur on the move. Subtle - 0.3 of a frame - but it is the
# difference between a camera moving and a slideshow of positions.
sc.render.use_motion_blur = True
if hasattr(sc.render, "motion_blur_shutter"):
    sc.render.motion_blur_shutter = 0.30

still = opt("--still", 1)
if still:
    sc.frame_set(int(still[0]))

print("SCENE OK")

# ---------------------------------------------------------------- animation
FPS, SECS = 30, 8
END = FPS*SECS
sc.frame_start, sc.frame_end = 1, END


def fcurves_of(obj):
    """Blender 5 moved keyframes into slotted actions, so action.fcurves is
    gone. Handle both shapes rather than pinning a version."""
    ad = getattr(obj, "animation_data", None)
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            cb = strip.channelbag(ad.action_slot) if hasattr(strip, "channelbag") else None
            if cb:
                out.extend(cb.fcurves)
    return out


def ease(obj, interp='SINE'):
    for fc in fcurves_of(obj):
        for kp in fc.keyframe_points:
            kp.interpolation = interp
            kp.easing = 'EASE_IN_OUT'


def ramp(data, path, pts, index=None):
    for f, v in pts:
        if index is None:
            setattr(data, path, v); data.keyframe_insert(path, frame=f)
        else:
            data.inputs[index].default_value = v
            data.inputs[index].keyframe_insert("default_value", frame=f)


def snap(obj, path, pts, index=-1):
    """Keys that arrive fast and settle, rather than gliding. QUAD/EASE_OUT is
    the difference between a camera whipping to a new angle and a camera
    drifting there."""
    for f, v in pts:
        setattr(obj, path, v)
        obj.keyframe_insert(path, frame=f)
    for fc in fcurves_of(obj):
        for kp in fc.keyframe_points:
            kp.interpolation = 'QUAD'; kp.easing = 'EASE_OUT'


if SHOT == "sweeps":
    # Four fast moves, each snapping to a new angle and settling. Lit from the
    # first frame - there is nothing being revealed, this is the one that goes
    # on a feed to be watched three times.
    pivot.location = (0, 0, H*0.50)
    F = 0.50 if PORTRAIT else 0.60
    snap(pivot, "rotation_euler", [
        (1,  (0, 0, math.radians(-72))), (22, (0, 0, math.radians(-26))),
        (62, (0, 0, math.radians(-26))), (80, (0, 0, math.radians(18))),
        (116,(0, 0, math.radians(18))),  (132,(0, 0, math.radians(4))),
        (170,(0, 0, math.radians(4))),   (190,(0, 0, math.radians(44))),
        (END,(0, 0, math.radians(38)))])
    snap(cam, "location", [
        (1,  (0, F*1.22, -0.030)), (22, (0, F, -0.010)),
        (62, (0, F, -0.010)),      (80, (0, F*0.96, 0.020)),
        (116,(0, F*0.96, 0.020)),  (132,(0, F*0.62, 0.028)),   # push in close
        (170,(0, F*0.62, 0.028)),  (190,(0, F*1.04, 0.040)),
        (END,(0, F, 0.030))])
    ramp(key.data,  "energy", [(1, 11.0)])
    ramp(fill.data, "energy", [(1, 2.2)])
    ramp(rim.data,  "energy", [(1, 26.0)])
    ramp(bs, "x", [(1, 1.85)], index='Emission Strength')
    for f, idx in [(1, 0), (74, 0), (86, 1), (126, 1), (138, 2), (184, 2),
                   (196, 0), (END, 0)]:
        page_key(f, idx)
    for fc in fcurves_of(mapn):
        for kp in fc.keyframe_points:
            kp.interpolation = 'QUAD'; kp.easing = 'EASE_OUT'

elif SHOT == "hand":
    # The finger does the work and the page follows it. The swipe on this
    # panel is VERTICAL (ui_pages.c walks the stack up and down), so the
    # finger travels up, not sideways - getting that wrong would show a
    # gesture the firmware does not implement.
    pivot.location = (0, 0, scr.location.z)
    D = 0.34 if PORTRAIT else 0.30
    for f, (dist, lift) in [(1, (D, 0.004)), (END, (D*0.95, 0.0))]:
        cam.location = (0, dist, lift)
        cam.keyframe_insert("location", frame=f)
    for f, ang in [(1, -14), (END, 6)]:
        pivot.rotation_euler = (0, 0, math.radians(ang))
        pivot.keyframe_insert("rotation_euler", frame=f)
    for o in (cam, pivot):
        ease(o)
    ramp(key.data,  "energy", [(1, 11.0)])
    ramp(fill.data, "energy", [(1, 2.2)])
    ramp(rim.data,  "energy", [(1, 26.0)])
    ramp(bs, "x", [(1, 1.85)], index='Emission Strength')

    sx, sy, sz = scr.location.x, scr.location.y, scr.location.z
    OUT = sz - 0.085                       # below frame
    NEAR = sy + 0.010                       # just off the glass
    TOUCH = sy + 0.0015

    def fkey(f, loc):
        finger.location = loc
        finger.keyframe_insert("location", frame=f)

    # two swipes: in, contact, drag up, lift, out - then again
    for base, page_to in [(18, 1), (112, 2)]:
        fkey(base,      (sx + 0.040, NEAR,  OUT))
        fkey(base + 16, (sx + 0.030, TOUCH, sz - 0.013))    # contact, low
        fkey(base + 34, (sx + 0.016, TOUCH, sz + 0.018))    # drag up and in
        fkey(base + 44, (sx + 0.012, NEAR,  sz + 0.030))    # lift off
        fkey(base + 62, (sx + 0.042, NEAR,  OUT))           # away
        page_key(base + 18, page_to - 1)
        page_key(base + 36, page_to)
    page_key(1, 0)
    page_key(END, 2)
    ease(finger)
    for fc in fcurves_of(mapn):
        for kp in fc.keyframe_points:
            kp.interpolation = 'SINE'; kp.easing = 'EASE_IN_OUT'

elif SHOT == "widgets":
    # A detail shot. The barbell is cropped at the sides on purpose - the
    # subject here is the panel, and holding the whole 182 mm silhouette in
    # frame would put the screen too far away to read.
    pivot.location = (0, 0, scr.location.z)
    # 0.30 cropped the barbell to stumps. 0.36 holds the arms and most of the
    # bar while leaving the panel ~430 px wide at 1080 - still readable, and
    # the object still looks like the thing the reveal introduced.
    D = 0.36 if PORTRAIT else 0.30
    for f, (dist, lift) in [(1, (D, 0.004)), (END//2, (D*0.94, -0.004)), (END, (D, 0.004))]:
        cam.location = (0, dist, lift)
        cam.keyframe_insert("location", frame=f)
    # There and back, so the clip loops cleanly - it is going on a feed.
    for f, ang in [(1, -9), (END//2, 9), (END, -9)]:
        pivot.rotation_euler = (0, 0, math.radians(ang))
        pivot.keyframe_insert("rotation_euler", frame=f)
    for o in (cam, pivot):
        ease(o)

    # Lit from the first frame: nothing is being revealed here.
    ramp(key.data,  "energy", [(1, 11.0)])
    ramp(fill.data, "energy", [(1, 2.2)])
    ramp(rim.data,  "energy", [(1, 26.0)])
    ramp(bs, "x", [(1, 1.85)], index='Emission Strength')

    # Hold, swipe, hold. 13 frames of travel is about 0.45 s, which is what a
    # deliberate page change feels like on the panel.
    for f, idx in [(1, 0), (46, 0), (59, 1), (112, 1), (125, 2),
                   (192, 2), (205, 0), (END, 0)]:
        page_key(f, idx)
    for fc in fcurves_of(mapn):
        for kp in fc.keyframe_points:
            kp.interpolation = 'SINE'; kp.easing = 'EASE_IN_OUT'

else:
    # The reveal. Light first, screen second: a panel lit from frame one has
    # nothing left to give at frame 130.
    pivot.location = (0, 0, H*0.50)
    near, far = (0.48, 0.56) if PORTRAIT else (0.58, 0.70)
    for f, (dist, lift) in [(1, (far, -0.045)), (END, (near, 0.065))]:
        cam.location = (0, dist, lift)
        cam.keyframe_insert("location", frame=f)
    for f, ang in [(1, -34), (END, 26)]:
        pivot.rotation_euler = (0, 0, math.radians(ang))
        pivot.keyframe_insert("rotation_euler", frame=f)
    for o in (cam, pivot):
        ease(o)

    ramp(key.data,  "energy", [(1, 0.0), (26, 0.0), (86, 11.0)])
    ramp(fill.data, "energy", [(1, 0.0), (40, 0.0), (100, 2.2)])
    ramp(rim.data,  "energy", [(1, 15.0), (60, 26.0)])
    # The panel wakes: a stutter, then it holds. Real panels do this.
    ramp(bs, "x", [(1,0.0),(118,0.0),(122,1.0),(126,0.08),(131,1.5),(136,0.45),
                   (146,1.85),(END,1.85)], index='Emission Strength')
    page_key(1, 0)

print("ANIM %s %s 1..%d" % (SHOT, "9:16" if PORTRAIT else "16:9", END))

# ---------------------------------------------------------------- comp
# Blender 5 moved the compositor into a node GROUP on the scene - no
# scene.node_tree, no Composite node - and turned every node setting into a
# SOCKET rather than a property. So this is all inputs[...], not setattr.
#
# One node earns its place: the bloom. A lit panel without a halo reads as a
# bright sticker rather than as a screen, and that is the whole payoff shot.
sc.use_nodes = True
ng = bpy.data.node_groups.new("overwatch_comp", "CompositorNodeTree")
sc.compositing_node_group = ng
ng.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
# The RENDER LAYERS node, not the group input. Blender 5's scene compositing
# group has an Image input socket that looks like it should carry the render
# and does not - wire the group input to the output and you get black frames,
# which is a quiet way to lose an afternoon.
rl    = ng.nodes.new("CompositorNodeRLayers"); rl.location = (-400, 0)
glare = ng.nodes.new("CompositorNodeGlare"); glare.location = (0, 0)
g_out = ng.nodes.new("NodeGroupOutput"); g_out.location = ( 380, 0)

def put(node, name, val):
    if name in node.inputs:
        try:
            node.inputs[name].default_value = val
            return True
        except Exception as e:
            print("  socket %s: %s" % (name, str(e)[:60]))
    return False

put(glare, "Type", 'Bloom')
put(glare, "Quality", 'High')
put(glare, "Threshold", 0.55)
put(glare, "Strength", 0.85)
put(glare, "Size", 8.5)
put(glare, "Smoothness", 0.30)

ng.links.new(rl.outputs['Image'], glare.inputs['Image'])
ng.links.new(glare.outputs['Image'], g_out.inputs[0])

# A little motion blur on the move. Subtle - 0.3 of a frame - but it is the
# difference between a camera moving and a slideshow of positions.
sc.render.use_motion_blur = True
if hasattr(sc.render, "motion_blur_shutter"):
    sc.render.motion_blur_shutter = 0.30

still = opt("--still", 1)
if still:
    sc.frame_set(int(still[0]))

print("SCENE OK")

# ---------------------------------------------------------------- render
anim = opt("--anim", 1)
if anim:
    sc.render.filepath = os.path.abspath(anim[0])
    # Blender 5 split image and video behind media_type; file_format alone
    # rejects FFMPEG with a list that does not mention video at all.
    if hasattr(sc.render.image_settings, "media_type"):
        sc.render.image_settings.media_type = 'VIDEO'
    sc.render.image_settings.file_format = 'FFMPEG'
    sc.render.ffmpeg.format = 'MPEG4'
    sc.render.ffmpeg.codec = 'H264'
    sc.render.ffmpeg.constant_rate_factor = 'HIGH'
    sc.render.ffmpeg.ffmpeg_preset = 'GOOD'
    sc.render.ffmpeg.gopsize = 12
    import time as _t
    t0 = _t.time()
    bpy.ops.render.render(animation=True)
    print("ANIM DONE %.1f min -> %s" % ((_t.time()-t0)/60, sc.render.filepath))

out = opt("--render", 1)
if out:
    sc.render.filepath = os.path.abspath(out[0])
    sc.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
    print("WROTE", sc.render.filepath)

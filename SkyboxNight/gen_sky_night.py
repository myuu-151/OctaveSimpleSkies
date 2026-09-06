#!/usr/bin/env python
# Night variant of the sky dome assets:
#   T_SkyGradientNight.oct  purple-blue ramp + horizon haze alpha
#   T_CloudsNight.oct       sparser moonlit two-tone clouds + baked stars in the gaps
#   M_SkyNight.oct          same TEV stack as day
#   SM_SkyDomeNight.oct     same dome, bound to M_SkyNight
# Writes into testproj\Assets alongside the day set (unique names/uuids).
import math
import struct
import os

OUT = r"C:\Users\NoSig\Documents\testproj\Assets"

MAGIC = 0x4F435421
VERSION = 13
TYPE_TEXTURE = 0xCDBBDA30
TYPE_STATICMESH = 0xD41D0D1D
TYPE_MATERIALLITE = 0xA3ED4C6F

UUID_GRAD = 0x51C0FFEE00000011
UUID_CLOUD = 0x51C0FFEE00000012
UUID_MAT = 0x51C0FFEE00000013
UUID_MESH = 0x51C0FFEE00000014
UUID_MOON_TEX = 0x51C0FFEE00000015
UUID_MOON_MAT = 0x51C0FFEE00000016
UUID_MOON_MESH = 0x51C0FFEE00000017
UUID_STARS = 0x51C0FFEE00000018
UUID_STARMAT = 0x51C0FFEE0000001A
UUID_STARMESH = 0x51C0FFEE0000001B
UUID_CLOUDMAT = 0x51C0FFEE0000001C
UUID_CLOUDMESH = 0x51C0FFEE0000001D
UUID_CLOUDHAZE = 0x51C0FFEE0000001E


def u8(v): return struct.pack("<B", v)
def u32(v): return struct.pack("<I", v & 0xFFFFFFFF)
def i32(v): return struct.pack("<i", v)
def u64(v): return struct.pack("<Q", v)
def f32(v): return struct.pack("<f", v)
def s(v):
    b = v.encode("ascii")
    return u32(len(b)) + b


def header(type_id, uuid, name):
    return u32(MAGIC) + u32(VERSION) + u32(type_id) + u8(0) + u64(uuid) + s(name)


def asset_ref(uuid, name):
    return u8(1) + u64(uuid) + s(name)


def null_ref():
    return u8(1) + u64(0) + s("")


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def mix(a, b, t):
    return a + (b - a) * t


def write_texture(path, name, uuid, w, h, pixels, wrap, mipmapped=False):
    mips = (int(math.log(min(w, h), 2)) + 1) if mipmapped else 1
    data = header(TYPE_TEXTURE, uuid, name)
    data += u32(w) + u32(h) + u32(mips) + u32(1)
    data += u32(2) + u32(1) + u32(wrap)
    data += u8(1 if mipmapped else 0) + u8(0) + u8(1)
    data += u8(0) + u8(1)
    assert len(pixels) == w * h * 4
    data += bytes(pixels)
    with open(path, "wb") as f:
        f.write(data)
    print("wrote %s (%d bytes)" % (path, len(data)))


# ------------------------------------------------- night palette (inspo: deep
# blue-violet, moonlit lavender cloud edges, dense clustered stars, glowing moon)
ZENITH = (0.015, 0.02, 0.09)     # near-black navy
HORIZON = (0.10, 0.26, 0.58)     # luminous azure glow (softened)
NEB_DEEP = (0.05, 0.10, 0.32)    # nebula ramp: faint outer wisps
NEB_MID = (0.12, 0.32, 0.72)     # glowing azure body
NEB_CORE = (0.62, 0.84, 1.00)    # cyan-white core
COVERAGE = 0.52
SUN = (0.45, -0.60)              # "moon" direction for the two-tone split
BASE = 4
STAR_DENSITY = 0.0045            # base density, modulated by cluster noise
BRIGHT_STAR = 0.0005


def gen_gradient():
    w, h = 8, 256
    px = bytearray()
    # v axis spans elevation -30..90 deg so the haze line can sit BELOW the
    # geometric horizon (sky content wraps down past eye level)
    for row in range(h):
        v = row / (h - 1.0)
        elev = math.radians(v * 120.0 - 30.0)
        diry = math.sin(elev)
        t = pow(max(diry, 0.0), 0.60)   # glow tucked against the low horizon
        r = mix(HORIZON[0], ZENITH[0], t)
        g = mix(HORIZON[1], ZENITH[1], t)
        b = mix(HORIZON[2], ZENITH[2], t)
        # stars full down to ~6 deg, 50% through the glow band, then dissolving
        # completely toward the bottom of the bowl (~ -28 deg)
        base = 1.0 - smoothstep(-0.10, 0.10, diry)
        deep = smoothstep(-0.07, -0.017, diry)
        haze = base * (1.0 - 0.5 * deep)
        px += bytes((int(r * 255), int(g * 255), int(b * 255), int(haze * 255))) * w
    return w, h, px


def gen_cloud_haze():
    # Fade mask for the CLOUD dome (Modulate stage): white RGB, alpha ramps
    # the cloud opacity to zero near the horizon. Modulate multiplies the
    # full RGBA identically on GX and Vulkan -- clouds truly fade out
    # instead of becoming an opaque haze wall (the Decal alpha divergence).
    w, h = 8, 256
    px = bytearray()
    for row in range(h):
        v = row / (h - 1.0)
        elev = math.radians(v * 120.0 - 30.0)
        diry = math.sin(elev)
        fade = smoothstep(0.03, 0.20, diry)   # clouds gone by ~2 deg, full by ~12
        px += bytes((255, 255, 255, int(fade * 255))) * w
    return w, h, px


def hash2(ix, iy, period, seed):
    ix %= period
    iy %= period
    n = (ix * 374761393 + iy * 668265263 + seed * 2246822519) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) & 0xFFFFFFFF
    n = (n * 1274126177) & 0xFFFFFFFF
    n = (n ^ (n >> 16)) & 0xFFFFFFFF
    return n / 4294967295.0


def vnoise(x, y, period, seed):
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    ux = fx * fx * (3.0 - 2.0 * fx)
    uy = fy * fy * (3.0 - 2.0 * fy)
    ix, iy = int(ix), int(iy)
    a = hash2(ix, iy, period, seed)
    b = hash2(ix + 1, iy, period, seed)
    c = hash2(ix, iy + 1, period, seed)
    d = hash2(ix + 1, iy + 1, period, seed)
    return mix(mix(a, b, ux), mix(c, d, ux), uy)


def fbm(x, y, base_period, seed):
    v, amp = 0.0, 0.5
    freq = 1
    for octave in range(5):
        v += amp * vnoise(x * freq, y * freq, base_period * freq, seed + octave * 101)
        freq *= 2
        amp *= 0.5
    return v


def gen_clouds():
    # Clouds at 512 with uniform-density single-pixel stars baked into the
    # clear-sky gaps -- the original look. Plane-projected UV0.
    base_size = 512
    size = 512
    sl = math.hypot(SUN[0], SUN[1])
    sx, sy = SUN[0] / sl * 0.35, SUN[1] / sl * 0.35
    # nebula: a low-frequency macro field carves the sky into irregular
    # regions (thick banks / clear gaps), a faint veil fills volume between
    # them, and warped anisotropic wisps live inside the dense regions.
    ANISO = 2            # must be an integer or the noise lattice won't tile (seams)
    lo = [(0.0, 0.0, 0.0, 0.0)] * (base_size * base_size)
    for j in range(base_size):
        y = j / base_size * BASE * ANISO
        ym = j / base_size * BASE
        for i in range(base_size):
            x = i / base_size * BASE
            # macro density: where the nebula lives (most of the sky; the
            # dark gaps are the exception, like the reference)
            macro = fbm(x * 0.5 + 3.1, ym * 0.5 + 9.4, BASE // 2, 501)
            macro = smoothstep(0.15, 0.60, macro)   # wide, soft bank edges
            wx = fbm(x * 0.5 + 13.7, y * 0.5 + 13.7, BASE // 2, 7) - 0.5
            wy = fbm(x * 0.5 - 7.2, y * 0.5 - 7.2, BASE // 2, 23) - 0.5
            wx += (fbm(x + 31.1, y + 5.5, BASE, 61) - 0.5) * 0.6
            wy += (fbm(x - 17.9, y + 41.3, BASE, 89) - 0.5) * 0.6
            pxx = x + wx * 2.8
            pyy = y + wy * 2.8
            f = fbm(pxx, pyy, BASE, 42)
            fil = fbm(pxx * 2.0 + 7.7, pyy * 2.0 - 3.3, BASE * 2, 137)
            # pure volume veil -- no bright wisp strands, just soft glowing
            # body with gentle internal variation
            veil = macro * (0.55 * (0.5 + 0.5 * f))
            mask = min(0.95, veil)
            dens = veil * (0.65 + 0.25 * smoothstep(0.35, 0.65, fil))
            if dens < 0.5:
                t2 = dens * 2.0
                r = mix(NEB_DEEP[0], NEB_MID[0], t2)
                g = mix(NEB_DEEP[1], NEB_MID[1], t2)
                b = mix(NEB_DEEP[2], NEB_MID[2], t2)
            else:
                t2 = (dens - 0.5) * 2.0
                r = mix(NEB_MID[0], NEB_CORE[0], t2)
                g = mix(NEB_MID[1], NEB_CORE[1], t2)
                b = mix(NEB_MID[2], NEB_CORE[2], t2)
            lo[j * base_size + i] = (r, g, b, mask * 0.9)

    def lo_sample(u, v):
        # bilinear, wrapping
        u = u * base_size - 0.5
        v = v * base_size - 0.5
        x0, y0 = int(math.floor(u)), int(math.floor(v))
        fx, fy = u - x0, v - y0
        acc = [0.0, 0.0, 0.0, 0.0]
        for (xx, yy, wgt) in ((x0, y0, (1 - fx) * (1 - fy)),
                              (x0 + 1, y0, fx * (1 - fy)),
                              (x0, y0 + 1, (1 - fx) * fy),
                              (x0 + 1, y0 + 1, fx * fy)):
            p = lo[(yy % base_size) * base_size + (xx % base_size)]
            for c in range(4):
                acc[c] += p[c] * wgt
        return acc

    px = bytearray(size * size * 4)
    alpha = bytearray(size * size)
    for j in range(size):
        for i in range(size):
            r, g, b, a = lo_sample(i / size, j / size)
            o = (j * size + i) * 4
            px[o] = int(min(r, 1.0) * 255)
            px[o + 1] = int(min(g, 1.0) * 255)
            px[o + 2] = int(min(b, 1.0) * 255)
            px[o + 3] = int(min(a, 1.0) * 255)
            alpha[j * size + i] = px[o + 3]

    return size, size, px


def gen_stars():
    # Stars-only layer for the main dome (Add stage on UV0, plane projection).
    # Uniform density, single-pixel at 1024 (small), static -> no shimmer.
    size = 1024
    period = 1 << 20
    star_dens = 0.006
    px = bytearray(size * size * 4)
    for j in range(size):
        for i in range(size):
            if hash2(i, j, period, 777) <= 1.0 - star_dens:
                continue
            h2 = hash2(i, j, period, 991)
            bright = 0.60 + 0.40 * h2 * h2
            tint = hash2(i, j, period, 555)
            o = (j * size + i) * 4
            if tint < 0.30:
                # warm star (pale rose-gold, like the reference)
                px[o] = int(bright * 255)
                px[o + 1] = int(bright * 0.86 * 255)
                px[o + 2] = int(bright * 0.80 * 255)
            else:
                # cool blue-white
                px[o] = int(bright * (0.78 + 0.14 * tint) * 255)
                px[o + 1] = int(bright * (0.84 + 0.12 * tint) * 255)
                px[o + 2] = int(bright * 255)
            px[o + 3] = 255
    return size, size, px



def material_tail():
    d = b""
    for _ in range(2):
        d += f32(0) + f32(0) + f32(1) + f32(1)
    d += f32(1) + f32(1) + f32(1) + f32(1)
    d += f32(1) + f32(0) + f32(0) + f32(0)
    d += f32(1.0) + f32(0.0) + f32(0.0) + f32(0.0)
    d += u32(2)
    d += f32(1.0) + f32(0.5) + f32(32.0)
    d += i32(0)
    d += u8(0) + u8(0) + u8(0) + u8(0)   # depthTestDisabled, fresnel, applyFog OFF, CullMode None
    return d


def gen_material(path):
    # Outer opaque sky dome: gradient base -> static stars (Add, uv0 plane
    # projection) -> horizon haze (Decal, uv1) which also fades the stars low.
    d = header(TYPE_MATERIALLITE, UUID_MAT, "M_SkyNight")
    d += u32(0)
    d += u32(0)                     # Unlit
    d += u32(0)                     # Opaque
    d += u32(1)                     # VertexColorMode::Modulate
    d += u32(3)
    d += asset_ref(UUID_GRAD, "T_SkyGradientNight") + u8(1) + u8(0)
    d += asset_ref(UUID_STARS, "T_StarsNight") + u8(0) + u8(3)
    d += asset_ref(UUID_GRAD, "T_SkyGradientNight") + u8(1) + u8(2)
    d += null_ref() + u8(0) + u8(1)
    d += material_tail()
    with open(path, "wb") as f:
        f.write(d)
    print("wrote %s (%d bytes)" % (path, len(d)))


def gen_cloud_material(path):
    # Inner translucent cloud dome, scrolled by the wind independently of the
    # stars. Haze decal tints the low clouds into the horizon glow.
    d = header(TYPE_MATERIALLITE, UUID_CLOUDMAT, "M_CloudsNight")
    d += u32(0)
    d += u32(0)                     # Unlit
    d += u32(2)                     # BlendMode::Translucent
    d += u32(1)                     # VertexColorMode::Modulate
    d += u32(2)
    d += asset_ref(UUID_CLOUD, "T_CloudsNight") + u8(0) + u8(0)
    d += asset_ref(UUID_CLOUDHAZE, "T_CloudHazeNight") + u8(1) + u8(1)
    d += null_ref() + u8(0) + u8(1)
    d += null_ref() + u8(0) + u8(1)
    d += material_tail()
    with open(path, "wb") as f:
        f.write(d)
    print("wrote %s (%d bytes)" % (path, len(d)))


RADIUS = 900.0
SEGMENTS = 32
ELEVATIONS = [-80.0, -50.0, -25.0, -16.0, -10.0, -4.0, 0.0, 4.0, 9.0, 15.0, 22.0, 30.0, 40.0, 52.0, 66.0, 80.0]
PLANE_SCALE = 1.6 / 4.0
MIN_DIRY = math.sin(math.radians(1.5))
FISHEYE_TILES = 2.2     # texture tiles from zenith to horizon


def gen_mesh(path, radius=None, mesh_uuid=None, mesh_name=None,
             mat_uuid=None, mat_name=None, fisheye=False, min_elev=None):
    radius = radius or RADIUS
    mesh_uuid = mesh_uuid or UUID_MESH
    mesh_name = mesh_name or "SM_SkyDomeNight"
    mat_uuid = mat_uuid or UUID_MAT
    mat_name = mat_name or "M_SkyNight"
    elevations = ELEVATIONS if min_elev is None else [e for e in ELEVATIONS if e >= min_elev]
    verts = []
    for elev in elevations:
        er = math.radians(elev)
        cy, sy_ = math.cos(er), math.sin(er)
        rr = (1.0 - elev / 90.0) * FISHEYE_TILES
        for seg in range(SEGMENTS + 1):
            az = seg / SEGMENTS * 2.0 * math.pi
            dx = math.cos(az) * cy
            dz = math.sin(az) * cy
            dy = sy_
            if fisheye:
                # uniform texel (and star) density across the dome
                u0 = math.cos(az) * rr
                v0 = math.sin(az) * rr
            else:
                dyc = max(dy, MIN_DIRY)
                u0 = dx / dyc * PLANE_SCALE
                v0 = dz / dyc * PLANE_SCALE
            v1 = max(0.0, min(1.0, (elev + 30.0) / 120.0))
            verts.append((dx * radius, dy * radius, dz * radius,
                          u0, v0, 0.5, v1, -dx, -dy, -dz))
    pole_index = len(verts)
    verts.append((0.0, radius, 0.0, 0.0, 0.0, 0.5, 1.0, 0.0, -1.0, 0.0))

    idx = []
    cols = SEGMENTS + 1
    for ring in range(len(elevations) - 1):
        for seg_i in range(SEGMENTS):
            a = ring * cols + seg_i
            b = a + 1
            c = a + cols
            dd = c + 1
            idx += [a, b, c, b, dd, c]
    top = (len(elevations) - 1) * cols
    for seg_i in range(SEGMENTS):
        idx += [top + seg_i, top + seg_i + 1, pole_index]

    d = header(TYPE_STATICMESH, mesh_uuid, mesh_name)
    d += u32(len(verts)) + u32(len(idx)) + u32(2)
    d += asset_ref(mat_uuid, mat_name)
    d += u8(0) + u8(0)
    for v in verts:
        d += b"".join(f32(c) for c in v)
    for ii in idx:
        d += u32(ii)
    d += u8(0) + u32(0)
    d += f32(0) + f32(0) + f32(0) + f32(0)
    with open(path, "wb") as f:
        f.write(d)
    print("wrote %s (%d verts, %d indices, %d bytes)" % (path, len(verts), len(idx), len(d)))


def main():
    for sub in ("Textures", "Materials", "Meshes"):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    w, h, px = gen_gradient()
    write_texture(os.path.join(OUT, "Textures", "T_SkyGradientNight.oct"),
                  "T_SkyGradientNight", UUID_GRAD, w, h, px, wrap=0)
    w, h, px = gen_clouds()
    write_texture(os.path.join(OUT, "Textures", "T_CloudsNight.oct"),
                  "T_CloudsNight", UUID_CLOUD, w, h, px, wrap=1)
    w, h, px = gen_stars()
    write_texture(os.path.join(OUT, "Textures", "T_StarsNight.oct"),
                  "T_StarsNight", UUID_STARS, w, h, px, wrap=1)
    gen_material(os.path.join(OUT, "Materials", "M_SkyNight.oct"))
    gen_cloud_material(os.path.join(OUT, "Materials", "M_CloudsNight.oct"))
    gen_mesh(os.path.join(OUT, "Meshes", "SM_SkyDomeNight.oct"), fisheye=True)
    gen_mesh(os.path.join(OUT, "Meshes", "SM_CloudDomeNight.oct"),
             radius=860.0, mesh_uuid=UUID_CLOUDMESH, mesh_name="SM_CloudDomeNight",
             mat_uuid=UUID_CLOUDMAT, mat_name="M_CloudsNight")


if __name__ == "__main__":
    main()

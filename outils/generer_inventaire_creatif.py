#!/usr/bin/env python3
"""Génère les icônes de l'inventaire créatif (Minecraft 26.3) pour index.html.

Sortie :
  assets/creatif/items.png  : icônes des items plats, 16x16 px (les textures du jeu telles quelles)
  assets/creatif/blocs.png  : icônes des blocs en 3D, BLOCK x BLOCK px (dessinées nettes, sans lissage)
  assets/creatif/items.json : [{ "id", "nom" (français), "a" (0 = items.png, 1 = blocs.png), "i" (index), "o" (onglet) }]

Les items « plats » (épées, nourriture…) sont les textures du jeu telles quelles. Les blocs n'existent
pas en image dans les fichiers du jeu (il les dessine en 3D à partir de leurs modèles) : on fait le même
rendu ici. Les onglets du mode créatif ne sont pas décrits dans les fichiers du jeu : l'onglet de chaque
item est déduit de son identifiant (fonction onglet).

Source : un clone (sparse) de https://github.com/InventivetalentDev/minecraft-assets, branche 26.3,
avec assets/minecraft/{items,models}/_all.json, lang/fr_fr.json et les textures item/, block/,
colormap/, entity/{chest,skeleton,zombie,creeper,piglin,player}.

Usage : python3 outils/generer_inventaire_creatif.py <dossier du clone> <dossier des json _all/lang>
"""
import json, math, os, sys
from PIL import Image, ImageDraw

SRC, JSONS = sys.argv[1], sys.argv[2]
TEX = os.path.join(SRC, 'assets/minecraft/textures')
OUT = os.path.join(os.path.dirname(__file__), '..', 'assets', 'creatif')
ICON = 16          # taille des icônes plates (px) = taille des textures du jeu
BLOCK = int(os.environ.get('BLOCK', 32))   # taille des icônes 3D (px) : rendu net à l'échelle de l'écran
COLS = 40

items = json.load(open(os.path.join(JSONS, 'items__all.json')))
models = {}
for kind in ('item', 'block'):
    for k, v in json.load(open(os.path.join(JSONS, f'models_{kind}__all.json'))).items():
        models[f'{kind}/{k}'] = v
lang = json.load(open(os.path.join(JSONS, 'lang_fr_fr.json')))

def strip(name):
    return name.split(':', 1)[-1]

_tex_cache = {}
def texture(path):
    """Texture (PIL RGBA) ; pour une texture animée, la première image carrée."""
    path = strip(path)
    if path not in _tex_cache:
        f = os.path.join(TEX, path + '.png')
        if not os.path.exists(f):
            _tex_cache[path] = None
        else:
            im = Image.open(f).convert('RGBA')
            if im.height > im.width:
                im = im.crop((0, 0, im.width, im.width))
            _tex_cache[path] = im
    return _tex_cache[path]

def resolve_model(name):
    """Fusionne la chaîne de parents : textures, éléments, affichage GUI, type."""
    name = strip(name)
    chain = []
    while name and name not in ('builtin/generated', 'builtin/entity'):
        m = models.get(name)
        if m is None:
            break
        chain.append(m)
        name = strip(m['parent']) if 'parent' in m else None
    generated = name == 'builtin/generated'
    textures, elements, gui = {}, None, None
    for m in reversed(chain):
        textures.update(m.get('textures', {}))
        if 'elements' in m:
            elements = m['elements']
        if 'display' in m and 'gui' in m['display']:
            gui = m['display']['gui']
    def ref(t, depth=0):
        if isinstance(t, dict):   # format 26.3 : {"sprite": "...", ...}
            t = t.get('sprite')
        while t and t.startswith('#') and depth < 10:
            if isinstance(t, dict):
                t = t.get('sprite')
            t = textures.get(t[1:]); depth += 1
            if isinstance(t, dict):
                t = t.get('sprite')
        return t
    return {'generated': generated, 'textures': {k: ref(v) for k, v in textures.items()},
            'elements': elements, 'gui': gui, 'ref': ref}

def argb(v):
    v &= 0xFFFFFFFF
    return ((v >> 16) & 255, (v >> 8) & 255, v & 255)

def colormap(kind, temp, down):
    im = texture(f'colormap/{kind}')
    temp = max(0.0, min(1.0, temp)); down = max(0.0, min(1.0, down)) * temp
    return im.getpixel((int((1 - temp) * 255), int((1 - down) * 255)))[:3]

def tint_color(t):
    typ = strip(t.get('type', ''))
    if typ == 'constant':
        return argb(t['value'])
    if typ == 'grass':
        return colormap('grass', t.get('temperature', 0.5), t.get('downfall', 1.0))
    if 'default' in t:
        return argb(t['default'])
    return (255, 255, 255)

def tinted(im, color):
    if color == (255, 255, 255):
        return im
    r, g, b, a = im.split()
    r = r.point(lambda x: x * color[0] // 255); g = g.point(lambda x: x * color[1] // 255); b = b.point(lambda x: x * color[2] // 255)
    return Image.merge('RGBA', (r, g, b, a))

def shade(im, k):
    if k >= 1:
        return im
    r, g, b, a = im.split()
    f = lambda x: int(x * k)
    return Image.merge('RGBA', (r.point(f), g.point(f), b.point(f), a))

# --- Rendu 3D (projection orthographique comme l'affichage GUI de Minecraft) ---
def rot_matrix(rx, ry, rz):
    rx, ry, rz = map(math.radians, (rx, ry, rz))
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    X = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    Y = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    Z = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
    mul = lambda A, B: [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mul(mul(X, Y), Z)

def apply(M, v):
    return [sum(M[i][k] * v[k] for k in range(3)) for i in range(3)]

DEFAULT_GUI = {'rotation': [30, 225, 0], 'translation': [0, 0, 0], 'scale': [0.625] * 3}

def face_corners(d, f, t):
    """Coins 3D (uv haut-gauche, haut-droit, bas-gauche) d'une face, et UV par défaut."""
    x1, y1, z1 = f; x2, y2, z2 = t
    if d == 'north': return [(x2, y2, z1), (x1, y2, z1), (x2, y1, z1)], (16 - x2, 16 - y2, 16 - x1, 16 - y1)
    if d == 'south': return [(x1, y2, z2), (x2, y2, z2), (x1, y1, z2)], (x1, 16 - y2, x2, 16 - y1)
    if d == 'east':  return [(x2, y2, z2), (x2, y2, z1), (x2, y1, z2)], (16 - z2, 16 - y2, 16 - z1, 16 - y1)
    if d == 'west':  return [(x1, y2, z1), (x1, y2, z2), (x1, y1, z1)], (z1, 16 - y2, z2, 16 - y1)
    if d == 'up':    return [(x1, y2, z1), (x2, y2, z1), (x1, y2, z2)], (x1, z1, x2, z2)
    return [(x1, y1, z2), (x2, y1, z2), (x1, y1, z1)], (x1, 16 - z2, x2, 16 - z1)   # down

NORMALS = {'north': (0, 0, -1), 'south': (0, 0, 1), 'east': (1, 0, 0), 'west': (-1, 0, 0), 'up': (0, 1, 0), 'down': (0, -1, 0)}

def render_elements(elements, get_tex, gui, tints=(), offset=(0, 0, 0)):
    gui = gui or DEFAULT_GUI
    R = rot_matrix(*gui.get('rotation', [0, 0, 0]))
    T = gui.get('translation', [0, 0, 0]); S = gui.get('scale', [1, 1, 1])
    size = BLOCK
    def project(p):
        v = [(p[i] + offset[i]) / 16 - 0.5 for i in range(3)]
        v = apply(R, [v[i] * S[i] for i in range(3)])
        v = [v[i] + T[i] / 16 for i in range(3)]
        return (size / 2 + v[0] * size, size / 2 - v[1] * size, v[2])
    faces = []
    for el in elements:
        f, t = el['from'], el['to']
        rot = el.get('rotation')
        def el_rot(p, rot=rot):
            if not rot or not rot.get('angle'):
                return p
            o = rot['origin']; a = math.radians(rot['angle']); ax = rot['axis']
            q = [p[i] - o[i] for i in range(3)]
            c, s_ = math.cos(a), math.sin(a)
            if ax == 'x': q = [q[0], q[1] * c - q[2] * s_, q[1] * s_ + q[2] * c]
            if ax == 'y': q = [q[0] * c + q[2] * s_, q[1], -q[0] * s_ + q[2] * c]
            if ax == 'z': q = [q[0] * c - q[1] * s_, q[0] * s_ + q[1] * c, q[2]]
            return [q[i] + o[i] for i in range(3)]
        for d, face in el.get('faces', {}).items():
            tex = get_tex(face.get('texture'))
            if tex is None:
                continue
            corners, duv = face_corners(d, f, t)
            corners = [el_rot(c) for c in corners]
            # normale transformée (culling + ombrage)
            n = apply(R, el_rot_vec(NORMALS[d], rot))
            if n[2] <= 1e-4:
                continue
            uv = face.get('uv', duv)
            P = [project(c) for c in corners]
            depth = sum(project(c)[2] for c in corners) / 3
            ti = face.get('tintindex')
            color = tint_color(tints[ti]) if ti is not None and ti < len(tints) else (255, 255, 255)
            if n[1] > 0.5: k = 1.0
            elif n[0] < 0: k = 0.8
            else: k = 0.6
            if not (gui.get('_light', 'side') == 'side'):
                k = 1.0
            faces.append((depth, P, tex, uv, face.get('rotation', 0), color, k))
    faces.sort(key=lambda f: f[0])
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    for depth, P, tex, uv, frot, color, k in faces:
        draw_face(out, P, tex, uv, frot, color, k)
    return out

def el_rot_vec(v, rot):
    if not rot or not rot.get('angle'):
        return list(v)
    a = math.radians(rot['angle']); ax = rot['axis']; c, s = math.cos(a), math.sin(a); x, y, z = v
    if ax == 'x': return [x, y * c - z * s, y * s + z * c]
    if ax == 'y': return [x * c + z * s, y, -x * s + z * c]
    return [x * c - y * s, x * s + y * c, z]

def draw_face(out, P, tex, uv, frot, color, k):
    w = tex.width
    u1, v1, u2, v2 = [c * w / 16 for c in uv]
    # UV des 3 coins (haut-gauche, haut-droit, bas-gauche), tournés selon "rotation"
    quad = [(u1, v1), (u2, v1), (u2, v2), (u1, v2)]
    r = (frot // 90) % 4
    quad = quad[r:] + quad[:r]
    (a_u, a_v), (b_u, b_v), _, (c_u, c_v) = quad
    (x0, y0, _), (x1, y1, _), (x2, y2, _) = P
    # matrice écran -> texture : on inverse texture -> écran
    # écran = P0 + s*(P1-P0) + t*(P2-P0) ; texture = A + s*(B-A) + t*(C-A)
    ex, ey, fx, fy = x1 - x0, y1 - y0, x2 - x0, y2 - y0
    det = ex * fy - ey * fx
    if abs(det) < 1e-6:
        return
    # s,t en fonction de (X,Y)
    ia, ib, ic, id_ = fy / det, -fx / det, -ey / det, ex / det
    su, sv, tu, tv = b_u - a_u, b_v - a_v, c_u - a_u, c_v - a_v
    # texture = A + (ia*(X-x0) + ib*(Y-y0))*(su,sv) + (ic*(X-x0) + id*(Y-y0))*(tu,tv)
    A = ia * su + ic * tu; B = ib * su + id_ * tu
    C = a_u - A * x0 - B * y0
    D = ia * sv + ic * tv; E = ib * sv + id_ * tv
    F = a_v - D * x0 - E * y0
    src = shade(tinted(tex, color), k)
    layer = src.transform(out.size, Image.AFFINE, (A, B, C, D, E, F), resample=Image.NEAREST)
    mask = Image.new('L', out.size, 0)
    x3, y3 = x1 + fx, y1 + fy
    ImageDraw.Draw(mask).polygon([(x0, y0), (x1, y1), (x3, y3), (x2, y2)], fill=255)
    layer.putalpha(Image.composite(layer.getchannel('A'), Image.new('L', out.size, 0), mask))
    out.alpha_composite(layer)

def render_flat(layers, tints):
    out = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    for i, path in enumerate(layers):
        t = texture(path)
        if t is None:
            continue
        t = t.resize((16, 16), Image.NEAREST) if t.size != (16, 16) else t
        color = tint_color(tints[i]) if i < len(tints) else (255, 255, 255)
        out.alpha_composite(tinted(t, color))
    return out.resize((ICON, ICON), Image.NEAREST)

def render_model(name, tints=()):
    m = resolve_model(name)
    if m['generated']:
        layers = [m['textures'][f'layer{i}'] for i in range(10) if m['textures'].get(f'layer{i}')]
        return render_flat(layers, tints)
    if m['elements']:
        gui = dict(m['gui'] or DEFAULT_GUI)
        get_tex = lambda t: texture(m['ref'](t)) if t else None
        return render_elements(m['elements'], get_tex, gui, tints)
    return None

# --- Items rendus par du code dans le jeu (coffres, têtes, bannières...) ---
def cube_from_images(top, front, side, size=(1, 0, 1, 15, 14, 15)):
    x1, y1, z1, x2, y2, z2 = size
    imgs = {'#top': top, '#front': front, '#side': side}
    el = [{'from': [x1, y1, z1], 'to': [x2, y2, z2], 'faces': {
        'up': {'texture': '#top', 'uv': [0, 0, 16, 16]},
        'east': {'texture': '#front', 'uv': [0, 0, 16, 16]},
        'north': {'texture': '#side', 'uv': [0, 0, 16, 16]}}}]
    return render_elements(el, lambda t: imgs.get(t), DEFAULT_GUI)

def chest_icon(texname):
    im = texture(f'entity/chest/{texname}')
    if im is None:
        return None
    s = im.width // 64
    c = lambda x, y, w, h: im.crop((x * s, y * s, (x + w) * s, (y + h) * s))
    top = c(28, 0, 14, 14)
    front = Image.new('RGBA', (14 * s, 14 * s)); front.alpha_composite(c(42, 14, 14, 5), (0, 0)); front.alpha_composite(c(42, 34, 14, 9), (0, 5 * s))
    front.alpha_composite(c(1, 1, 2, 4), (6 * s, 2 * s))
    side = Image.new('RGBA', (14 * s, 14 * s)); side.alpha_composite(c(28, 14, 14, 5), (0, 0)); side.alpha_composite(c(28, 34, 14, 9), (0, 5 * s))
    return cube_from_images(top, front, side)

SKULLS = {'skeleton_skull': 'entity/skeleton/skeleton', 'wither_skeleton_skull': 'entity/skeleton/wither_skeleton',
          'zombie_head': 'entity/zombie/zombie', 'creeper_head': 'entity/creeper/creeper', 'piglin_head': 'entity/piglin/piglin',
          'player_head': 'entity/player/wide/steve'}
def skull_icon(item):
    im = texture(SKULLS.get(item, ''))
    if im is None:
        return None
    s = im.width // 64
    c = lambda x, y: im.crop((x * s, y * s, (x + 8) * s, (y + 8) * s))
    return cube_from_images(c(8, 0), c(8, 8), c(0, 8), size=(3, 3, 3, 13, 13, 13))

DYE = {'white': '#F9FFFE', 'orange': '#F9801D', 'magenta': '#C74EBD', 'light_blue': '#3AB3DA', 'yellow': '#FED83D', 'lime': '#80C71F',
       'pink': '#F38BAA', 'gray': '#474F52', 'light_gray': '#9D9D97', 'cyan': '#169C9C', 'purple': '#8932B8', 'blue': '#3C44AA',
       'brown': '#835432', 'green': '#5E7C16', 'red': '#B02E26', 'black': '#1D1D21'}
def banner_icon(color):
    im = Image.new('RGBA', (16, 16)); d = ImageDraw.Draw(im)
    d.rectangle((7, 0, 8, 15), fill='#6b5132'); d.rectangle((3, 1, 12, 1), fill='#6b5132')
    d.rectangle((4, 2, 11, 12), fill=DYE.get(color, '#F9FFFE')); d.rectangle((4, 12, 11, 12), fill='#00000040')
    return im.resize((ICON, ICON), Image.NEAREST)

def shield_icon():
    im = Image.new('RGBA', (16, 16)); d = ImageDraw.Draw(im)
    d.polygon([(3, 1), (12, 1), (12, 10), (7.5, 14), (3, 10)], fill='#8a8a8a')
    d.polygon([(4, 2), (11, 2), (11, 9.5), (7.5, 12.8), (4, 9.5)], fill='#6b4a2b')
    return im.resize((ICON, ICON), Image.NEAREST)

def special_icon(item, spec):
    kind = strip(spec['model']['type'])
    if kind == 'chest':
        return chest_icon(strip(spec['model'].get('texture', 'minecraft:normal')))
    if kind in ('head', 'player_head'):
        return skull_icon(item)
    if kind == 'banner':
        return banner_icon(spec['model'].get('color', 'white'))
    if kind == 'shield':
        return shield_icon()
    base = resolve_model(spec['base'])
    part = base['textures'].get('particle')
    if kind == 'shulker_box':
        t = texture(f"block/{item}") or texture(part or '')
        return cube_from_images(t, t, t, size=(0, 0, 0, 16, 16, 16)) if t else None
    if part and texture(part):
        t = texture(part)
        if part.split(':')[-1].startswith('block/'):
            return cube_from_images(t, t, t, size=(0, 0, 0, 16, 16, 16))
        return render_flat([part], ())
    return None

def pick(node):
    """Choisit la variante « par défaut » d'une définition d'item."""
    typ = strip(node['type'])
    if typ == 'model': return node
    if typ == 'select': return pick(node['fallback']) if 'fallback' in node else pick(node['cases'][0]['model'])
    if typ == 'condition': return pick(node['on_false'])
    if typ == 'range_dispatch': return pick(node['fallback']) if 'fallback' in node else pick(node['entries'][0]['model'])
    return node   # special, composite

def icon_for(item, node):
    node = pick(node)
    typ = strip(node['type'])
    if typ == 'model':
        return render_model(node['model'], node.get('tints', []))
    if typ == 'special':
        return special_icon(item, node)
    if typ == 'composite':
        # ex. lits : on assemble les modèles en décalant le pied d'un bloc
        els_all = []
        for sub in node['models']:
            sub = pick(sub)
            if strip(sub['type']) != 'model':
                continue
            m = resolve_model(sub['model'])
            tr = (sub.get('transformation') or {}).get('translation', [0, 0, 0])
            for el in m['elements'] or []:
                el = json.loads(json.dumps(el))
                el['from'] = [el['from'][i] + tr[i] * 16 for i in range(3)]
                el['to'] = [el['to'][i] + tr[i] * 16 for i in range(3)]
                for f in el['faces'].values():
                    f['texture'] = m['ref'](f['texture'])
                els_all.append(el)
        if not els_all:
            return None
        xs = [c for el in els_all for c in (el['from'][2], el['to'][2])]
        off = (0, 0, -(min(xs) + max(xs)) / 2 + 8)
        return render_elements(els_all, lambda t: texture(t) if t else None, {'rotation': [30, 160, 0], 'translation': [0, 0, 0], 'scale': [0.5] * 3}, offset=off)
    return None

COLORS = ['white', 'light_gray', 'gray', 'black', 'brown', 'red', 'orange', 'yellow', 'lime', 'green', 'cyan',
          'light_blue', 'blue', 'purple', 'magenta', 'pink']
ONGLETS = ['construction', 'colores', 'naturels', 'fonctionnels', 'redstone', 'outils', 'combat', 'nourriture', 'ingredients', 'oeufs']

def has(item, *parts):
    return any(p in item for p in parts)

def onglet(item):
    """Onglet du mode créatif (approximation à partir de l'identifiant)."""
    is_block = f'block.minecraft.{item}' in lang
    if item.endswith('_spawn_egg'):
        return 'oeufs'
    if item in {'apple', 'golden_apple', 'enchanted_golden_apple', 'melon_slice', 'sweet_berries', 'glow_berries', 'chorus_fruit',
                'carrot', 'golden_carrot', 'potato', 'baked_potato', 'poisonous_potato', 'beetroot', 'dried_kelp', 'beef', 'cooked_beef',
                'porkchop', 'cooked_porkchop', 'mutton', 'cooked_mutton', 'chicken', 'cooked_chicken', 'rabbit', 'cooked_rabbit', 'cod',
                'cooked_cod', 'salmon', 'cooked_salmon', 'tropical_fish', 'pufferfish', 'bread', 'cookie', 'cake', 'pumpkin_pie',
                'rotten_flesh', 'spider_eye', 'mushroom_stew', 'beetroot_soup', 'rabbit_stew', 'suspicious_stew', 'milk_bucket',
                'honey_bottle', 'potion', 'splash_potion', 'lingering_potion', 'ominous_bottle'}:
        return 'nourriture'
    if has(item, '_sword', '_helmet', '_chestplate', '_leggings', '_boots', '_horse_armor', '_spear') or item in {
            'bow', 'crossbow', 'arrow', 'spectral_arrow', 'tipped_arrow', 'trident', 'mace', 'shield', 'totem_of_undying', 'snowball',
            'egg', 'blue_egg', 'brown_egg', 'wind_charge', 'end_crystal', 'wolf_armor', 'elytra'}:
        return 'combat'
    if has(item, '_pickaxe', '_shovel', '_hoe', '_boat', '_raft', 'minecart', 'music_disc_', '_bucket', 'bundle', '_harness') or item.endswith('_axe') or item in {
            'shears', 'flint_and_steel', 'fishing_rod', 'carrot_on_a_stick', 'warped_fungus_on_a_stick', 'bucket', 'compass',
            'recovery_compass', 'clock', 'spyglass', 'brush', 'lead', 'name_tag', 'map', 'filled_map', 'writable_book', 'written_book',
            'saddle', 'goat_horn', 'ender_pearl', 'ender_eye', 'firework_rocket', 'experience_bottle', 'debug_stick', 'knowledge_book'}:
        return 'outils'
    if item.endswith('_banner_pattern'):
        return 'ingredients'
    if (has(item, '_button', '_pressure_plate', 'rail', 'piston', 'redstone', 'copper_bulb', 'sculk_sensor') and not has(item, '_ore')) or item in {
            'repeater', 'comparator', 'lever', 'observer', 'dispenser', 'dropper', 'hopper', 'target', 'daylight_detector',
            'tripwire_hook', 'trapped_chest', 'tnt', 'note_block', 'crafter', 'lightning_rod', 'slime_block', 'honey_block'}:
        return 'redstone'
    color = next((c for c in COLORS if item.startswith(c + '_')), None)
    if (color and is_block and not has(item, 'orchid', '_ice', 'tulip')) or item in {'terracotta', 'glass', 'glass_pane', 'tinted_glass', 'shulker_box', 'candle'}:
        return 'colores'
    if has(item, 'shulker_box', '_bed', '_sign', '_hanging_sign', 'banner', 'torch', 'lantern', 'campfire', 'anvil', '_head', '_skull',
           'chest', 'bookshelf', 'shelf', 'copper_golem_statue') or item in {
            'crafting_table', 'furnace', 'blast_furnace', 'smoker', 'barrel', 'grindstone', 'stonecutter', 'loom', 'cartography_table',
            'fletching_table', 'smithing_table', 'enchanting_table', 'brewing_stand', 'cauldron', 'composter', 'beacon', 'conduit',
            'lodestone', 'respawn_anchor', 'bell', 'jukebox', 'lectern', 'flower_pot', 'decorated_pot', 'scaffolding', 'ladder',
            'item_frame', 'glow_item_frame', 'painting', 'armor_stand', 'end_portal_frame', 'spawner', 'trial_spawner', 'vault',
            'chain', 'iron_chain', 'end_rod', 'ender_chest', 'suspicious_sand', 'suspicious_gravel', 'dragon_egg', 'heavy_core',
            'infested_stone', 'sponge', 'wet_sponge', 'creaking_heart', 'command_block', 'chain_command_block',
            'repeating_command_block', 'structure_block', 'jigsaw', 'structure_void', 'barrier', 'light', 'test_block',
            'test_instance_block'}:
        return 'fonctionnels'
    if is_block:
        natural = ('grass', 'dirt', 'podzol', 'mycelium', 'mud', 'sand', 'gravel', '_ore', 'raw_', 'sapling', 'leaves', 'flower', 'tulip',
                   'orchid', 'allium', 'bluet', 'daisy', 'poppy', 'dandelion', 'cornflower', 'lily', 'rose', 'peony', 'lilac', 'mushroom',
                   'fungus', 'roots', 'vine', 'kelp', 'seagrass', 'coral', 'ice', 'snow', 'clay', 'netherrack', 'soul_s', 'nylium', 'wart',
                   'cactus', 'sugar_cane', 'bamboo', 'moss', 'azalea', 'dripleaf', 'sculk', 'amethyst', 'dripstone', 'bee_nest',
                   'fern', 'bush', 'pumpkin', 'melon', 'hay_block', 'sea_pickle', 'frogspawn', 'turtle_egg', 'sniffer_egg', 'spore',
                   'lichen', 'hanging_roots', 'petals', 'pitcher', 'torchflower', 'eyeblossom', 'shroomlight', 'magma', 'obsidian',
                   'bedrock', 'mangrove_propagule', 'cocoa', 'chorus', 'firefly', 'cactus_flower', 'leaf_litter', 'grass_block',
                   'end_stone', 'basalt', 'blackstone', 'calcite', 'tuff', 'deepslate', 'bone_block', 'honeycomb_block', 'resin_clump')
        building = ('_planks', '_stairs', '_slab', '_wall', '_fence', '_door', '_trapdoor', 'bricks', 'polished', 'chiseled', 'smooth',
                    'cut_', 'pillar', '_tiles', 'copper', 'quartz', 'prismarine', 'purpur', '_block', 'glass')
        if (item.endswith(('_log', '_wood', '_stem', '_hyphae')) or has(item, *building, 'bamboo_mosaic')) and not has(item, '_ore', 'sapling'):
            return 'construction'
        if has(item, *natural) or item in {'stone', 'granite', 'diorite', 'andesite', 'cobblestone'}:
            return 'naturels' if item not in {'stone', 'cobblestone', 'granite', 'diorite', 'andesite', 'deepslate', 'tuff', 'calcite',
                                              'blackstone', 'basalt', 'end_stone'} or item in {'calcite'} else 'construction'
        return 'construction'
    return 'ingredients'

def french_name(item):
    return lang.get(f'item.minecraft.{item}') or lang.get(f'block.minecraft.{item}') or item.replace('_', ' ')

def main():
    os.makedirs(OUT, exist_ok=True)
    icons, entries, missing = [], [], []
    for item in sorted(items):
        if item == 'air':
            continue
        try:
            im = icon_for(item, items[item]['model'])
        except Exception as e:
            im = None
            print('erreur', item, e)
        if im is None:
            missing.append(item)
            continue
        entries.append({'id': item, 'nom': french_name(item), 'i': len(icons), 'o': onglet(item)})
        icons.append(im)
    # Deux atlas : icônes plates (16 px) et icônes 3D (BLOCK px)
    groups = ([], [])
    for e, im in zip(entries, icons):
        g = 0 if im.size == (ICON, ICON) else 1
        e['a'], e['i'] = g, len(groups[g])
        groups[g].append(im)
    for g, (name, size) in enumerate((('items', ICON), ('blocs', BLOCK))):
        rows = math.ceil(len(groups[g]) / COLS)
        atlas = Image.new('RGBA', (COLS * size, rows * size))
        for i, im in enumerate(groups[g]):
            atlas.alpha_composite(im.resize((size, size), Image.NEAREST), ((i % COLS) * size, (i // COLS) * size))
        atlas.save(os.path.join(OUT, f'{name}.png'), optimize=True)
    # Ordre : par onglet, puis par identifiant (regroupe les matériaux : acacia_*, birch_*…)
    entries.sort(key=lambda e: (ONGLETS.index(e['o']), e['id']))
    json.dump({'tailles': [ICON, BLOCK], 'colonnes': COLS, 'onglets': ONGLETS, 'items': entries}, open(os.path.join(OUT, 'items.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    print(len(entries), 'icônes ;', len(missing), 'sans icône :', ' '.join(missing))

main()

"""Native Maya ASCII (`.ma`) geometry interchange, without a Maya runtime.

Reads and writes the subset of Maya ASCII that carries modeled geometry:
transform hierarchy (translate / rotate / scale / rotate order / visibility),
polygon mesh shapes (`.vt`, `.pt` tweaks, `.ed` with hard/soft flags,
`.fc` polyFaces with `f` and `mu`) and the default UV set. Maya is Y-up and
measures in the file's `currentUnit`; Blender is Z-up in metres.

Meshes whose geometry only exists through construction history (an
`inMesh` connection and no stored vertices) cannot be evaluated without Maya.
They are reported as skipped with the reason, never silently imported empty.
Shaders, skinning, animation and other nodes are outside this subset; the
`mayapy` bridge remains the full-fidelity route when a Maya runtime works.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

UNIT_TO_METRES = {"mm": 0.001, "millimeter": 0.001, "cm": 0.01, "centimeter": 0.01,
                  "m": 1.0, "meter": 1.0, "km": 1000.0, "kilometer": 1000.0,
                  "in": 0.0254, "inch": 0.0254, "ft": 0.3048, "foot": 0.3048,
                  "yd": 0.9144, "yard": 0.9144, "mi": 1609.344, "mile": 1609.344}
ROTATE_ORDERS = ("XYZ", "YZX", "ZXY", "XZY", "YXZ", "ZYX")
_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|[^\s"]+')


# --------------------------------------------------------------------------------------
# Axis conversion: Maya (x, y, z) Y-up -> Blender (x, -z, y) Z-up.
# --------------------------------------------------------------------------------------
def _basis():
    from mathutils import Matrix
    return Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def _maya_to_blender_point(p, scale):
    return (p[0] * scale, -p[2] * scale, p[1] * scale)


def _blender_to_maya_point(p, scale):
    return (p[0] / scale, p[2] / scale, -p[1] / scale)


# --------------------------------------------------------------------------------------
# Reader
# --------------------------------------------------------------------------------------
def _statements(text: str):
    """Yield token lists for each `;`-terminated statement, quote-aware."""
    tokens: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("//") and not tokens:
            continue
        for token in _TOKEN.findall(line):
            if token.startswith('"'):
                tokens.append(token)
                continue
            while token:
                head, sep, token = token.partition(";")
                if head:
                    tokens.append(head)
                if sep:
                    if tokens:
                        yield tokens
                    tokens = []
                else:
                    break
    if tokens:
        yield tokens


def _unquote(token: str) -> str:
    return token[1:-1].replace('\\"', '"') if token.startswith('"') else token


def _flag(tokens: Sequence[str], *names: str) -> Optional[str]:
    for i, token in enumerate(tokens[:-1]):
        if token in names:
            return _unquote(tokens[i + 1])
    return None


def _range(attr: str) -> Tuple[str, Optional[int], Optional[int]]:
    """'.vt[3:7]' -> ('vt', 3, 7); '.vt[5]' -> ('vt', 5, 5); '.t' -> ('t', None, None)."""
    m = re.match(r"^\.?([A-Za-z_][\w\.\[\]]*?)(?:\[(\d+)(?::(\d+))?\])?$", attr)
    if not m:
        return attr.lstrip("."), None, None
    start = int(m.group(2)) if m.group(2) is not None else None
    end = int(m.group(3)) if m.group(3) is not None else start
    return m.group(1), start, end


def _numbers(tokens: Sequence[str]) -> List[float]:
    out = []
    for token in tokens:
        try:
            out.append(float(token))
        except ValueError:
            if token in ("yes", "true", "on"):
                out.append(1.0)
            elif token in ("no", "false", "off"):
                out.append(0.0)
    return out


class _Node:
    def __init__(self, kind: str, name: str, parent: Optional[str]):
        self.kind, self.name, self.parent = kind, name, parent
        self.attrs: Dict[str, Any] = {}
        self.vt: Dict[int, Tuple[float, float, float]] = {}
        self.pt: Dict[int, Tuple[float, float, float]] = {}
        self.ed: Dict[int, Tuple[int, int, int]] = {}
        self.faces: List[Tuple[List[int], Optional[List[int]]]] = []
        self.uv: Dict[int, Tuple[float, float]] = {}
        self.uv_name = "map1"
        self.history = False
        self.holes = 0


def parse_maya_ascii(text: str) -> Dict[str, Any]:
    """Parse geometry-carrying nodes from Maya ASCII text."""
    nodes: Dict[str, _Node] = {}
    order: List[str] = []
    unit = "centimeter"
    up_axis = "y"
    current: Optional[_Node] = None
    by_short: Dict[str, List[str]] = {}

    def key_for(name: str, parent: Optional[str]) -> str:
        short = name.split("|")[-1]
        if name.startswith("|"):
            return name
        if parent:
            pkey = resolve(parent)
            return (pkey or ("|" + parent.split("|")[-1])) + "|" + short
        return "|" + short

    def resolve(name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        if name in nodes:
            return name
        if name.startswith("|") and name in nodes:
            return name
        candidates = by_short.get(name.split("|")[-1], [])
        if name.count("|"):
            tail = "|" + name.lstrip("|")
            candidates = [c for c in candidates if c.endswith(tail)] or candidates
        return candidates[-1] if candidates else None

    for tokens in _statements(text):
        command = tokens[0]
        if command == "currentUnit":
            unit = _flag(tokens, "-l", "-linear") or unit
        elif command == "upAxis" or (command == "fileInfo" and len(tokens) > 2 and _unquote(tokens[1]) == "upAxis"):
            up_axis = (_flag(tokens, "-ax", "-axis") or _unquote(tokens[-1])).lower()
        elif command == "createNode":
            kind = tokens[1]
            name = _flag(tokens, "-n", "-name") or kind
            parent = _flag(tokens, "-p", "-parent")
            if kind in ("transform", "joint", "mesh"):
                key = key_for(name, parent)
                current = _Node(kind, key, resolve(parent) if parent else None)
                nodes[key] = current
                order.append(key)
                by_short.setdefault(key.split("|")[-1], []).append(key)
            else:
                current = None
        elif command == "select":
            target = _unquote(tokens[-1]) if len(tokens) > 1 else ""
            current = nodes.get(resolve(target) or "", None)
        elif command == "setAttr" and current is not None:
            _apply_set_attr(current, tokens)
        elif command == "connectAttr" and len(tokens) >= 3:
            dest = _unquote(tokens[2])
            node_name, _, attr = dest.partition(".")
            target = nodes.get(resolve(node_name) or "", None)
            if target is not None and target.kind == "mesh" and attr in ("i", "inMesh"):
                target.history = True
    return {"nodes": nodes, "order": order, "unit": unit, "up_axis": up_axis}


def _apply_set_attr(node: _Node, tokens: Sequence[str]) -> None:
    attr_index = next((i for i, t in enumerate(tokens[1:], 1) if t.startswith('".') or t.startswith('"')), None)
    if attr_index is None:
        return
    attr_token = _unquote(tokens[attr_index])
    rest = list(tokens[attr_index + 1:])
    if rest[:1] == ["-type"]:
        value_type = _unquote(rest[1]) if len(rest) > 1 else ""
        rest = rest[2:]
    else:
        value_type = ""
    name, start, end = _range(attr_token)

    if node.kind in ("transform", "joint"):
        if name in ("t", "r", "s", "jo", "ra"):
            values = _numbers(rest)
            if len(values) >= 3:
                node.attrs[name] = tuple(values[:3])
        elif name in ("ro", "v"):
            values = _numbers(rest)
            if values:
                node.attrs[name] = values[0]
        return

    if name == "vt" and start is not None:
        values = _numbers(rest)
        for i in range((len(values)) // 3):
            if start + i > end:
                break
            node.vt[start + i] = tuple(values[3 * i:3 * i + 3])
    elif name == "pt" and start is not None:
        values = _numbers(rest)
        for i in range(len(values) // 3):
            if start + i > end:
                break
            node.pt[start + i] = tuple(values[3 * i:3 * i + 3])
    elif name == "ed" and start is not None:
        values = [int(v) for v in _numbers(rest)]
        for i in range(len(values) // 3):
            if start + i > end:
                break
            node.ed[start + i] = tuple(values[3 * i:3 * i + 3])
    elif name == "fc" and value_type == "polyFaces":
        _parse_poly_faces(node, rest)
    elif name.startswith("uvst[0].uvsp") or (name == "uvst[0].uvsp" and start is not None):
        values = _numbers(rest)
        base = start or 0
        for i in range(len(values) // 2):
            node.uv[base + i] = (values[2 * i], values[2 * i + 1])
    elif name == "uvst[0].uvsn":
        node.uv_name = _unquote(rest[0]) if rest else node.uv_name
    elif name == "v":
        values = _numbers(rest)
        if values:
            node.attrs["v"] = values[0]


def _parse_poly_faces(node: _Node, tokens: Sequence[str]) -> None:
    i = 0
    while i < len(tokens):
        tag = tokens[i]
        if tag == "f":
            count = int(tokens[i + 1])
            edges = [int(t) for t in tokens[i + 2:i + 2 + count]]
            node.faces.append((edges, None))
            i += 2 + count
        elif tag == "mu":
            uv_set, count = int(tokens[i + 1]), int(tokens[i + 2])
            ids = [int(t) for t in tokens[i + 3:i + 3 + count]]
            if uv_set == 0 and node.faces:
                edges, _ = node.faces[-1]
                node.faces[-1] = (edges, ids)
            i += 3 + count
        elif tag == "h":
            count = int(tokens[i + 1])
            node.holes += 1
            i += 2 + count
        elif tag in ("mf", "mh"):
            count = int(tokens[i + 1])
            i += 2 + count
        elif tag == "fc":
            count = int(tokens[i + 1])
            i += 2 + count
        elif tag == "mc":
            count = int(tokens[i + 2])
            i += 3 + count
        else:
            i += 1


def import_maya_ascii(path: str, collection: Any = None) -> Dict[str, Any]:
    """Create Blender objects for the transforms and meshes in a `.ma` file."""
    import bpy
    from mathutils import Euler, Matrix, Vector

    source = Path(path)
    if source.suffix.lower() != ".ma":
        return {"ok": False, "error": "Native import reads Maya ASCII (.ma) only; .mb needs a Maya runtime."}
    try:
        text = source.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"ok": False, "error": f"Cannot read {source}: {exc}"}
    if not text.lstrip().startswith("//Maya"):
        return {"ok": False, "error": f"{source.name} is not a Maya ASCII file."}
    parsed = parse_maya_ascii(text)
    nodes, order = parsed["nodes"], parsed["order"]
    scale = UNIT_TO_METRES.get(parsed["unit"], 0.01)
    z_up = parsed["up_axis"] == "z"
    collection = collection or bpy.context.collection
    basis = Matrix.Identity(4) if z_up else _basis()

    created: Dict[str, Any] = {}
    skipped: List[Dict[str, str]] = []
    shapes_for: Dict[str, List[_Node]] = {}
    for key in order:
        node = nodes[key]
        if node.kind == "mesh":
            shapes_for.setdefault(node.parent or "", []).append(node)

    def point(p):
        return (p[0] * scale, p[1] * scale, p[2] * scale) if z_up else _maya_to_blender_point(p, scale)

    def build_mesh(shape: _Node):
        if not shape.vt:
            reason = ("geometry comes from construction history; Delete History in Maya, "
                      "or import through a working Maya runtime") if shape.history else "no stored vertices"
            skipped.append({"node": shape.name.split("|")[-1], "reason": reason})
            return None
        count = max(shape.vt) + 1
        coords = []
        for i in range(count):
            base = shape.vt.get(i, (0.0, 0.0, 0.0))
            tweak = shape.pt.get(i, (0.0, 0.0, 0.0))
            coords.append(point((base[0] + tweak[0], base[1] + tweak[1], base[2] + tweak[2])))
        faces, face_uvs = [], []
        for edges, uv_ids in shape.faces:
            loop = []
            for e in edges:
                edge = shape.ed.get(e if e >= 0 else -e - 1)
                if edge is None:
                    loop = []
                    break
                loop.append(edge[0] if e >= 0 else edge[1])
            if len(loop) >= 3:
                faces.append(loop)
                face_uvs.append(uv_ids)
        loose = [] if faces else [(e[0], e[1]) for e in shape.ed.values()]
        mesh = bpy.data.meshes.new(shape.name.split("|")[-1])
        mesh.from_pydata(coords, loose, faces)
        if shape.uv and any(ids for ids in face_uvs):
            layer = mesh.uv_layers.new(name=shape.uv_name or "map1")
            for poly, ids in zip(mesh.polygons, face_uvs):
                for corner in range(poly.loop_total):
                    if ids and corner < len(ids) and ids[corner] in shape.uv:
                        layer.data[poly.loop_start + corner].uv = shape.uv[ids[corner]]
        # Maya edge flag 0 is hard; keep those edges sharp in Blender.
        hard = {tuple(sorted((a, b))) for a, b, smooth in shape.ed.values() if not smooth}
        if hard and faces:
            sharp = mesh.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
            for edge in mesh.edges:
                sharp.data[edge.index].value = tuple(sorted(edge.vertices)) in hard
            for poly in mesh.polygons:
                poly.use_smooth = True
        mesh.validate(clean_customdata=False)
        mesh.update()
        return mesh

    def local_matrix(node: _Node):
        t = node.attrs.get("t", (0.0, 0.0, 0.0))
        r = node.attrs.get("r", (0.0, 0.0, 0.0))
        s = node.attrs.get("s", (1.0, 1.0, 1.0))
        order_name = ROTATE_ORDERS[int(node.attrs.get("ro", 0)) % 6]
        rot = Euler(tuple(math.radians(a) for a in r), order_name).to_matrix().to_4x4()
        if node.kind == "joint":
            jo = node.attrs.get("jo", (0.0, 0.0, 0.0))
            rot = Euler(tuple(math.radians(a) for a in jo), "XYZ").to_matrix().to_4x4() @ rot
        m = Matrix.Translation(Vector(t) * scale) @ rot @ Matrix.Diagonal(Vector(s + (1.0,)))
        return basis @ m @ basis.inverted()

    for key in order:
        node = nodes[key]
        if node.kind not in ("transform", "joint"):
            continue
        shapes = shapes_for.get(key, [])
        mesh = None
        for shape in shapes:
            mesh = build_mesh(shape)
            if mesh is not None:
                break
        obj = bpy.data.objects.new(key.split("|")[-1], mesh)
        if mesh is None:
            obj.empty_display_type = "PLAIN_AXES"
            obj.empty_display_size = 0.1
        collection.objects.link(obj)
        parent = created.get(node.parent or "")
        if parent is not None:
            obj.parent = parent
        obj.matrix_basis = local_matrix(node)
        if node.attrs.get("v", 1.0) == 0.0:
            obj.hide_set(True)
            obj.hide_render = True
        created[key] = obj
    # Shapes without a transform parent in the file.
    for shape_parent, shapes in shapes_for.items():
        if shape_parent in created:
            continue
        for shape in shapes:
            mesh = build_mesh(shape)
            if mesh is not None:
                obj = bpy.data.objects.new(shape.name.split("|")[-1], mesh)
                collection.objects.link(obj)
                created[shape.name] = obj
    meshes = sum(1 for o in created.values() if o.type == "MESH")
    return {"ok": True, "objects": [o.name for o in created.values()], "mesh_count": meshes,
            "skipped": skipped, "unit": parsed["unit"], "up_axis": parsed["up_axis"],
            "route": "native_ascii"}


# --------------------------------------------------------------------------------------
# Writer
# --------------------------------------------------------------------------------------
def _q(name: str) -> str:
    return '"' + name.replace('"', '_') + '"'


def _maya_name(name: str, used: set) -> str:
    clean = re.sub(r"[^A-Za-z0-9_]", "_", name) or "node"
    if clean[0].isdigit():
        clean = "_" + clean
    candidate, n = clean, 1
    while candidate in used:
        candidate = f"{clean}{n}"
        n += 1
    used.add(candidate)
    return candidate


def _fmt(values) -> str:
    return " ".join(f"{v:.9g}" for v in values)


def export_maya_ascii(path: str, objects: Optional[Sequence[Any]] = None, unit: str = "centimeter") -> Dict[str, Any]:
    """Write transforms and evaluated meshes to a Maya ASCII file Maya can open."""
    import bpy
    from mathutils import Matrix

    scale = UNIT_TO_METRES[unit]
    objects = list(objects if objects is not None else bpy.context.scene.objects)
    chosen = set(objects)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    basis = _basis()
    used: set = set()
    names: Dict[Any, str] = {}
    lines = [
        "//Maya ASCII 2024 scene",
        f"//Name: {Path(path).name}",
        "//Codeset: UTF-8",
        'requires maya "2024";',
        f"currentUnit -l {unit} -a degree -t film;",
        'fileInfo "application" "maya";',
        'fileInfo "exportedBy" "Landfall Studio (native Maya ASCII)";',
    ]
    written_meshes = 0

    def depth(obj):
        d, p = 0, obj.parent
        while p is not None:
            d, p = d + 1, p.parent
        return d

    # Matrices Maya will actually evaluate, per written object (Blender space).
    written_world: Dict[Any, Any] = {}
    for obj in sorted(objects, key=lambda o: (depth(o), o.name)):
        if obj.type not in ("MESH", "EMPTY", "CURVE", "SURFACE", "META", "FONT"):
            continue
        name = _maya_name(obj.name, used)
        names[obj] = name
        parent = obj.parent if obj.parent in chosen and obj.parent in names else None
        header = f"createNode transform -n {_q(name)}"
        if parent is not None:
            header += f" -p {_q(names[parent])}"
            local = written_world[parent].inverted() @ obj.matrix_world
        else:
            local = obj.matrix_world.copy()
        lines.append(header + ";")
        maya = basis.inverted() @ local @ basis
        loc, rot, sca = maya.decompose()
        written = Matrix.LocRotScale(loc, rot, sca)
        # Shear (from non-uniform parent scale) has no translate/rotate/scale
        # form; bake that remainder into the shape so world positions match.
        residual = written.inverted() @ maya
        written_world[obj] = (written_world[parent] if parent is not None else Matrix.Identity(4)) @ (basis @ written @ basis.inverted())
        euler = rot.to_euler("XYZ")
        lines.append(f'	setAttr ".t" -type "double3" {_fmt(v / scale for v in loc)} ;')
        lines.append(f'	setAttr ".r" -type "double3" {_fmt(math.degrees(a) for a in euler)} ;')
        lines.append(f'	setAttr ".s" -type "double3" {_fmt(sca)} ;')
        if obj.hide_get() or obj.hide_viewport:
            lines.append('	setAttr ".v" no;')
        if obj.type == "EMPTY":
            continue
        evaluated = obj.evaluated_get(depsgraph)
        try:
            mesh = evaluated.to_mesh()
        except RuntimeError:
            mesh = None
        if mesh is None or not mesh.vertices:
            if mesh is not None:
                evaluated.to_mesh_clear()
            continue
        try:
            lines.extend(_mesh_lines(mesh, name + "Shape", name, scale, residual))
            written_meshes += 1
        finally:
            evaluated.to_mesh_clear()
    lines.append("// End of " + Path(path).name)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True, "path": str(path), "transforms": len(names), "meshes": written_meshes,
            "unit": unit, "route": "native_ascii"}


def _mesh_lines(mesh, shape: str, parent: str, scale: float, residual=None) -> List[str]:
    verts = [_blender_to_maya_point(v.co, scale) for v in mesh.vertices]
    if residual is not None:
        from mathutils import Vector
        verts = [tuple(residual @ Vector(p)) for p in verts]
    edges = [tuple(e.vertices) for e in mesh.edges]
    sharp_attr = mesh.attributes.get("sharp_edge")
    sharp_face = mesh.attributes.get("sharp_face")
    hard = [bool(sharp_attr.data[i].value) if sharp_attr else False for i in range(len(edges))]
    if sharp_face is not None:
        # Flat-shaded faces read as hard edges in Maya.
        flat_edges = {i for poly in mesh.polygons if sharp_face.data[poly.index].value
                      for i in (mesh.loops[l].edge_index for l in range(poly.loop_start, poly.loop_start + poly.loop_total))}
        for i in flat_edges:
            hard[i] = True
    uv_layer = mesh.uv_layers.active
    uv_ids: List[List[int]] = []
    uv_coords: List[Tuple[float, float]] = []
    if uv_layer is not None:
        seen: Dict[Tuple[int, float, float], int] = {}
        for poly in mesh.polygons:
            ids = []
            for li in range(poly.loop_start, poly.loop_start + poly.loop_total):
                u, v = uv_layer.data[li].uv
                key = (mesh.loops[li].vertex_index, round(u, 6), round(v, 6))
                if key not in seen:
                    seen[key] = len(uv_coords)
                    uv_coords.append((u, v))
                ids.append(seen[key])
            uv_ids.append(ids)
    out = [f"createNode mesh -n {_q(shape)} -p {_q(parent)};",
           '\tsetAttr -k off ".v";',
           '\tsetAttr ".vir" yes;',
           '\tsetAttr ".vif" yes;']
    if uv_coords:
        out.append(f'\tsetAttr ".uvst[0].uvsn" -type "string" {_q(uv_layer.name or "map1")};')
        out.append(f'\tsetAttr -s {len(uv_coords)} ".uvst[0].uvsp[0:{len(uv_coords) - 1}]" -type "float2" '
                   + _fmt(c for uv in uv_coords for c in uv) + ";")
        out.append('\tsetAttr ".cuvs" -type "string" ' + _q(uv_layer.name or "map1") + ";")
    out.append(f'\tsetAttr -s {len(verts)} ".vt[0:{len(verts) - 1}]" ' + _fmt(c for p in verts for c in p) + ";")
    if edges:
        out.append(f'\tsetAttr -s {len(edges)} ".ed[0:{len(edges) - 1}]" '
                   + " ".join(f"{a} {b} {0 if h else 1}" for (a, b), h in zip(edges, hard)) + ";")
    if mesh.polygons:
        corner_total = sum(p.loop_total for p in mesh.polygons)
        face_lines = []
        for fi, poly in enumerate(mesh.polygons):
            refs = []
            for li in range(poly.loop_start, poly.loop_start + poly.loop_total):
                loop = mesh.loops[li]
                a, _b = edges[loop.edge_index]
                refs.append(loop.edge_index if a == loop.vertex_index else -loop.edge_index - 1)
            face_lines.append(f"\t\tf {len(refs)} " + " ".join(map(str, refs)))
            if uv_ids:
                face_lines.append(f"\t\tmu 0 {len(uv_ids[fi])} " + " ".join(map(str, uv_ids[fi])))
        out.append(f'\tsetAttr -s {len(mesh.polygons)} -ch {corner_total} ".fc[0:{len(mesh.polygons) - 1}]" -type "polyFaces" ')
        out.append("\n".join(face_lines) + ";")
    return out

"""Source HUD adapter graph, mirroring public RecoveredHudBuilder authoring."""

import copy
from types import SimpleNamespace as N
from pathlib import Path
from contextlib import closing
import importlib.util
import hashlib
import io
import json
import re
import time


def pointer(key=0):
    return dict(m_FileID=0, m_PathID=key)


class Graph:
    def __init__(self, U, store, scripts):
        self.U, self.store, self.scripts = U, store, scripts
        self.rows, self.by_key, self.instances, self.extra = [], {}, {}, 0

    def clone(self, asset, pid, label, parent=None):
        self.U.require(label not in self.instances, "duplicate clone instance")
        hierarchy = self.U.hierarchy(asset, pid)
        ids = {i for g in hierarchy for i in [g["id"], *g["components"]]}
        self.instances[label] = label, asset.name, pid
        for game in hierarchy:
            for identity in [game["id"], *game["components"]]:
                obj = asset.objects[identity]
                fields = copy.deepcopy(obj.read_typetree())

                def relocate(ptr):
                    if not ptr["m_PathID"]:
                        return pointer()
                    if not ptr["m_FileID"] and ptr["m_PathID"] in ids:
                        return pointer(("object", label, ptr["m_PathID"]))
                    return pointer(("asset", *self.U.reference_key(asset, ptr)))

                self.U.map_pointers(fields, relocate)
                key = ("object", label, identity)
                row = dict(
                    key=key,
                    asset=asset,
                    source_id=identity,
                    path=label + game["path"][1:],
                    identity=self.U.identity(obj, self.scripts),
                    fields=fields,
                    typ=obj.typ,
                    node=obj.node,
                )
                self.rows.append(row)
                self.by_key[key] = row
        root = self.by_key["object", label, pid]
        root["fields"]["m_Name"] += "(Clone)"
        if parent is not None:
            self.attach(root, parent)
        return root

    def resolve(self, ptr, owner=None):
        key = ptr["m_PathID"]
        self.U.require(key, "null required HUD source relationship")
        if isinstance(key, tuple):
            if key[0] == "object":
                return self.by_key[key]
            _, member, pid = key
        else:
            member, pid = self.U.reference_key(owner["asset"], ptr)
        if member not in self.store.assets:
            native = self.store.pc / "Risk of Rain 2_Data" / ("Resources/" + member if member == "unity_builtin_extra" else member)
            if native.is_file():
                self.store.asset_file(native, member)
            else:
                if not hasattr(self, "member_sources"):
                    self.member_sources = {}
                    for source in (self.store.pc / "Risk of Rain 2_Data/StreamingAssets/aa/StandaloneWindows64").glob("*.bundle"):
                        bundle = self.U.W.B.Bundle(source)
                        for key, (_, _, flags) in bundle.members.items():
                            if flags & 4:
                                self.member_sources.setdefault(key, []).append(source)
                files = self.member_sources.get(member, [])
                self.U.require(len(files) == 1, "missing/ambiguous original HUD member " + member)
                self.store.asset_file(files[0], member, member=member)
        asset = self.store.assets[member]
        obj = asset.objects[pid]
        return dict(
            key=("asset", member, pid),
            asset=asset,
            source_id=pid,
            fields=copy.deepcopy(obj.read_typetree()),
            identity=self.U.identity(obj, self.scripts),
            typ=obj.typ,
            node=obj.node,
            path=member,
        )

    def field(self, row, name):
        self.U.require(name in row["fields"], "missing HUD field " + name + " in " + row["identity"] + ": " + str(list(row["fields"])))
        return self.resolve(row["fields"][name], row)

    def copied(self, value, owner):
        value = copy.deepcopy(value)

        def canonical(ptr):
            if not ptr["m_PathID"]:
                return pointer()
            if isinstance(ptr["m_PathID"], tuple):
                return ptr
            return pointer(("asset", *self.U.reference_key(owner["asset"], ptr)))

        self.U.map_pointers(value, canonical)
        return value

    def game(self, row):
        return row if row["typ"]["class_id"] == 1 else self.field(row, "m_GameObject")

    def ref(self, row):
        return pointer(row["key"])

    def components(self, game):
        game = self.game(game)
        return [self.resolve(p["component"], game) for p in game["fields"]["m_Component"]]

    def component(self, game, kind, optional=False):
        game = self.game(game)
        matches = [
            r
            for r in self.components(game)
            if r["identity"].rsplit(".", 1)[-1] == kind or r["identity"] == kind or kind == "TMP_Text" and "m_text" in r["fields"]
        ]
        self.U.require(optional or len(matches) == 1, "HUD component absent/ambiguous: " + kind + " at " + game["fields"]["m_Name"])
        return matches[0] if matches else None

    def transform(self, row):
        game = self.game(row)
        matches = [r for r in self.components(game) if r["typ"]["class_id"] in (4, 224)]
        self.U.require(len(matches) == 1, "HUD Transform ambiguous")
        return matches[0]

    def descendants(self, row):
        root = self.game(row)
        out = []
        seen = set()

        def visit(go):
            self.U.require(go["key"] not in seen, "cyclic HUD instance hierarchy")
            seen.add(go["key"])
            out.append(go)
            for ptr in self.transform(go)["fields"]["m_Children"]:
                visit(self.field(self.resolve(ptr), "m_GameObject"))

        visit(root)
        return out

    def named(self, root, name):
        matches = [r for r in self.descendants(root) if r["fields"]["m_Name"] == name]
        self.U.require(matches, "HUD named source absent: " + name)
        return matches[0]

    def find(self, root, kind, optional=False):
        for go in self.descendants(root):
            row = self.component(go, kind, True)
            if row:
                return row
        self.U.require(optional, "HUD descendant component absent: " + kind)

    def text(self, root, name):
        return self.component(self.named(root, name), "TMP_Text")

    def active(self, row, enabled):
        self.game(row)["fields"]["m_IsActive"] = bool(enabled)

    def hide(self, root, names):
        for go in self.descendants(root):
            if go["fields"]["m_Name"] in names:
                self.active(go, False)

    def attach(self, root, parent):
        transform = self.transform(root)
        parent = self.transform(parent)
        transform["fields"]["m_Father"] = self.ref(parent)
        parent["fields"]["m_Children"].append(self.ref(transform))

    def clone_ref(self, ptr, owner, label, parent):
        original = self.resolve(ptr, owner)
        return self.clone(original["asset"], original["source_id"], label, parent)

    def add(self, game, identity, fields=None):
        self.extra += 1
        key = ("object", "authored", self.extra)
        row = dict(
            key=key,
            asset=game["asset"],
            source_id=None,
            path=game["path"],
            identity=identity,
            fields=dict(fields or {}, m_GameObject=self.ref(game), m_Enabled=1, m_Script=pointer(), m_Name=""),
            typ=dict(class_id=114),
        )
        self.rows.append(row)
        self.by_key[key] = row
        game["fields"]["m_Component"].append(dict(component=self.ref(row)))
        return row

    def normalize(self, root, labels):
        default_font = None
        default_pointer = None
        for go in self.descendants(root):
            for row in self.components(go):
                f = row["fields"]
                if "m_text" not in f or not f["m_fontAsset"]["m_PathID"]:
                    continue
                font = self.resolve(f["m_fontAsset"], row)
                if font["fields"]["m_Name"].startswith("tmpRiskofRainFont"):
                    default_font = font
                    default_pointer = copy.deepcopy(f["m_fontAsset"])
                    break
            if default_font:
                break
        self.U.require(default_font is not None, "original default HUD font absent")
        for go in self.descendants(root):
            language = self.component(go, "LanguageTextMeshController", True)
            if language:
                texts = [r for child in self.descendants(go) for r in self.components(child) if "m_text" in r["fields"]]
                if texts:
                    token = language["fields"]["_token"]
                    texts[0]["fields"]["m_text"] = labels.get(token, token or "")
            for row in self.components(go):
                f = row["fields"]
                kind = row["typ"]["class_id"]
                if "m_text" in f:
                    if not f["m_fontAsset"]["m_PathID"]:
                        f["m_fontAsset"] = copy.deepcopy(default_pointer)
                        f["m_sharedMaterial"] = self.copied(default_font["fields"]["material"], default_font)
                    elif not f["m_sharedMaterial"]["m_PathID"]:
                        font = self.resolve(f["m_fontAsset"], row)
                        f["m_sharedMaterial"] = self.copied(font["fields"]["material"], font)
                    if "<sprite" in f["m_text"]:
                        self.active(go, False)
                    if "useLanguageDefaultFont" in f:
                        f["useLanguageDefaultFont"] = False
                    f["m_RaycastTarget"] = False
                if "m_Material" in f and "m_text" not in f and row["identity"].startswith("UnityEngine.UI:") and f["m_Material"]["m_PathID"]:
                    material = self.resolve(f["m_Material"], row)
                    shader = self.field(material, "m_Shader")
                    if shader["fields"]["m_ParsedForm"]["m_Name"] != "Hopoo Games/UI/Animate Alpha":
                        f["m_Material"] = pointer()
                if kind == 225:
                    f["m_Alpha"] = 1.0
                if kind == 223 and go is root:
                    f.update(m_RenderMode=0, m_Camera=pointer(), m_SortingOrder=50)
        keep = {"TimerText", "BuffIcon", "GenericNotification", "AnimateUIAlpha", "RecoveredPickupPresentation", "RecoveredHudPresentation"}
        removed = set()
        for row in self.rows:
            if (
                row["typ"]["class_id"] in (54, 95)
                or row["typ"]["class_id"] == 114
                and not (
                    "m_text" in row["fields"] or row["identity"].startswith("UnityEngine.UI:UnityEngine.UI.") or row["identity"].rsplit(".", 1)[-1] in keep
                )
            ):
                removed.add(row["key"])
        for row in self.rows:
            if row["typ"]["class_id"] == 1:
                row["fields"]["m_Component"] = [p for p in row["fields"]["m_Component"] if p["component"]["m_PathID"] not in removed]
            self.U.map_pointers(row["fields"], lambda p: pointer() if isinstance(p["m_PathID"], tuple) and p["m_PathID"] in removed else p)
        self.rows = [r for r in self.rows if r["key"] not in removed]
        self.removed = removed

    def finalize(self):
        for row in self.rows:
            row["fields"] = copy.deepcopy(row["fields"])
        rows = sorted(self.rows, key=lambda r: (r["typ"]["class_id"] == 114, r["typ"]["class_id"], r["key"]))
        allocation = {r["key"]: i + 1 for i, r in enumerate(rows)}
        for row in rows:
            original = row["asset"]
            asset = N(**vars(original))
            asset.externals = copy.deepcopy(original.externals)
            row["asset"] = asset

            def relocate(ptr):
                token = ptr["m_PathID"]
                if not token:
                    return pointer()
                self.U.require(isinstance(token, tuple), "noncanonical HUD source pointer")
                if token[0] == "object":
                    return pointer(allocation[token])
                _, member, pid = token
                if member == asset.name:
                    return pointer(pid)
                paths = [x["path"].rsplit("/", 1)[-1] for x in asset.externals]
                if member not in paths:
                    asset.externals.append(dict(path="archive:/" + member + "/" + member))
                    paths.append(member)
                return dict(m_FileID=paths.index(member) + 1, m_PathID=pid)

            self.U.map_pointers(row["fields"], relocate)
            row["id"] = allocation[row["key"]]
        return rows, allocation


def construct(U, store, scripts, roots, labels):
    g = Graph(U, store, scripts)

    def original(name):
        selected = roots[name]["source"]
        return store.asset(selected), selected["path_id"]

    hud = g.clone(*original("hudSource"), "hud")
    native = g.component(hud, "HUD")
    view = g.add(hud, "Assembly-CSharp:.RecoveredHudPresentation")
    v = view["fields"]

    def bind(field, row):
        v[field] = g.ref(row)

    health = g.field(native, "healthBar")
    for field in ("currentHealthText", "fullHealthText"):
        bind(field.replace("Text", ""), g.field(health, field))
    bind("level", g.field(g.field(native, "levelText"), "targetText"))
    bind("money", g.field(g.field(native, "moneyText"), "targetText"))
    bind("experienceFill", g.field(g.field(native, "expBar"), "fillRectTransform"))
    style = g.field(health, "_style")
    container = g.field(health, "barContainer")
    for field, style_name, name in [
        ("healthFill", "trailingOverHealthBarStyle", "Owned health fill"),
        ("shieldFill", "shieldBarStyle", "Owned shield fill"),
        ("barrierFill", "barrierBarStyle", "Owned barrier fill"),
    ]:
        bar = g.clone_ref(style["fields"]["barPrefab"], style, "bar-" + field, container)
        bar["fields"]["m_Name"] = name
        image = g.component(bar, "Image")
        bf = style["fields"][style_name]
        image["fields"].update(m_Sprite=g.copied(bf["sprite"], style), m_Color=copy.deepcopy(bf["baseColor"]), m_Type=bf["imageType"], m_RaycastTarget=False)
        bind(field, image)
    skills = []
    for i, ptr in enumerate(native["fields"]["skillIcons"]):
        row = g.resolve(ptr, native)
        key = g.text(g.game(row), "SkillKeyText")
        key["fields"]["m_text"] = ("X", "Y", "LB", "RB")[i]
        skills.append(
            dict(
                icon=row["fields"]["iconImage"],
                cooldown=row["fields"]["cooldownText"],
                stock=row["fields"]["stockText"],
                key=g.ref(key),
                ready=row["fields"]["isReadyPanelObject"],
            )
        )
        for field in ("cooldownRemapPanel", "flashPanelObject"):
            if row["fields"][field]["m_PathID"]:
                g.active(g.field(row, field), False)
        g.hide(g.game(row), {"FlashPanel, Expanding"})
    v["skills"] = skills
    equipments = [g.resolve(p, native) for p in native["fields"]["equipmentIcons"] if p["m_PathID"]]
    equipment = equipments[0]
    for field, source in [
        ("equipmentImage", "iconImage"),
        ("equipmentCooldown", "cooldownText"),
        ("equipmentStock", "stockText"),
        ("equipmentReady", "isReadyPanelObject"),
    ]:
        v[field] = equipment["fields"][source]
    for row in equipments:
        g.active(row, row is equipment)
    g.hide(g.game(equipment), {"FlashPanel, Expanding"})
    for field in ("stockFlashPanelObject", "reminderFlashPanelObject"):
        if equipment["fields"][field]["m_PathID"]:
            g.active(g.field(equipment, field), False)
    spectator = g.find(hud, "SpectatorLabel", True)
    if spectator:
        g.active(spectator, False)
    boss = g.find(hud, "HUDBossHealthBarController")
    for field, source in [("bossContainer", "container"), ("bossFill", "fillRectImage"), ("bossName", "bossNameLabel"), ("bossHealth", "healthLabel")]:
        v[field] = boss["fields"][source]
    g.field(boss, "bossSubtitleLabel")["fields"]["m_text"] = ""
    inventory = g.transform(g.field(native, "itemInventoryDisplay"))
    bind("inventoryRoot", inventory)
    icons = g.clone(*original("itemIconSource"), "item-template", hud)
    icons["fields"]["m_Name"] = "Owned inactive item template"
    item = g.component(icons, "ItemIcon")
    template = g.add(icons, "Assembly-CSharp:.RecoveredHudPresentation", dict(itemImage=item["fields"]["image"], itemCount=item["fields"]["stackText"]))
    bind("itemTemplate", template)
    g.active(icons, False)
    for field in ("glowImage", "durationImage"):
        if item["fields"][field]["m_PathID"]:
            g.active(g.field(item, field), False)
    g.hide(icons, {"Managed_Sprite_ItemCounter", "Timer"})
    count = g.field(item, "stackText")
    g.active(count, True)
    count["fields"]["m_text"] = ""
    size = g.transform(icons)["fields"]["m_SizeDelta"]
    g.add(
        g.game(inventory),
        "UnityEngine.UI:UnityEngine.UI.GridLayoutGroup",
        dict(m_CellSize={k: max(48.0, size[k]) for k in ("x", "y")}, m_Spacing=dict(x=0.0, y=0.0), m_Constraint=1, m_ConstraintCount=12),
    )
    buffs = g.find(hud, "BuffDisplay")
    bind("buffRoot", g.transform(buffs))
    v["buffWidth"] = buffs["fields"]["iconWidth"]
    buff = g.clone_ref(buffs["fields"]["buffIconPrefab"], buffs, "buff-template", hud)
    buff["fields"]["m_Name"] = "Owned inactive buff template"
    g.active(buff, False)
    bind("buffTemplate", g.component(buff, "BuffIcon"))
    notices = g.find(hud, "NotificationUIController")
    bind("notificationRoot", g.transform(notices))
    noticego = g.clone_ref(notices["fields"]["genericNotificationPrefab"], notices, "notification-template", hud)
    noticego["fields"]["m_Name"] = "Owned inactive pickup template"
    g.active(noticego, False)
    notice = g.component(noticego, "GenericNotification")
    flash = g.find(noticego, "AnimateUIAlpha")
    pickup = g.add(
        noticego,
        "Assembly-CSharp:.RecoveredPickupPresentation",
        dict(
            nativeFade=g.ref(notice),
            title=notice["fields"]["titleTMP"],
            description=g.ref(g.component(g.field(notice, "descriptionText"), "TMP_Text")),
            nativeFlash=g.ref(flash),
        ),
    )
    bind("notificationTemplate", pickup)
    for field in ("previousIconImage", "extraPanel", "tempPanel"):
        if notice["fields"][field]["m_PathID"]:
            g.active(g.field(notice, field), False)
    stage = g.text(g.named(hud, "MapNameCluster"), "MainText")
    bind("stage", stage)
    g.text(g.game(g.field(g.transform(stage), "m_Father")), "Subtext")["fields"]["m_text"] = ""
    info = g.clone(*original("runInfoSource"), "run-info", g.named(hud, "UpperRightCluster"))
    g.active(info, True)
    timer = g.text(g.named(info, "TimerPanel"), "TimerText")
    bind("timer", timer)
    bind("timerFormatter", g.component(g.game(timer), "TimerText"))
    stagecount = g.text(g.named(info, "StageCountRoot"), "Stage Text")
    bind("stageCount", stagecount)
    bind("ambientLevel", g.text(g.named(info, "AmbientLevelRoot"), "Level Text"))
    difficulty = g.find(info, "DifficultyBarController")
    v["difficultySegments"] = copy.deepcopy(difficulty["fields"]["segmentDefs"])
    v["levelsPerSegment"] = difficulty["fields"]["levelsPerSegment"]
    v["difficultyBackground"] = difficulty["fields"]["difficultyBarBackdrop"]
    textgo = g.clone(stagecount["asset"], g.game(stagecount)["source_id"], "difficulty-tier", g.game(difficulty))
    textgo["fields"]["m_Name"] = "Owned difficulty tier"
    textrow = g.component(textgo, "TMP_Text")
    textrow["fields"]["m_HorizontalAlignment"] = 2
    textrow["fields"]["m_VerticalAlignment"] = 512
    rect = g.transform(textgo)["fields"]
    rect.update(m_AnchorMin=dict(x=0.0, y=0.0), m_AnchorMax=dict(x=1.0, y=1.0), m_AnchoredPosition=dict(x=0.0, y=0.0), m_SizeDelta=dict(x=0.0, y=0.0))
    rect["m_LocalPosition"].update(x=0.0, y=0.0)
    bind("difficulty", textrow)
    g.active(g.field(difficulty, "segmentContainer"), False)
    for p in difficulty["fields"]["wormGearImages"]:
        g.active(g.resolve(p, difficulty), False)
    g.hide(info, {"Managed_Sprite_Timer", "DifficultyIcon", "ArtifactPanel", "DifficultyTutorial"})
    strip = g.named(info, "ObjectiveStrip")
    g.active(strip, True)
    objective = g.text(strip, "Label")
    bind("objective", objective)
    bind("objectiveLayout", g.component(strip, "LayoutElement"))
    g.active(objective, True)
    objective["fields"]["m_fontColor"] = dict(r=1.0, g=1.0, b=1.0, a=1.0)
    g.transform(strip)["fields"]["m_LocalScale"] = dict(x=1.0, y=1.0, z=1.0)
    g.hide(
        hud,
        {
            "SteamBuildLabel",
            "DebugStats",
            "TutorialObjectiveText",
            "ScoreboardPanel",
            "InspectPanelArea",
            "CinematicUI",
            "VoiceChatNotifications",
            "VoiceChatNotificationManager",
            "ChatBoxRoot",
            "CharacterStats",
            "LunarCoinRoot",
            "VoidCoinRoot",
            "SharedSufferingRoot",
            "Managed_Sprite_HP",
            "RemoteOp",
            "MovePanel",
            "AimPanel",
            "AimPanel (1)",
            "AimPanel (2)",
            "AimPanel (3)",
            "SprintCluster",
            "Hitmarker",
            "CrosshairExtras",
            "ContextNotification",
            "InventoryCluster",
        },
    )
    for go in g.descendants(hud):
        if go["fields"]["m_Name"].startswith("TUTORIAL:"):
            g.active(go, False)
    for field in ("buffRoot", "notificationRoot", "currentHealth", "fullHealth"):
        g.active(g.resolve(v[field]), True)
    for field in ("mainContainer", "mainUIPanel"):
        g.active(g.field(native, field), True)
    current = g.resolve(v["currentHealth"])
    g.active(g.field(g.transform(current), "m_Father"), True)
    cross = g.clone(*original("crosshairSource"), "crosshair", g.named(hud, "CrosshairCanvas"))
    g.active(cross, True)
    controller = g.component(cross, "CrosshairController")
    for field, source in [
        ("spreadPositions", "spriteSpreadPositions"),
        ("spreadImages", "remapSprites"),
        ("spreadAngle", "maxSpreadAngle"),
        ("minSpreadAlpha", "minSpreadAlpha"),
        ("maxSpreadAlpha", "maxSpreadAlpha"),
    ]:
        v[field] = copy.deepcopy(controller["fields"][source])
    for part in v["spreadPositions"]:
        g.resolve(part["target"])["fields"]["m_LocalPosition"] = copy.deepcopy(part["zeroPosition"])
    for ptr in v["spreadImages"]:
        g.resolve(ptr)["fields"]["m_Color"] = dict(r=1.0, g=1.0, b=1.0, a=v["minSpreadAlpha"])
    g.normalize(hud, labels)
    hud["fields"]["m_Name"] = "Hud"
    g.active(hud, False)
    return g, hud


def _ui():
    path = Path(__file__).with_name("player_ui.py")
    spec = importlib.util.spec_from_file_location("_hud_source_ui", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def authored_schemas(U, store, ui, graph, native, managed):
    receipt = store.json(Path(managed) / "result.json")
    U.require(receipt.get("success") is True and receipt.get("phase") == "managed-produced", "source-produced HUD managed assemblies required")
    providers = store.json(Path(managed) / "providers.json")
    templates = {}
    for typ in ui.layout["types"]:
        for kind in ("Vector2f", "Vector3f", "Vector4f", "ColorRGBA", "Rectf", "RectOffset"):
            choices = U.S._native_subtrees(U.explicit_tree(typ["tree"]), kind)
            if choices:
                templates.setdefault(kind, choices[0])
    original = next(o for o in ui.objects.values() if o.type.value == 114)
    runtime_base = []
    for node in U.S.tree_nodes(U.explicit_tree(original.typ["tree"])):
        if node["level"] == 1 and node["name"] not in {"m_GameObject", "m_Enabled", "m_Script", "m_Name"}:
            break
        runtime_base.append(node)
    U.require([n["name"] for n in runtime_base if n["level"] == 1] == ["m_GameObject", "m_Enabled", "m_Script", "m_Name"], "HUD runtime script base differs")
    with closing(U.S._RegistryTypes(store.pc / "Risk of Rain 2_Data/Managed", providers, store.pin, native, templates)) as clr:
        for row in graph.rows:
            if row["source_id"] is not None:
                continue
            assembly, full = row["identity"].split(":", 1)
            namespace, cls = full.rsplit(".", 1)
            tree = clr.script_schema((assembly + ".dll", namespace, cls), {})
            U.require(tree is not None, "authored HUD component has no CLR schema")
            base_names = {n["name"] for n in clr.base if n["level"] == 1}
            custom = [n for name, nodes in U.S._fields(U.S.tree_nodes(tree)).items() if name not in base_names for n in nodes]
            runtime_tree = U.S._tree(runtime_base + custom)
            node = U.node_from_tree(runtime_tree)
            fields = U.zero(node)
            U.require(set(row["fields"]) <= fields.keys(), "HUD assignment is absent from CLR schema")
            fields.update(row["fields"])
            row.update(fields=fields, node=node, typ=dict(class_id=114, stripped=0, script_type=-1, hash=bytes(16), tree=runtime_tree))


def sdk_curves(U, source):
    with Path(source).open("rb") as raw:
        raw.size = Path(source).stat().st_size
        layout = U.W.read_serialized(raw)
    curves = []
    for typ in layout["types"]:
        if not typ.get("tree"):
            continue
        tree = U.explicit_tree(typ["tree"])
        if any(n["type"] == "AnimationCurve" and n["name"] == "m_Falloff" for n in U.S.tree_nodes(tree)):
            curves.append(tree)
    U.require(curves, "SDK editor curve transfer absent")
    return curves[0]


def produce(profile_path, profile_sha256, pc, player, builtin_extra, editor_resources, managed, registry, output):
    """Current source HUD phase; parent supplies its freshly produced registry.

    All authored transformations mirror RecoveredHudBuilder. Historical player
    files, exported YAML, a cached prefab and saved ID maps are not providers.
    """
    U = _ui()
    started = time.monotonic()
    output = Path(output)
    profile_path = Path(profile_path).resolve(strict=True)
    U.require(output.is_dir(), "HUD parent must create its new target tree")
    audit = output.parent.parent.parent.parent / "hud-source"
    audit.mkdir(exist_ok=False)
    with closing(U.Sources(pc)) as store:
        selected = store.json(profile_path, dict(sha256=profile_sha256))
        U.require(selected.get("schema") == "owner-source-hud-v1" and selected.get("input_id") == player["input_id"], "unsupported source HUD profile")
        U.require(set(selected["roots"]) == {"hudSource", "runInfoSource", "itemIconSource", "crosshairSource"}, "HUD root population differs")
        ui = store.asset(selected["roots"]["hudSource"]["source"])
        scripts = U.original_identities(store.asset(selected["scripts_source"]))
        linker = U.Linker(store, ui, player, profile_path.parent, selected, builtin_extra, output)
        labels_raw, pins = U.P.language_strings(store.pc, player["text_assets"]["language"])
        labels = {row["key"]: row["value"] for row in json.loads(labels_raw)["entries"]}
        for path, pin in pins:
            store.pin(path, dict(bytes=pin[0], sha256=pin[1]))
        graph, hud = construct(U, store, scripts, selected["roots"], labels)
        native = U.P.script_sdk_schema(editor_resources, player["script_properties_sdk"])
        store.pin(editor_resources, player["script_properties_sdk"])
        curves = sdk_curves(U, editor_resources)
        authored_schemas(U, store, ui, graph, native, managed)
        rows, allocation = graph.finalize()
        ids = {r["id"] for r in rows}
        bodies = {}
        types = []
        scripts_table = []
        objects = []
        offset = 0
        manifest = []
        for row in rows:
            U.require(set(row["fields"]) == {n.m_Name for n in row["node"].m_Children}, "HUD fields differ from runtime schema")

            def admit(ptr):
                pid = ptr["m_PathID"]
                if pid and (ptr["m_FileID"] or pid not in ids):
                    member, original = U.reference_key(row["asset"], ptr)
                    if member not in store.assets:
                        graph.resolve(pointer(("asset", member, original)))
                return ptr

            U.map_pointers(row["fields"], admit)
            linker.ui = row["asset"]
            fields = linker.fields(row, ids, registry["script_ids"])
            typ = dict(row["typ"])
            if typ["class_id"] == 114:
                typ["tree"] = U.explicit_tree(typ["tree"])
                assembly, full = row["identity"].split(":", 1)
                namespace, cls = full.rsplit(".", 1)
                identity = assembly + ".dll", namespace, cls
                sid = registry["script_ids"][identity]
                properties = U.S._script_record(registry["bodies"][sid])["properties"]
                schema = (
                    U.P.OBJECTS.legacy_animate_hash_tree(typ["tree"], curves, U.S)
                    if any(n["type"] == "AnimationCurve" for n in U.S.tree_nodes(typ["tree"]))
                    else typ["tree"]
                )
                U.require(U.S.properties_hash(cls, namespace, identity[0], schema, native) == properties, "HUD runtime schema differs from source registry")
                reference = (1, sid)
                if reference not in scripts_table:
                    scripts_table.append(reference)
                typ.update(script_type=scripts_table.index(reference), script_id=U.S.md4((cls + namespace + identity[0]).encode()), hash=properties)
            if typ not in types:
                types.append(typ)
                (audit / ("schema-" + str(len(types) - 1) + ".tree")).write_bytes(typ["tree"])
            body = U.encode(fields, row["node"])
            offset = (offset + 7) // 8 * 8
            objects.append(dict(path_id=row["id"], type_id=types.index(typ), offset=offset, bytes=len(body)))
            bodies[row["id"]] = body
            offset += len(body)
            manifest.append(
                dict(id=row["id"], path=row["path"], identity=row["identity"], type_id=types.index(typ), fields=fields, sha256=hashlib.sha256(body).hexdigest())
            )
        layout = dict(
            engine="2021.3.45f2",
            platform=13,
            trees=False,
            types=types,
            objects=objects,
            scripts=scripts_table,
            externals=[dict(empty="", guid=bytes(16), type=0, path=p) for p in linker.externals],
            ref_types=[],
            user="",
        )
        name = selected["file"]
        U.require(re.fullmatch("[a-f0-9]{32}", name) is not None, "unsafe HUD output filename")
        with (output / name).open("xb") as stream:
            U.W.write_serialized(stream, layout, lambda row: io.BytesIO(bodies[row["path_id"]]))
        files = {
            file: dict(
                bytes=(output / file).stat().st_size,
                sha256=U.P.sha(output / file),
                source_role="pc-sdk-and-authored-hud",
                source=selected["roots"]["hudSource"]["source"]["path"],
            )
            for file in linker.generated | {name}
        }
        (audit / "objects.json").write_text(json.dumps(manifest, indent=2) + "\n")
        store.recheck()
        result = dict(
            files=files,
            objects=len(rows),
            resources={"RecoveredUI/Hud": dict(file=name, path_id=allocation[hud["key"]])},
            profile_sha256=profile_sha256,
            provider_pins=store.pins,
            external_files=linker.externals,
            phone_qualified=False,
            runtime_qualified=False,
            historical_raw_exact=False,
            seconds=time.monotonic() - started,
        )
        (audit / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        return result

"""The 24 animation scenes (UX section 6). Drawings carry no text; control names are labels."""

from __future__ import annotations

from ...i18n import N_
from . import shapes as s
from .engine import Layer, Scene, Track


def T(layer: str, prop: str, *keys: tuple[float, float]) -> Track:
    return Track(layer, prop, tuple(keys))


def _front(mirrorless: bool = False, with_lens: bool = True) -> list[Layer]:
    layers = [Layer("body", s.front_body(mirrorless), z=1)]
    if with_lens:
        layers.append(Layer("lens", s.lens(), z=2))
    return layers


def _rear() -> list[Layer]:
    return [Layer("body", s.rear_body(), z=1), Layer("screen", s.screen_content(), z=2)]


SCENES: dict[str, Scene] = {}


def _add(scene: Scene) -> None:
    SCENES[scene.id] = scene


_add(
    Scene(
        "plug_usb",
        (
            *_front(),
            Layer("port", s.usb_port(), z=3),
            Layer("plug", s.usb_plug(), at=(340, 162), z=4),
        ),
        (T("plug", "x", (0, 120), (0.55, 0), (0.9, 0), (1, 120)),),
        control_label=N_("USB port"),
    )
)
_add(
    Scene(
        "power_on",
        (
            *_front(),
            Layer("switch", s.power_switch(), z=3),
            Layer("knob", f'<circle cx="312" cy="92" r="7" fill="{s.ACCENT}"/>', z=4),
            Layer("finger", s.finger(), at=(318, 80), z=5),
        ),
        (
            T("finger", "y", (0, -50), (0.4, 0), (0.7, 0), (1, -50)),
            T("knob", "x", (0, 0), (0.4, 0), (0.55, 14), (1, 14)),
        ),
        control_label=N_("Power switch"),
    )
)
_add(
    Scene(
        "read_serial",
        (
            Layer("body", s.front_body(), z=1),
            Layer(
                "plate",
                f'<rect x="120" y="150" width="190" height="34" rx="4" fill="{s.PAPER}" stroke="{s.LINE}" stroke-width="2"/>'
                f'<path d="M132 162 L290 162 M132 174 L240 174" stroke="{s.LINE}" stroke-width="3"/>',
                z=3,
                opacity=0.0,
            ),
        ),
        (
            T("body", "rotate", (0, 0), (0.4, 180), (1, 180)),
            T("plate", "opacity", (0, 0), (0.4, 0), (0.55, 1), (1, 1)),
        ),
        control_label=N_("Serial plate"),
    )
)
_add(
    Scene(
        "tilt_mount",
        (*_front(with_lens=False),),
        (T("body", "rotate", (0, 0), (0.4, 24), (0.7, -8), (1, 0)),),
        control_label=N_("Lens mount"),
    )
)
_add(
    Scene(
        "change_lens",
        (*_front(), Layer("hint", s.arrow(0), at=(120, 250), z=4)),
        (
            T("lens", "x", (0, 0), (0.35, 0), (0.6, 130), (0.85, 130), (1, 0)),
            T("lens", "rotate", (0, 0), (0.35, -30), (0.6, -30), (1, 0)),
        ),
        control_label=N_("Lens release"),
    )
)
_add(
    Scene(
        "body_cap",
        (*_front(with_lens=False), Layer("cap", s.body_cap(), z=3)),
        (
            T("cap", "x", (0, -130), (0.55, 0), (1, 0)),
            T("cap", "y", (0, -50), (0.55, 0), (1, 0)),
            T("cap", "rotate", (0, -50), (0.55, 0), (0.8, 25), (1, 25)),
        ),
        control_label=N_("Body cap"),
    )
)
_add(
    Scene(
        "cover_viewfinder",
        (*_rear(), Layer("hand", s.hand_cover(), at=(200, 53), z=5)),
        (T("hand", "x", (0, 90), (0.5, 0), (1, 0)), T("hand", "y", (0, -30), (0.5, 0), (1, 0))),
        control_label=N_("Viewfinder"),
    )
)
_add(
    Scene(
        "af_mf",
        (
            Layer("lensbody", s.focus_ring(), z=1),
            Layer("track", s.switch_track(), at=(150, 232), z=2),
            Layer("knob", s.switch_knob(), at=(168, 245), z=3),
            Layer("finger", s.finger(), at=(168, 245), z=4),
        ),
        (
            T("knob", "x", (0, 0), (0.4, 0), (0.6, 28), (1, 28)),
            T("finger", "x", (0, 0), (0.4, 0), (0.6, 28), (1, 28)),
            T("finger", "y", (0, 40), (0.3, 5), (1, 5)),
        ),
        control_label=N_("AF/MF switch"),
    )
)
_add(
    Scene(
        "focus_ring",
        (
            Layer("lensbody", s.focus_ring(), z=1),
            Layer("hint", s.arrow(0), at=(160, 90), z=2),
            Layer("hint2", s.arrow(180), at=(160, 255), z=2),
        ),
        (T("lensbody", "rotate", (0, -4), (0.5, 4), (1, -4)),),
        control_label=N_("Focus ring"),
    )
)
_add(
    Scene(
        "command_dial",
        (
            *_front(),
            Layer("dial", s.top_dial(), z=3),
            Layer("hint", s.arrow(-20), at=(110, 55), z=4),
        ),
        (T("dial", "rotate", (0, 0), (0.5, 70), (1, 0)),),
        control_label=N_("Command dial"),
    )
)
_add(
    Scene(
        "half_press",
        (
            *_front(),
            Layer("shutter", s.top_shutter(), z=3),
            Layer("finger", s.finger(), at=(285, 86), z=5),
            Layer("focus", s.focus_box(), at=(215, 170), z=6, opacity=0.0),
        ),
        (
            T("finger", "y", (0, -40), (0.4, 0), (0.55, 5), (0.9, 5), (1, -40)),
            T("focus", "opacity", (0, 0), (0.5, 0), (0.6, 1), (0.8, 1), (0.9, 0)),
        ),
        control_label=N_("Shutter button"),
    )
)
_add(
    Scene(
        "hold_shutter",
        (
            *_front(),
            Layer("shutter", s.top_shutter(), z=3),
            Layer("finger", s.finger(), at=(285, 86), z=5),
            Layer("d1", s.burst_dot(), at=(110, 50), z=6, opacity=0.0),
            Layer("d2", s.burst_dot(), at=(160, 50), z=6, opacity=0.0),
            Layer("d3", s.burst_dot(), at=(210, 50), z=6, opacity=0.0),
        ),
        (
            T("finger", "y", (0, -40), (0.2, 8), (0.9, 8), (1, -40)),
            T("d1", "opacity", (0, 0), (0.3, 0), (0.35, 1), (1, 1)),
            T("d2", "opacity", (0, 0), (0.5, 0), (0.55, 1), (1, 1)),
            T("d3", "opacity", (0, 0), (0.7, 0), (0.75, 1), (1, 1)),
        ),
        control_label=N_("Shutter button"),
    )
)
_add(
    Scene(
        "af_joystick",
        (
            *_rear(),
            Layer("stick", s.joystick(), z=3),
            Layer("finger", s.finger(), at=(300, 200), z=5),
            Layer("focus", s.focus_box(), at=(165, 160), z=4),
        ),
        (
            T("finger", "x", (0, 0), (0.5, 12), (1, 0)),
            T("finger", "y", (0, 10), (0.5, 4), (1, 10)),
            T("focus", "x", (0, -40), (0.5, 40), (1, -40)),
        ),
        control_label=N_("AF joystick"),
    )
)
_add(
    Scene(
        "card_door",
        (
            *_rear(),
            Layer("door", s.card_door(), z=3),
            Layer("card", s.card(), at=(276, 158), z=2),
        ),
        (
            T("door", "rotate", (0, 0), (0.3, -70), (0.9, -70), (1, 0)),
            T("door", "opacity", (0, 1), (0.3, 0.4), (0.9, 0.4), (1, 1)),
            T("card", "x", (0, 0), (0.4, 0), (0.7, 50), (1, 50)),
        ),
        control_label=N_("Card door"),
    )
)
_add(
    Scene(
        "card_reader",
        (
            Layer(
                "reader",
                f'<rect x="240" y="120" width="110" height="70" rx="8" fill="{s.BODY_DARK}" stroke="{s.LINE}" stroke-width="2"/><rect x="250" y="150" width="70" height="8" fill="{s.GLASS}"/>',
                z=1,
            ),
            Layer("card", s.card(), at=(80, 130), z=2),
        ),
        (T("card", "x", (0, 0), (0.6, 160), (0.85, 160), (1, 0)),),
        control_label=N_("Card reader"),
    )
)
_add(
    Scene(
        "tripod_chart",
        (
            Layer("tripod", s.tripod(), at=(-60, 0), z=1),
            Layer("cam", s.front_body(), at=(-40, -60), z=2),
            Layer("chart", s.chart(), at=(290, 110), z=1),
            Layer("hint", s.arrow(0), at=(250, 160), z=3),
        ),
        (T("hint", "x", (0, -10), (0.5, 10), (1, -10)),),
        control_label=N_("Focus chart"),
    )
)
_add(
    Scene(
        "aim_flat",
        (
            Layer("wall", s.wall(), at=(280, 90), z=1),
            Layer("cam", s.front_body(), at=(-60, 20), z=2),
            Layer("rays", s.rays(), at=(270, 150), z=3),
        ),
        (
            T("cam", "rotate", (0, -4), (0.5, 4), (1, -4)),
            T("rays", "opacity", (0, 0.2), (0.5, 1), (1, 0.2)),
        ),
        control_label=N_("Even bright surface"),
    )
)
_add(
    Scene(
        "diopter",
        (
            *_rear(),
            Layer("eye", s.eye(), at=(200, 18), z=5),
            Layer(
                "dial",
                f'<circle cx="250" cy="52" r="8" fill="{s.BODY_LIGHT}" stroke="{s.LINE}" stroke-width="2"/><path d="M250 46 L250 58" stroke="{s.LINE}" stroke-width="2"/>',
                z=4,
                pivot=(250.0, 52.0),
            ),
        ),
        (T("dial", "rotate", (0, 0), (0.5, 120), (1, 0)),),
        control_label=N_("Diopter dial"),
    )
)
_add(
    Scene(
        "mount_play",
        (*_front(), Layer("hint", s.arrow(90), at=(215, 250), z=4)),
        (
            T("lens", "x", (0, -3), (0.25, 3), (0.5, -3), (0.75, 3), (1, -3)),
            T("lens", "rotate", (0, -2), (0.5, 2), (1, -2)),
        ),
        control_label=N_("Lens mount"),
    )
)
_add(
    Scene(
        "popup_flash",
        (
            Layer("flash", s.flash_head(), at=(200, 78), z=1),
            *_front(),
        ),
        (T("flash", "y", (0, 20), (0.4, -26), (0.9, -26), (1, 20)),),
        control_label=N_("Flash"),
    )
)
_add(
    Scene(
        "solid_colours",
        (
            *_rear(),
            *(
                Layer(
                    n,
                    f'<rect x="86" y="106" width="158" height="108" rx="4" fill="{c}"/>',
                    z=3 + i,
                    opacity=0.0,
                )
                for i, (n, c) in enumerate(
                    (
                        ("red", "#d02020"),
                        ("green", "#20a040"),
                        ("blue", "#2040d0"),
                        ("white", "#ffffff"),
                        ("black", "#000000"),
                    )
                )
            ),
        ),
        tuple(
            T(
                n,
                "opacity",
                (0, 0),
                (i / 5, 0),
                (i / 5 + 0.01, 1),
                ((i + 1) / 5 - 0.01, 1),
                ((i + 1) / 5, 0),
                (1, 0),
            )
            for i, n in enumerate(("red", "green", "blue", "white", "black"))
        ),
        duration_ms=4500,
        control_label=N_("Screen"),
    )
)
_add(
    Scene(
        "press_buttons",
        (
            *_rear(),
            Layer("b1", s.button_dot(270, 90), z=3),
            Layer("b2", s.button_dot(300, 90), z=3),
            Layer("b3", s.button_dot(330, 90), z=3),
            Layer("b4", s.button_dot(270, 230), z=3),
            Layer("b5", s.button_dot(330, 230), z=3),
            Layer("finger", s.finger(), at=(270, 90), z=5),
        ),
        (
            T("finger", "x", (0, 0), (0.25, 30), (0.5, 60), (0.75, 0), (1, 0)),
            T("finger", "y", (0, 0), (0.5, 0), (0.75, 140), (1, 0)),
        ),
        control_label=N_("Buttons"),
    )
)
_add(
    Scene(
        "move_spot",
        (
            Layer("meter", s.meter_circle(), at=(200, 150), z=2),
            Layer("square", s.bright_square(), at=(90, 150), z=3),
            Layer(
                "frame",
                f'<rect x="60" y="80" width="280" height="140" rx="6" fill="none" stroke="{s.BODY_LIGHT}" stroke-width="3"/>',
                z=1,
            ),
        ),
        (T("square", "x", (0, 0), (0.5, 110), (1, 220)),),
        control_label=N_("Spot metering area"),
    )
)
_add(
    Scene(
        "mirrorless_sample",
        (*_front(mirrorless=True),),
        (
            T("body", "rotate", (0, -3), (0.5, 3), (1, -3)),
            T("lens", "rotate", (0, -3), (0.5, 3), (1, -3)),
        ),
        control_label=N_("Camera body"),
    )
)

SCENE_IDS = tuple(SCENES)

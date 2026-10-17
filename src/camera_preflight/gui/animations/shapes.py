"""Text-free vector parts for the animation scenes (D-19, D-20).

Two generic body types, DSLR and mirrorless, with no brand shapes or logos. Every part is an
SVG fragment drawn in a 400 x 300 scene. Colours are fixed neutrals plus one accent used to
highlight the control involved.
"""

from __future__ import annotations

BODY = "#5d6272"
BODY_DARK = "#3b3f4b"
BODY_LIGHT = "#8a90a3"
GLASS = "#1c2030"
ACCENT = "#2f6bff"
SKIN = "#e0b08f"
PAPER = "#f2f3f7"
LINE = "#2a2d38"


def wrap(content: str, w: int = 400, h: int = 300) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
        f"{content}</svg>"
    )


def front_body(mirrorless: bool = False) -> str:
    """Front view: body, grip and (for a DSLR) the prism hump, with the empty mount."""
    hump = (
        ""
        if mirrorless
        else f'<path d="M165 100 L180 68 Q200 60 220 68 L235 100 Z" fill="{BODY_DARK}"/>'
    )
    evf = (
        f'<rect x="228" y="78" width="26" height="22" rx="4" fill="{BODY_DARK}"/>'
        if mirrorless
        else ""
    )
    return (
        f'<rect x="60" y="100" width="280" height="130" rx="18" fill="{BODY}" stroke="{LINE}" stroke-width="2"/>'
        f'<rect x="60" y="100" width="64" height="130" rx="18" fill="{BODY_DARK}"/>'
        f"{hump}{evf}"
        f'<circle cx="215" cy="170" r="54" fill="{BODY_DARK}" stroke="{LINE}" stroke-width="2"/>'
        f'<circle cx="215" cy="170" r="42" fill="{GLASS}"/>'
    )


def lens(opened: bool = False) -> str:
    """Lens seen from the front, drawn over the mount."""
    return (
        f'<circle cx="215" cy="170" r="50" fill="{BODY_DARK}" stroke="{LINE}" stroke-width="3"/>'
        f'<circle cx="215" cy="170" r="38" fill="{BODY_LIGHT}"/>'
        f'<circle cx="215" cy="170" r="28" fill="{GLASS}"/>'
        f'<circle cx="203" cy="158" r="7" fill="#ffffff" opacity="0.45"/>'
        f'<rect x="262" y="166" width="10" height="8" fill="{ACCENT}" opacity="{1 if opened else 0.0}"/>'
    )


def body_cap() -> str:
    return (
        f'<circle cx="215" cy="170" r="50" fill="#2a2d38" stroke="{LINE}" stroke-width="3"/>'
        f'<circle cx="215" cy="170" r="36" fill="#363a48"/>'
        f'<rect x="209" y="136" width="12" height="9" rx="2" fill="{BODY_LIGHT}"/>'
    )


def top_shutter() -> str:
    return f'<rect x="268" y="88" width="34" height="12" rx="5" fill="{BODY_LIGHT}" stroke="{LINE}" stroke-width="2"/>'


def top_dial() -> str:
    return (
        f'<circle cx="110" cy="92" r="18" fill="{BODY_LIGHT}" stroke="{LINE}" stroke-width="2"/>'
        f'<path d="M110 76 L110 108 M94 92 L126 92" stroke="{LINE}" stroke-width="2"/>'
    )


def power_switch() -> str:
    return (
        f'<rect x="300" y="84" width="40" height="16" rx="8" fill="{BODY_DARK}"/>'
        f'<circle cx="312" cy="92" r="7" fill="{BODY_LIGHT}"/>'
    )


def rear_body() -> str:
    """Rear view: screen, viewfinder, joystick, dial and card door."""
    return (
        f'<rect x="50" y="60" width="300" height="190" rx="20" fill="{BODY}" stroke="{LINE}" stroke-width="2"/>'
        f'<rect x="170" y="38" width="60" height="30" rx="8" fill="{BODY_DARK}"/>'
        f'<rect x="184" y="46" width="32" height="16" rx="4" fill="{GLASS}"/>'
        f'<rect x="80" y="100" width="170" height="120" rx="8" fill="{GLASS}" stroke="{LINE}" stroke-width="2"/>'
    )


def screen_content(color: str = "#4a5a80") -> str:
    return f'<rect x="86" y="106" width="158" height="108" rx="4" fill="{color}"/>'


def joystick() -> str:
    return (
        f'<circle cx="300" cy="200" r="16" fill="{BODY_DARK}" stroke="{LINE}" stroke-width="2"/>'
        f'<circle cx="300" cy="200" r="8" fill="{BODY_LIGHT}"/>'
    )


def rear_dial() -> str:
    return (
        f'<circle cx="300" cy="120" r="20" fill="{BODY_LIGHT}" stroke="{LINE}" stroke-width="2"/>'
        f'<path d="M300 100 L300 140 M280 120 L320 120" stroke="{LINE}" stroke-width="2"/>'
    )


def card_door() -> str:
    return f'<rect x="262" y="150" width="76" height="62" rx="6" fill="{BODY_DARK}" stroke="{LINE}" stroke-width="2"/>'


def card() -> str:
    return (
        f'<path d="M0 0 L40 0 L48 8 L48 62 L0 62 Z" fill="{BODY_LIGHT}" stroke="{LINE}" stroke-width="2"/>'
        f'<rect x="8" y="48" width="32" height="8" fill="{ACCENT}"/>'
    )


def focus_box(color: str = ACCENT) -> str:
    return f'<rect x="-14" y="-14" width="28" height="28" rx="3" fill="none" stroke="{color}" stroke-width="3"/>'


def finger() -> str:
    """A fingertip pointing down, origin at the tip."""
    return (
        f'<path d="M-12 -70 L12 -70 L12 -10 Q12 6 0 6 Q-12 6 -12 -10 Z" fill="{SKIN}" stroke="#a97c5f" stroke-width="2"/>'
        f'<ellipse cx="0" cy="-12" rx="7" ry="5" fill="#f2cdb3"/>'
    )


def hand_cover() -> str:
    return f'<rect x="-26" y="-18" width="52" height="36" rx="10" fill="{SKIN}" stroke="#a97c5f" stroke-width="2"/>'


def arrow(angle_deg: float = 0.0) -> str:
    return (
        f'<g transform="rotate({angle_deg})">'
        f'<path d="M-30 0 L24 0 M12 -12 L26 0 L12 12" fill="none" stroke="{ACCENT}" stroke-width="5" '
        f'stroke-linecap="round" stroke-linejoin="round"/></g>'
    )


def usb_plug() -> str:
    return (
        f'<rect x="-44" y="-9" width="38" height="18" rx="3" fill="{BODY_LIGHT}" stroke="{LINE}" stroke-width="2"/>'
        f'<rect x="-6" y="-12" width="26" height="24" rx="4" fill="{BODY_DARK}"/>'
        f'<path d="M-44 0 Q-90 0 -120 40" fill="none" stroke="{BODY_DARK}" stroke-width="8" stroke-linecap="round"/>'
    )


def usb_port() -> str:
    return f'<rect x="326" y="150" width="14" height="24" rx="3" fill="{GLASS}" stroke="{ACCENT}" stroke-width="2"/>'


def tripod() -> str:
    return (
        f'<path d="M200 230 L150 290 M200 230 L250 290 M200 230 L200 290" stroke="{BODY_DARK}" '
        f'stroke-width="8" stroke-linecap="round"/>'
        f'<rect x="176" y="218" width="48" height="14" rx="4" fill="{BODY_LIGHT}" stroke="{LINE}" stroke-width="2"/>'
    )


def chart() -> str:
    cells = ""
    for r in range(4):
        for c in range(4):
            if (r + c) % 2 == 0:
                cells += f'<rect x="{c * 20}" y="{r * 20}" width="20" height="20" fill="{LINE}"/>'
    return f'<rect x="0" y="0" width="80" height="80" fill="{PAPER}" stroke="{LINE}" stroke-width="2"/>{cells}'


def wall() -> str:
    return f'<rect x="0" y="0" width="90" height="120" rx="4" fill="#fdfdf5" stroke="{BODY_LIGHT}" stroke-width="3"/>'


def rays() -> str:
    return (
        '<path d="M0 -30 L-70 -60 M0 0 L-80 0 M0 30 L-70 60" stroke="#f5b800" stroke-width="4" '
        'stroke-linecap="round" stroke-dasharray="10 8"/>'
    )


def flash_head() -> str:
    return f'<rect x="-24" y="-10" width="48" height="20" rx="5" fill="{BODY_LIGHT}" stroke="{LINE}" stroke-width="2"/>'


def switch_track() -> str:
    return f'<rect x="0" y="0" width="64" height="26" rx="13" fill="{BODY_DARK}" stroke="{LINE}" stroke-width="2"/>'


def switch_knob() -> str:
    return f'<circle cx="0" cy="0" r="10" fill="{ACCENT}"/>'


def focus_ring() -> str:
    return (
        f'<rect x="100" y="120" width="120" height="100" rx="12" fill="{BODY_DARK}" stroke="{LINE}" stroke-width="2"/>'
        + "".join(
            f'<path d="M{110 + i * 10} 124 L{110 + i * 10} 216" stroke="{BODY_LIGHT}" stroke-width="3"/>'
            for i in range(10)
        )
    )


def burst_dot() -> str:
    return f'<rect x="-9" y="-6" width="18" height="12" rx="2" fill="{ACCENT}"/>'


def eye() -> str:
    return (
        f'<path d="M-30 0 Q0 -26 30 0 Q0 26 -30 0 Z" fill="{PAPER}" stroke="{LINE}" stroke-width="3"/>'
        f'<circle cx="0" cy="0" r="9" fill="{LINE}"/>'
    )


def meter_circle() -> str:
    return f'<circle cx="0" cy="0" r="22" fill="none" stroke="{ACCENT}" stroke-width="3"/>'


def bright_square() -> str:
    return '<rect x="-14" y="-14" width="28" height="28" rx="3" fill="#ffe27a" stroke="#c99a00" stroke-width="2"/>'


def button_dot(x: float, y: float) -> str:
    return f'<circle cx="{x}" cy="{y}" r="9" fill="{BODY_LIGHT}" stroke="{LINE}" stroke-width="2"/>'

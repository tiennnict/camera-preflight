"""Layered SVG scene player on QGraphicsView with a keyframe timeline (D-19, FR-GUI-06).

A scene is data: named SVG layers and tracks that move them over time. The player loops the
scene, can pause and replay, and shows one static key frame when reduced motion is on.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

from PySide6.QtCore import QByteArray, QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n_helpers import tr
from .shapes import wrap


@dataclass(frozen=True)
class Layer:
    name: str
    svg: str  # fragment in scene coordinates unless ``at`` is given
    at: tuple[float, float] = (0.0, 0.0)  # placement of the fragment origin
    pivot: tuple[float, float] | None = None  # rotation and scale pivot in scene coordinates
    z: float = 0.0
    opacity: float = 1.0


@dataclass(frozen=True)
class Track:
    layer: str
    prop: str  # "x", "y", "rotate", "scale", "opacity"
    keys: tuple[tuple[float, float], ...]  # (time 0..1, value)


@dataclass(frozen=True)
class Scene:
    id: str
    layers: tuple[Layer, ...]
    tracks: tuple[Track, ...] = ()
    duration_ms: int = 3200
    key_frame: float = 0.55  # time (0..1) shown under reduced motion
    control_label: str = ""  # translatable name of the highlighted control
    extra: dict[str, str] = field(default_factory=dict)


def _ease(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * t)


def sample(track: Track, t: float) -> float:
    keys = track.keys
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in itertools.pairwise(keys):
        if t0 <= t <= t1:
            span = max(t1 - t0, 1e-9)
            return v0 + (v1 - v0) * _ease((t - t0) / span)
    return keys[-1][1]


class ScenePlayer(QGraphicsView):
    """Draws a scene; ``set_time`` positions every layer for a time in 0..1."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(0, 0, 400, 300, self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setBackgroundBrush(Qt.GlobalColor.transparent)
        self.setMinimumSize(260, 200)
        self._items: dict[str, QGraphicsSvgItem] = {}
        self._renderers: list[QSvgRenderer] = []
        self._base: dict[str, tuple[float, float]] = {}
        self._scene_def: Scene | None = None

    def load(self, scene: Scene) -> None:
        self._scene.clear()
        self._items.clear()
        self._renderers.clear()
        self._base.clear()
        self._scene_def = scene
        for layer in scene.layers:
            data = QByteArray(
                wrap(
                    f'<g transform="translate({layer.at[0]},{layer.at[1]})">{layer.svg}</g>'
                ).encode()
            )
            renderer = QSvgRenderer(data, self)
            item = QGraphicsSvgItem()
            item.setSharedRenderer(renderer)
            item.setZValue(layer.z)
            item.setOpacity(layer.opacity)
            pivot = layer.pivot or (200.0, 150.0)
            item.setTransformOriginPoint(QPointF(*pivot))
            self._scene.addItem(item)
            self._renderers.append(renderer)
            self._items[layer.name] = item
            self._base[layer.name] = (0.0, 0.0)
        self.set_time(scene.key_frame)
        self.fitInView(QRectF(0, 0, 400, 300), Qt.AspectRatioMode.KeepAspectRatio)

    def set_time(self, t: float) -> None:
        if self._scene_def is None:
            return
        state: dict[str, dict[str, float]] = {}
        for tr_ in self._scene_def.tracks:
            state.setdefault(tr_.layer, {})[tr_.prop] = sample(tr_, t)
        for name, item in self._items.items():
            props = state.get(name, {})
            item.setPos(props.get("x", 0.0), props.get("y", 0.0))
            item.setRotation(props.get("rotate", 0.0))
            item.setScale(props.get("scale", 1.0))
            if "opacity" in props:
                item.setOpacity(props["opacity"])

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        self.fitInView(QRectF(0, 0, 400, 300), Qt.AspectRatioMode.KeepAspectRatio)


class AnimationPanel(QWidget):
    """Scene player with Pause and Replay, and a caption naming the highlighted control."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.player = ScenePlayer(self)
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setLoopCount(-1)
        self._anim.setEasingCurve(QEasingCurve.Type.Linear)
        self._anim.valueChanged.connect(lambda v: self.player.set_time(float(v)))
        self._reduced = False
        self.caption = QLabel("")
        self.caption.setObjectName("muted")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pause_btn = QPushButton()
        self.replay_btn = QPushButton()
        self.pause_btn.clicked.connect(self.toggle)
        self.replay_btn.clicked.connect(self.replay)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.pause_btn)
        row.addWidget(self.replay_btn)
        row.addStretch(1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.player, 1)
        lay.addWidget(self.caption)
        lay.addLayout(row)
        self.scene: Scene | None = None
        self.retranslate()

    def retranslate(self) -> None:
        self.pause_btn.setText(tr("Play") if self._paused() else tr("Pause"))
        self.replay_btn.setText(tr("Replay"))
        if self.scene is not None:
            self.caption.setText(tr(self.scene.control_label) if self.scene.control_label else "")

    def _paused(self) -> bool:
        return self._reduced or self._anim.state() != QVariantAnimation.State.Running

    def set_reduced_motion(self, on: bool) -> None:
        self._reduced = on
        if self.scene is not None:
            self.show_scene(self.scene)

    def show_scene(self, scene: Scene) -> None:
        self.scene = scene
        self._anim.stop()
        self.player.load(scene)
        self._anim.setDuration(scene.duration_ms)
        self.pause_btn.setEnabled(not self._reduced)
        self.replay_btn.setEnabled(not self._reduced)
        if not self._reduced:
            self._anim.start()  # static key frame is already shown when reduced
        self.retranslate()

    def toggle(self) -> None:
        if self._anim.state() == QVariantAnimation.State.Running:
            self._anim.pause()
        else:
            self._anim.resume() if self._anim.state() == QVariantAnimation.State.Paused else self._anim.start()
        self.retranslate()

    def replay(self) -> None:
        self._anim.stop()
        self._anim.start()
        self.retranslate()

    def stop(self) -> None:
        self._anim.stop()

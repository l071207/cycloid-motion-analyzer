from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from PyQt5.QtCore import QPoint, QPointF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import (
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
)

from cycloid_analyzer.cycloid import CycloidParameters, generate_cycloid_points


Point = tuple[float, float]


@dataclass(frozen=True)
class CycloidRecord:
    record_id: str
    start: Point
    end: Point
    parameters: CycloidParameters


@dataclass(frozen=True)
class MovementTraceRecord:
    record_id: str
    points: list[Point]


@dataclass
class CanvasStateRecord:
    background: QPixmap
    cycloids: list[CycloidRecord]
    movement_trace: MovementTraceRecord | None
    selected_cycloid_ids: list[str]

def build_path(points: list[Point]) -> QPainterPath:
    path = QPainterPath()
    if not points:
        return path
    path.moveTo(*points[0])
    for point in points[1:]:
        path.lineTo(*point)
    return path


class CycloidPathItem(QGraphicsPathItem):
    def __init__(self, record: CycloidRecord):
        super().__init__()
        self.record = record
        self.setFlag(QGraphicsPathItem.ItemIsSelectable)
        self.refresh()

    def refresh(self) -> None:
        self.setPath(build_path(generate_cycloid_points(self.record.start, self.record.end, self.record.parameters)))
        self._update_pen()

    def _update_pen(self) -> None:
        if self.isSelected():
            self.setPen(QPen(QColor("#ff6b6b"), 3))
        else:
            self.setPen(QPen(QColor("#f59e0b"), 2))

    def itemChange(self, change, value):
        if change == QGraphicsPathItem.ItemSelectedHasChanged:
            self._update_pen()
        return super().itemChange(change, value)

    @property
    def points(self) -> list[Point]:
        return generate_cycloid_points(self.record.start, self.record.end, self.record.parameters)


class MovementTraceItem(QGraphicsPathItem):
    def __init__(self, record: MovementTraceRecord):
        super().__init__()
        self.record = record
        self.setZValue(1)
        self.setPen(QPen(QColor("#2563eb"), 2))
        self.setPath(build_path(record.points))


class CanvasView(QGraphicsView):
    cycloid_drawn = pyqtSignal(tuple, tuple)
    movement_trace_drawn = pyqtSignal(object)
    cycloid_selection_changed = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#111827"))
        self.setDragMode(QGraphicsView.NoDrag)

        self._background_item = QGraphicsPixmapItem()
        self._background_item.setZValue(-10)
        self._scene.addItem(self._background_item)

        self._cycloid_items: dict[str, CycloidPathItem] = {}
        self._movement_trace_item: MovementTraceItem | None = None
        self._mode = "select"
        self._current_parameters = CycloidParameters()
        self._draft_start: QPointF | None = None
        self._draft_points: list[Point] = []
        self._preview_item: QGraphicsPathItem | None = None
        self._last_pan_point: QPoint | None = None
        self._scene.selectionChanged.connect(self._notify_selection_changed)

    def set_mode(self, mode: str) -> None:
        if mode != self._mode:
            self._clear_draft()
        self._mode = mode
        self.setDragMode(QGraphicsView.ScrollHandDrag if mode == "pan" else QGraphicsView.NoDrag)

    def set_current_parameters(self, parameters: CycloidParameters) -> None:
        self._current_parameters = parameters

    def set_background_pixmap(self, pixmap: QPixmap) -> None:
        self.apply_state(CanvasStateRecord(pixmap, [], None, []))
        self.fitInView(self._background_item, Qt.KeepAspectRatio)

    def apply_state(self, state: CanvasStateRecord) -> None:
        self._clear_draft()
        for record_id in list(self._cycloid_items):
            self.remove_cycloid(record_id)
        self.set_movement_trace(None)
        self._background_item.setPixmap(QPixmap(state.background))
        for record in state.cycloids:
            self.add_cycloid(record)
        for record_id in state.selected_cycloid_ids:
            item = self._cycloid_items.get(record_id)
            if item:
                item.setSelected(True)
        if state.movement_trace:
            self.set_movement_trace(state.movement_trace)
        self._scene.setSceneRect(self._background_item.boundingRect())

    def capture_state(self) -> CanvasStateRecord:
        trace = self.get_movement_trace_record()
        trace_copy = MovementTraceRecord(trace.record_id, list(trace.points)) if trace else None
        return CanvasStateRecord(
            QPixmap(self._background_item.pixmap()),
            [item.record for item in self._cycloid_items.values()],
            trace_copy,
            [record.record_id for record in [self.selected_cycloid_record()] if record],
        )

    def reset_zoom(self) -> None:
        if not self._background_item.pixmap().isNull():
            self.fitInView(self._background_item, Qt.KeepAspectRatio)
        else:
            self.resetTransform()

    def add_cycloid(self, record: CycloidRecord) -> None:
        existing = self._cycloid_items.get(record.record_id)
        was_selected = existing.isSelected() if existing else False
        self.remove_cycloid(record.record_id)
        item = CycloidPathItem(record)
        item.setZValue(2)
        self._cycloid_items[record.record_id] = item
        self._scene.addItem(item)
        item.setSelected(was_selected)

    def remove_cycloid(self, record_id: str) -> None:
        item = self._cycloid_items.pop(record_id, None)
        if item:
            self._scene.removeItem(item)

    def update_cycloid(self, record: CycloidRecord) -> None:
        item = self._cycloid_items.get(record.record_id)
        if item is None:
            self.add_cycloid(record)
            return
        was_selected = item.isSelected()
        item.record = record
        item.refresh()
        item.setSelected(was_selected)

    def cycloid_record(self, record_id: str) -> CycloidRecord | None:
        item = self._cycloid_items.get(record_id)
        return item.record if item else None

    def selected_cycloid_record(self) -> CycloidRecord | None:
        for item in self._scene.selectedItems():
            if isinstance(item, CycloidPathItem):
                return item.record
        return None

    def selected_cycloid_points(self) -> list[Point]:
        for item in self._scene.selectedItems():
            if isinstance(item, CycloidPathItem):
                return item.points
        return []

    def get_movement_trace_record(self) -> MovementTraceRecord | None:
        return self._movement_trace_item.record if self._movement_trace_item else None

    def set_movement_trace(self, record: MovementTraceRecord | None) -> None:
        if self._movement_trace_item:
            self._scene.removeItem(self._movement_trace_item)
            self._movement_trace_item = None
        if record:
            self._movement_trace_item = MovementTraceItem(record)
            self._scene.addItem(self._movement_trace_item)

    def movement_trace_points(self) -> list[Point]:
        return self._movement_trace_item.record.points if self._movement_trace_item else []

    def wheelEvent(self, event) -> None:
        if event.angleDelta().y() == 0:
            event.ignore()
            return
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def mousePressEvent(self, event) -> None:
        scene_pos = self.mapToScene(event.pos())
        if event.button() == Qt.MiddleButton:
            self._last_pan_point = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        if self._mode == "draw" and event.button() == Qt.LeftButton and self._background_contains(scene_pos):
            self._draft_start = scene_pos
            self._set_preview(build_path([(scene_pos.x(), scene_pos.y())]))
            event.accept()
            return
        if self._mode == "trace" and event.button() == Qt.LeftButton and self._background_contains(scene_pos):
            current = (scene_pos.x(), scene_pos.y())
            if not self._draft_points:
                self._draft_points = [current]
            elif current != self._draft_points[-1]:
                self._draft_points.append(current)
            self._set_preview(build_path(self._draft_points))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        scene_pos = self.mapToScene(event.pos())
        if self._last_pan_point is not None:
            delta = event.pos() - self._last_pan_point
            self._last_pan_point = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        if self._mode == "draw" and self._draft_start is not None:
            scene_pos = self._clamp_to_background(scene_pos)
            points = generate_cycloid_points(
                (self._draft_start.x(), self._draft_start.y()),
                (scene_pos.x(), scene_pos.y()),
                self._current_parameters,
            )
            self._set_preview(build_path(points))
            event.accept()
            return
        if self._mode == "trace" and self._draft_points and event.buttons() & Qt.LeftButton:
            scene_pos = self._clamp_to_background(scene_pos)
            current = (scene_pos.x(), scene_pos.y())
            if hypot(current[0] - self._draft_points[-1][0], current[1] - self._draft_points[-1][1]) >= 2:
                self._draft_points.append(current)
                self._set_preview(build_path(self._draft_points))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        scene_pos = self.mapToScene(event.pos())
        if event.button() == Qt.MiddleButton and self._last_pan_point is not None:
            self._last_pan_point = None
            self.unsetCursor()
            event.accept()
            return
        if self._mode == "draw" and self._draft_start is not None and event.button() == Qt.LeftButton:
            scene_pos = self._clamp_to_background(scene_pos)
            start = (self._draft_start.x(), self._draft_start.y())
            end = (scene_pos.x(), scene_pos.y())
            self._draft_start = None
            self._clear_preview()
            self.cycloid_drawn.emit(start, end)
            event.accept()
            return
        if self._mode == "trace" and self._draft_points and event.button() == Qt.LeftButton:
            scene_pos = self._clamp_to_background(scene_pos)
            current = (scene_pos.x(), scene_pos.y())
            if not self._draft_points or current != self._draft_points[-1]:
                self._draft_points.append(current)
            self._set_preview(build_path(self._draft_points))
            event.accept()
            return
        if self._mode == "trace" and self._draft_points and event.button() == Qt.RightButton:
            scene_pos = self._clamp_to_background(scene_pos)
            current = (scene_pos.x(), scene_pos.y())
            if current != self._draft_points[-1]:
                self._draft_points.append(current)
            points = list(self._draft_points)
            self._clear_draft()
            if any(point != points[0] for point in points[1:]):
                self.movement_trace_drawn.emit(points)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _set_preview(self, path: QPainterPath) -> None:
        if self._preview_item is None:
            self._preview_item = QGraphicsPathItem()
            pen = QPen(QColor("#93c5fd"), 2, Qt.DashLine)
            self._preview_item.setPen(pen)
            self._preview_item.setZValue(3)
            self._scene.addItem(self._preview_item)
        self._preview_item.setPath(path)

    def _clear_preview(self) -> None:
        if self._preview_item is not None:
            self._scene.removeItem(self._preview_item)
            self._preview_item = None

    def _clear_draft(self) -> None:
        self._draft_start = None
        self._draft_points = []
        self._clear_preview()

    def _notify_selection_changed(self) -> None:
        self.cycloid_selection_changed.emit(self.selected_cycloid_record())

    def _background_contains(self, scene_pos: QPointF) -> bool:
        pixmap = self._background_item.pixmap()
        return not pixmap.isNull() and self._background_item.boundingRect().contains(scene_pos)

    def _clamp_to_background(self, scene_pos: QPointF) -> QPointF:
        rect = self._background_item.boundingRect()
        if rect.isNull():
            return scene_pos
        return QPointF(
            min(max(scene_pos.x(), rect.left()), rect.right()),
            min(max(scene_pos.y(), rect.top()), rect.bottom()),
        )

from __future__ import annotations

from dataclasses import replace

from PyQt5.QtWidgets import QUndoCommand

from PyQt5.QtGui import QPixmap

from cycloid_analyzer.canvas import CanvasStateRecord, CycloidRecord, MovementTraceRecord


class AddCycloidCommand(QUndoCommand):
    def __init__(self, canvas, record: CycloidRecord):
        super().__init__("Add cycloid")
        self._canvas = canvas
        self._record = record

    def redo(self) -> None:
        self._canvas.add_cycloid(self._record)

    def undo(self) -> None:
        self._canvas.remove_cycloid(self._record.record_id)


class UpdateCycloidCommand(QUndoCommand):
    def __init__(self, canvas, before: CycloidRecord, after: CycloidRecord):
        super().__init__("Update cycloid")
        self._canvas = canvas
        self._before = replace(before)
        self._after = replace(after)

    def redo(self) -> None:
        self._canvas.update_cycloid(self._after)

    def undo(self) -> None:
        self._canvas.update_cycloid(self._before)


class ReplaceMovementTraceCommand(QUndoCommand):
    def __init__(self, canvas, new_trace: MovementTraceRecord):
        super().__init__("Trace movement")
        self._canvas = canvas
        self._new_trace = MovementTraceRecord(new_trace.record_id, list(new_trace.points))
        previous_trace = canvas.get_movement_trace_record()
        self._previous_trace = (
            MovementTraceRecord(previous_trace.record_id, list(previous_trace.points)) if previous_trace else None
        )

    def redo(self) -> None:
        self._canvas.set_movement_trace(self._new_trace)

    def undo(self) -> None:
        self._canvas.set_movement_trace(self._previous_trace)


class ReplaceCanvasStateCommand(QUndoCommand):
    def __init__(
        self,
        canvas,
        before: CanvasStateRecord,
        after: CanvasStateRecord,
        label: str = "Replace canvas",
        on_redo_applied=None,
        on_undo_applied=None,
        restore_after_selection: bool = False,
    ):
        super().__init__(label)
        self._canvas = canvas
        self._before = self._copy_state(before, include_selection_ids=True)
        self._after = self._copy_state(after, include_selection_ids=restore_after_selection)
        self._on_redo_applied = on_redo_applied
        self._on_undo_applied = on_undo_applied

    def redo(self) -> None:
        self._canvas.apply_state(self._after)
        if self._on_redo_applied:
            self._on_redo_applied()

    def undo(self) -> None:
        self._canvas.apply_state(self._before)
        if self._on_undo_applied:
            self._on_undo_applied()

    def _copy_state(self, state: CanvasStateRecord, include_selection_ids: bool) -> CanvasStateRecord:
        trace = (
            MovementTraceRecord(state.movement_trace.record_id, list(state.movement_trace.points))
            if state.movement_trace
            else None
        )
        return CanvasStateRecord(
            QPixmap(state.background),
            [replace(record) for record in state.cycloids],
            trace,
            list(state.selected_cycloid_ids) if include_selection_ids else [],
        )

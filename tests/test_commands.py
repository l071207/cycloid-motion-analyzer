import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QUndoStack

from cycloid_analyzer.commands import AddCycloidCommand, ReplaceMovementTraceCommand, UpdateCycloidCommand
from cycloid_analyzer.canvas import CycloidRecord, MovementTraceRecord
from cycloid_analyzer.cycloid import CycloidParameters
from cycloid_analyzer.main_window import MainWindow


class FakeCanvas:
    def __init__(self):
        self.cycloids = {}
        self.trace = None

    def add_cycloid(self, record):
        self.cycloids[record.record_id] = record

    def remove_cycloid(self, record_id):
        self.cycloids.pop(record_id, None)

    def update_cycloid(self, record):
        self.cycloids[record.record_id] = record

    def get_movement_trace_record(self):
        return self.trace

    def set_movement_trace(self, record):
        self.trace = record


class CommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_add_cycloid_command_round_trip(self):
        canvas = FakeCanvas()
        stack = QUndoStack()
        record = CycloidRecord("c1", (0.0, 0.0), (10.0, 0.0), CycloidParameters())
        stack.push(AddCycloidCommand(canvas, record))
        self.assertIn("c1", canvas.cycloids)
        stack.undo()
        self.assertNotIn("c1", canvas.cycloids)
        stack.redo()
        self.assertIn("c1", canvas.cycloids)

    def test_update_cycloid_command_round_trip(self):
        canvas = FakeCanvas()
        before = CycloidRecord("c1", (0.0, 0.0), (10.0, 0.0), CycloidParameters(radius=25.0))
        after = CycloidRecord("c1", (0.0, 0.0), (10.0, 0.0), CycloidParameters(radius=40.0))
        canvas.add_cycloid(before)
        stack = QUndoStack()
        stack.push(UpdateCycloidCommand(canvas, before, after))
        self.assertEqual(canvas.cycloids["c1"].parameters.radius, 40.0)
        stack.undo()
        self.assertEqual(canvas.cycloids["c1"].parameters.radius, 25.0)

    def test_replace_trace_command_restores_previous_trace(self):
        canvas = FakeCanvas()
        canvas.trace = MovementTraceRecord("movement-trace", [(0.0, 0.0), (1.0, 1.0)])
        stack = QUndoStack()
        stack.push(ReplaceMovementTraceCommand(canvas, MovementTraceRecord("movement-trace", [(2.0, 2.0), (3.0, 3.0)])))
        self.assertEqual(canvas.trace.points[0], (2.0, 2.0))
        stack.undo()
        self.assertEqual(canvas.trace.points[0], (0.0, 0.0))

    def test_live_parameter_edit_is_undoable(self):
        window = MainWindow()
        record = CycloidRecord("c1", (0.0, 0.0), (50.0, 0.0), CycloidParameters(radius=25.0))
        window.canvas.add_cycloid(record)
        window.canvas._cycloid_items["c1"].setSelected(True)
        QApplication.processEvents()

        window._begin_parameter_edit()
        window.radius_slider.setValue(60)
        window._commit_parameter_edit()

        self.assertEqual(window.canvas.cycloid_record("c1").parameters.radius, 60.0)
        window.undo_stack.undo()
        self.assertEqual(window.canvas.cycloid_record("c1").parameters.radius, 25.0)
        window.close()


if __name__ == "__main__":
    unittest.main()

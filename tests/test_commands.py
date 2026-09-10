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

        window.radius_slider.sliderPressed.emit()
        window.radius_slider.setValue(60)
        window.radius_slider.sliderReleased.emit()

        self.assertEqual(window.canvas.cycloid_record("c1").parameters.radius, 60.0)
        window.undo_stack.undo()
        self.assertEqual(window.canvas.cycloid_record("c1").parameters.radius, 25.0)
        window.close()

    def test_loading_demo_resets_undo_stack(self):
        window = MainWindow()
        record = CycloidRecord("c1", (0.0, 0.0), (50.0, 0.0), CycloidParameters(radius=25.0))
        window.canvas.add_cycloid(record)
        window.canvas._cycloid_items["c1"].setSelected(True)
        QApplication.processEvents()
        window.metrics_label.setText("Average distance: 1.23px")
        window.radius_slider.setValue(60)

        window.load_demo_assets()

        self.assertEqual(len(window.canvas.movement_trace_points()), 14)
        self.assertTrue(window.undo_stack.canUndo())
        self.assertEqual(window.selection_label.text(), "Selected cycloid: none")
        self.assertEqual(window.radius_slider.value(), 40)
        self.assertEqual(window.frequency_slider.value(), 20)
        self.assertEqual(window.phase_slider.value(), 0)
        self.assertEqual(
            window.metrics_label.text(),
            "Average distance: —\nRMSE: —\nMax distance: —\nLength ratio: —\nSimilarity score: —",
        )
        window.undo_stack.undo()
        self.assertEqual(window.selection_label.text(), "Selected cycloid: c1")
        self.assertEqual(window.radius_slider.value(), 25)
        self.assertEqual(len(window.canvas.movement_trace_points()), 0)
        window.close()

    def test_selection_change_clears_stale_metrics(self):
        window = MainWindow()
        record = CycloidRecord("c1", (0.0, 0.0), (50.0, 0.0), CycloidParameters(radius=25.0))
        window.canvas.add_cycloid(record)
        window.metrics_label.setText("Average distance: 1.23px")
        window._handle_selection_changed(None)
        self.assertEqual(
            window.metrics_label.text(),
            "Average distance: —\nRMSE: —\nMax distance: —\nLength ratio: —\nSimilarity score: —",
        )
        window.close()


if __name__ == "__main__":
    unittest.main()

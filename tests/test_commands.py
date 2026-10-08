import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QUndoStack

from cycloid_analyzer.commands import AddCycloidCommand, ReplaceMovementTraceCommand, UpdateCycloidCommand
from cycloid_analyzer.canvas import CanvasView, CycloidRecord, MovementTraceRecord
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

        window.radius_spinbox.setValue(60)
        window.radius_spinbox.editingFinished.emit()

        self.assertEqual(window.canvas.cycloid_record("c1").parameters.radius, 60.0)
        window.undo_stack.undo()
        self.assertEqual(window.canvas.cycloid_record("c1").parameters.radius, 25.0)
        window.close()

    def test_programmatic_parameter_change_is_not_undoable(self):
        window = MainWindow()
        record = CycloidRecord("c1", (0.0, 0.0), (50.0, 0.0), CycloidParameters(radius=25.0))
        window.canvas.add_cycloid(record)
        window.canvas._cycloid_items["c1"].setSelected(True)
        QApplication.processEvents()

        window.radius_spinbox.setValue(60)

        self.assertEqual(window.canvas.cycloid_record("c1").parameters.radius, 60.0)
        self.assertFalse(window.undo_stack.canUndo())
        window.close()

    def test_metric_radius_requires_calibration(self):
        window = MainWindow()
        window.radius_unit_combo.setCurrentIndex(window.radius_unit_combo.findData("m"))
        self.assertEqual(window.radius_unit_combo.currentData(), "px")
        window.close()

    def test_calibration_enables_metric_radius_conversion(self):
        window = MainWindow()
        window._handle_calibration_drawn((0.0, 0.0), (100.0, 0.0))
        window.radius_unit_combo.setCurrentIndex(window.radius_unit_combo.findData("m"))
        window.radius_spinbox.setValue(0.5)
        window.radius_spinbox.editingFinished.emit()
        self.assertAlmostEqual(window.current_parameters().radius, 50.0)
        self.assertIn("1 m = 100.0 px", window.calibration_value.text())
        window.close()

    def test_calibration_enables_centimetre_radius_conversion(self):
        window = MainWindow()
        window._handle_calibration_drawn((0.0, 0.0), (200.0, 0.0))
        window.radius_unit_combo.setCurrentIndex(window.radius_unit_combo.findData("cm"))
        window.radius_spinbox.setValue(50.0)
        window.radius_spinbox.editingFinished.emit()
        self.assertAlmostEqual(window.current_parameters().radius, 100.0)
        self.assertIn("1 m = 200.0 px", window.calibration_value.text())
        window.close()

    def test_tiny_calibration_drag_is_rejected(self):
        window = MainWindow()
        window._handle_calibration_drawn((0.0, 0.0), (3.0, 4.0))
        self.assertIsNone(window.canvas.get_calibration_record())
        self.assertFalse(window.undo_stack.canUndo())
        window.close()

    def test_undoing_calibration_resets_metric_radius_unit(self):
        window = MainWindow()
        window._handle_calibration_drawn((0.0, 0.0), (100.0, 0.0))
        window.radius_unit_combo.setCurrentIndex(window.radius_unit_combo.findData("m"))
        window.radius_spinbox.setValue(0.5)
        window.undo_stack.undo()
        self.assertEqual(window.radius_unit_combo.currentData(), "px")
        self.assertEqual(window.radius_spinbox.value(), 40.0)
        self.assertEqual(window.calibration_value.text(), "Scale: not calibrated")
        window.undo_stack.redo()
        self.assertIn("1 m = 100.0 px", window.calibration_value.text())
        window.close()

    def test_calibration_undo_redo_preserves_selection(self):
        window = MainWindow()
        record = CycloidRecord("c1", (0.0, 0.0), (50.0, 0.0), CycloidParameters(radius=25.0))
        window.canvas.add_cycloid(record)
        window.canvas._cycloid_items["c1"].setSelected(True)
        QApplication.processEvents()
        window._handle_calibration_drawn((0.0, 0.0), (100.0, 0.0))
        self.assertEqual(window.selection_label.text(), "Selected cycloid: c1")
        window.undo_stack.undo()
        self.assertEqual(window.selection_label.text(), "Selected cycloid: c1")
        window.undo_stack.redo()
        self.assertEqual(window.selection_label.text(), "Selected cycloid: c1")
        self.assertIsNotNone(window.canvas.get_calibration_record())
        window.close()

    def test_radius_pixels_are_preserved_across_unit_switches(self):
        window = MainWindow()
        window._handle_calibration_drawn((0.0, 0.0), (100.0, 0.0))
        self.assertAlmostEqual(window.current_parameters().radius, 40.0)
        window.radius_unit_combo.setCurrentIndex(window.radius_unit_combo.findData("m"))
        self.assertAlmostEqual(window.radius_spinbox.value(), 0.4)
        self.assertAlmostEqual(window.current_parameters().radius, 40.0)
        window.radius_unit_combo.setCurrentIndex(window.radius_unit_combo.findData("cm"))
        self.assertAlmostEqual(window.radius_spinbox.value(), 40.0)
        self.assertAlmostEqual(window.current_parameters().radius, 40.0)
        window.close()

    def test_curve_type_change_is_undoable(self):
        window = MainWindow()
        record = CycloidRecord("c1", (0.0, 0.0), (50.0, 0.0), CycloidParameters(curve_type="standard"))
        window.canvas.add_cycloid(record)
        window.canvas._cycloid_items["c1"].setSelected(True)
        QApplication.processEvents()

        window.curve_type_combo.setCurrentIndex(window.curve_type_combo.findData("prolate"))

        self.assertEqual(window.canvas.cycloid_record("c1").parameters.curve_type, "prolate")
        self.assertTrue(window.undo_stack.canUndo())
        window.undo_stack.undo()
        self.assertEqual(window.canvas.cycloid_record("c1").parameters.curve_type, "standard")
        window.close()

    def test_curtate_curve_type_change_is_undoable(self):
        window = MainWindow()
        record = CycloidRecord("c1", (0.0, 0.0), (50.0, 0.0), CycloidParameters(curve_type="standard"))
        window.canvas.add_cycloid(record)
        window.canvas._cycloid_items["c1"].setSelected(True)
        QApplication.processEvents()

        window.curve_type_combo.setCurrentIndex(window.curve_type_combo.findData("curtate"))

        self.assertEqual(window.canvas.cycloid_record("c1").parameters.curve_type, "curtate")
        self.assertTrue(window.undo_stack.canUndo())
        window.undo_stack.undo()
        self.assertEqual(window.canvas.cycloid_record("c1").parameters.curve_type, "standard")
        window.close()

    def test_loading_demo_is_undoable_and_resets_panel(self):
        window = MainWindow()
        record = CycloidRecord("c1", (0.0, 0.0), (50.0, 0.0), CycloidParameters(radius=25.0))
        window.canvas.add_cycloid(record)
        window.canvas._cycloid_items["c1"].setSelected(True)
        QApplication.processEvents()
        window._handle_calibration_drawn((0.0, 0.0), (100.0, 0.0))
        window.metrics_label.setText("Average distance: 1.23px")
        window.radius_spinbox.setValue(60)

        window.load_demo_assets()

        self.assertEqual(len(window.canvas.movement_trace_points()), 14)
        self.assertTrue(window.undo_stack.canUndo())
        self.assertIsNone(window.canvas.get_calibration_record())
        self.assertEqual(window.selection_label.text(), "Selected cycloid: none")
        self.assertEqual(window.radius_spinbox.value(), 40)
        self.assertEqual(window.frequency_slider.value(), 20)
        self.assertEqual(window.phase_slider.value(), 0)
        self.assertEqual(
            window.metrics_label.text(),
            "Average distance: —\nRMSE: —\nMax distance: —\nLength ratio: —\nSimilarity score: —",
        )
        window.undo_stack.undo()
        self.assertEqual(window.selection_label.text(), "Selected cycloid: c1")
        self.assertIsNotNone(window.canvas.get_calibration_record())
        self.assertEqual(window.radius_spinbox.value(), 60)
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

    def test_comparison_metrics_use_pixels_and_metres_when_calibrated(self):
        window = MainWindow()
        record = CycloidRecord("c1", (0.0, 0.0), (50.0, 0.0), CycloidParameters(radius=25.0))
        window.canvas.add_cycloid(record)
        window.canvas._cycloid_items["c1"].setSelected(True)
        QApplication.processEvents()
        window.canvas.set_movement_trace(MovementTraceRecord("movement-trace", window.canvas.selected_cycloid_points()))

        window.compare_selected_cycloid()
        self.assertIn("px", window.metrics_label.text())

        window._handle_calibration_drawn((0.0, 0.0), (100.0, 0.0))
        window.compare_selected_cycloid()
        self.assertIn(" m", window.metrics_label.text())
        window.close()

    def test_calibrate_mode_emits_calibration_line(self):
        canvas = CanvasView()
        canvas.resize(200, 200)
        canvas.set_background_pixmap(QPixmap(200, 200))
        canvas.set_mode("calibrate")
        emitted = []
        canvas.calibration_drawn.connect(lambda start, end: emitted.append((start, end)))
        canvas.show()
        QApplication.processEvents()

        QTest.mousePress(canvas.viewport(), Qt.LeftButton, pos=QPoint(10, 10))
        QTest.mouseMove(canvas.viewport(), QPoint(110, 10))
        QTest.mouseRelease(canvas.viewport(), Qt.LeftButton, pos=QPoint(110, 10))

        self.assertEqual(len(emitted), 1)
        self.assertNotEqual(emitted[0][0], emitted[0][1])
        canvas.close()


if __name__ == "__main__":
    unittest.main()

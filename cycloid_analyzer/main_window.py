from __future__ import annotations

import json
import sys
from dataclasses import replace
from math import hypot
from pathlib import Path
from uuid import uuid4

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QDockWidget,
    QFormLayout,
    QUndoStack,
)

from cycloid_analyzer.canvas import CalibrationRecord, CanvasStateRecord, CanvasView, CycloidRecord, MovementTraceRecord
from cycloid_analyzer.commands import AddCycloidCommand, ReplaceCanvasStateCommand, ReplaceMovementTraceCommand, UpdateCycloidCommand
from cycloid_analyzer.comparison import compare_paths
from cycloid_analyzer.cycloid import CycloidParameters
from cycloid_analyzer.image_tools import load_png_pixmap

MIN_CALIBRATION_PIXELS = 10.0
CALIBRATION_LENGTH_METERS = 1.0


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cycloid Motion Analyzer")
        self.resize(1400, 900)

        self.undo_stack = QUndoStack(self)
        self.canvas = CanvasView()
        self.setCentralWidget(self.canvas)

        self._default_parameters = CycloidParameters()
        self._slider_update_guard = False
        self._edit_snapshot: CycloidRecord | None = None
        self._edit_record_id: str | None = None
        self._radius_pixels_buffer = self._default_parameters.radius

        self._build_actions()
        self._build_toolbar()
        self._build_parameter_panel()
        self._connect_signals()
        self._set_slider_values(self._default_parameters)
        self._reset_metrics_display()
        self.statusBar().showMessage("Open a PNG image, choose Draw Cycloid or Trace Movement, then work directly on the canvas.")

    def _build_actions(self) -> None:
        open_action = QAction("Open PNG…", self)
        open_action.triggered.connect(self.open_png_image)
        demo_action = QAction("Load bundled demo", self)
        demo_action.triggered.connect(self.load_demo_assets)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)

        undo_action = self.undo_stack.createUndoAction(self, "Undo")
        redo_action = self.undo_stack.createRedoAction(self, "Redo")

        reset_zoom_action = QAction("Reset Zoom", self)
        reset_zoom_action.triggered.connect(self.canvas.reset_zoom)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(open_action)
        file_menu.addAction(demo_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction(undo_action)
        edit_menu.addAction(redo_action)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(reset_zoom_action)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Tools", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        action_group = QActionGroup(self)
        action_group.setExclusive(True)
        self._mode_actions: dict[str, QAction] = {}
        for mode_name, label in [
            ("select", "Select"),
            ("draw", "Draw Cycloid"),
            ("calibrate", "Calibrate 1 m"),
            ("trace", "Trace Movement"),
            ("pan", "Pan"),
        ]:
            action = QAction(label, self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, mode=mode_name: checked and self._activate_mode(mode))
            action_group.addAction(action)
            toolbar.addAction(action)
            self._mode_actions[mode_name] = action
        self._mode_actions["select"].setChecked(True)

        toolbar.addSeparator()
        toolbar.addAction(self.undo_stack.createUndoAction(self, "Undo"))
        toolbar.addAction(self.undo_stack.createRedoAction(self, "Redo"))

    def _build_parameter_panel(self) -> None:
        self.radius_spinbox = QDoubleSpinBox(self)
        self.radius_spinbox.setRange(0.1, 5000.0)
        self.radius_spinbox.setDecimals(2)
        self.radius_spinbox.setValue(40.0)
        self.radius_spinbox.setSingleStep(1.0)
        self.frequency_slider = self._build_slider(10, 60, 20)
        self.phase_slider = self._build_slider(0, 360, 0)
        self.curve_type_combo = QComboBox(self)
        self.curve_type_combo.addItem("Standard", "standard")
        self.curve_type_combo.addItem("Prolate", "prolate")
        self.curve_type_combo.addItem("Curtate", "curtate")
        self.radius_unit_combo = QComboBox(self)
        self.radius_unit_combo.addItem("Pixels", "px")
        self.radius_unit_combo.addItem("Centimetres", "cm")
        self.radius_unit_combo.addItem("Metres", "m")

        self.radius_value = QLabel()
        self.radius_unit_value = QLabel()
        self.frequency_value = QLabel()
        self.phase_value = QLabel()
        self.curve_type_value = QLabel()
        self.calibration_value = QLabel("Scale: not calibrated")
        self.selection_label = QLabel("Selected cycloid: none")

        compare_button = QPushButton("Compare selected cycloid to movement trace")
        compare_button.clicked.connect(self.compare_selected_cycloid)

        self.metrics_label = QLabel("Average distance: —\nRMSE: —\nMax distance: —\nLength ratio: —\nSimilarity score: —")
        self.metrics_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        panel = QWidget()
        layout = QVBoxLayout(panel)
        form = QFormLayout()
        form.addRow("Type", self._labeled_control(self.curve_type_combo, self.curve_type_value))
        form.addRow("Radius", self._labeled_control(self.radius_spinbox, self.radius_value))
        form.addRow("Radius unit", self._labeled_control(self.radius_unit_combo, self.radius_unit_value))
        form.addRow("Scale", self.calibration_value)
        form.addRow("Frequency", self._labeled_control(self.frequency_slider, self.frequency_value))
        form.addRow("Phase", self._labeled_control(self.phase_slider, self.phase_value))
        layout.addWidget(self.selection_label)
        layout.addLayout(form)
        layout.addWidget(compare_button)
        layout.addWidget(self.metrics_label)
        layout.addStretch(1)

        dock = QDockWidget("Parameters & Analysis", self)
        dock.setWidget(panel)
        dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

        self.radius_spinbox.valueChanged.connect(self._on_radius_changed)
        self.radius_spinbox.editingFinished.connect(self._commit_radius_edit)
        for slider in (self.frequency_slider, self.phase_slider):
            slider.sliderPressed.connect(self._begin_parameter_edit)
            slider.valueChanged.connect(self._on_slider_changed)
            slider.sliderReleased.connect(self._commit_parameter_edit)
        self.curve_type_combo.currentIndexChanged.connect(self._on_curve_type_changed)
        self.radius_unit_combo.currentIndexChanged.connect(self._on_radius_unit_changed)

    def _build_slider(self, minimum: int, maximum: int, value: int) -> QSlider:
        slider = QSlider(Qt.Horizontal, self)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        return slider

    def _activate_mode(self, mode: str) -> None:
        self.canvas.set_mode(mode)
        messages = {
            "select": "Select a cycloid to inspect or edit its parameters.",
            "draw": "Drag on the image to create a cycloid preview, then release to place it.",
            "calibrate": "Drag a 1 metre ruler across the image where a real metre should appear.",
            "trace": "Drag to trace movement. Right-click to finish the current trace.",
            "pan": "Drag the view to pan the image and overlays.",
        }
        self.statusBar().showMessage(messages[mode])

    def _samples_dir(self) -> Path:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / "cycloid_analyzer" / "samples"
        return Path(__file__).resolve().parent / "samples"

    def _labeled_control(self, control: QWidget, value_label: QLabel) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(control)
        layout.addWidget(value_label)
        return container

    def _connect_signals(self) -> None:
        self.canvas.cycloid_drawn.connect(self._handle_cycloid_drawn)
        self.canvas.movement_trace_drawn.connect(self._handle_movement_trace_drawn)
        self.canvas.calibration_drawn.connect(self._handle_calibration_drawn)
        self.canvas.cycloid_selection_changed.connect(self._handle_selection_changed)

    def open_png_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Open PNG image", "", "PNG Images (*.png)")
        if file_path:
            pixmap = self._load_png(file_path)
            if pixmap is not None:
                self._replace_canvas_state(
                    CanvasStateRecord(QPixmap(pixmap), [], None, None, []),
                    "Open PNG image",
                    f"Loaded background image: {file_path}",
                )

    def _load_png(self, file_path: str) -> QPixmap | None:
        try:
            return load_png_pixmap(file_path)
        except ValueError as error:
            QMessageBox.warning(self, "Unable to open image", str(error))
            return None

    def _handle_cycloid_drawn(self, start: tuple[float, float], end: tuple[float, float]) -> None:
        if start == end:
            self.statusBar().showMessage("Drag to create a cycloid path.")
            return
        record = CycloidRecord(str(uuid4()), start, end, self.current_parameters())
        self.undo_stack.push(AddCycloidCommand(self.canvas, record))
        self.statusBar().showMessage("Cycloid created. Select it to adjust its parameters from the panel.")

    def _handle_movement_trace_drawn(self, points: list[tuple[float, float]]) -> None:
        if len(points) < 2:
            self.statusBar().showMessage("Trace a longer movement path for comparison.")
            return
        self.undo_stack.push(ReplaceMovementTraceCommand(self.canvas, MovementTraceRecord("movement-trace", points)))
        self.statusBar().showMessage("Movement trace updated.")

    def _handle_calibration_drawn(self, start: tuple[float, float], end: tuple[float, float]) -> None:
        if hypot(end[0] - start[0], end[1] - start[1]) < MIN_CALIBRATION_PIXELS:
            self.statusBar().showMessage(
                f"Calibration ruler is too short. Drag at least {MIN_CALIBRATION_PIXELS:.0f} pixels to mark 1 metre."
            )
            return
        state = self.canvas.capture_state()
        state.calibration = CalibrationRecord(start, end, CALIBRATION_LENGTH_METERS)
        self._replace_canvas_state(
            state,
            "Calibrate image",
            "Image calibrated: 1 metre ruler placed.",
            restore_after_selection=True,
        )

    def _handle_selection_changed(self, record: CycloidRecord | None) -> None:
        if self._edit_snapshot is not None and (self._edit_record_id != (record.record_id if record else None)):
            self._commit_parameter_edit()
        self._reset_metrics_display()
        self.selection_label.setText(f"Selected cycloid: {record.record_id[:8]}" if record else "Selected cycloid: none")
        if record:
            self._set_slider_values(record.parameters)
        else:
            self._set_slider_values(self._default_parameters)

    def _begin_parameter_edit(self) -> None:
        if self._slider_update_guard:
            return
        self._edit_snapshot = self.canvas.selected_cycloid_record()
        self._edit_record_id = self._edit_snapshot.record_id if self._edit_snapshot else None

    def _on_radius_changed(self) -> None:
        if self._slider_update_guard:
            return
        if self._edit_snapshot is None:
            self._begin_parameter_edit()
        self._radius_pixels_buffer = self._radius_display_value_to_pixels(self.radius_spinbox.value())
        parameters = self.current_parameters()
        self._sync_parameter_display(parameters)
        selected = self.canvas.selected_cycloid_record()
        if selected:
            self.canvas.update_cycloid(replace(selected, parameters=parameters))
        else:
            self.canvas.set_current_parameters(parameters)

    def _commit_radius_edit(self) -> None:
        if self._slider_update_guard:
            return
        if self._edit_snapshot is not None:
            self._commit_parameter_edit()
        else:
            self.canvas.set_current_parameters(self.current_parameters())

    def _on_slider_changed(self) -> None:
        parameters = self.current_parameters()
        self._sync_parameter_display(parameters)

        if self._slider_update_guard:
            return
        selected = self.canvas.selected_cycloid_record()
        if selected:
            self.canvas.update_cycloid(replace(selected, parameters=parameters))

    def _commit_parameter_edit(self) -> None:
        if not self._edit_snapshot:
            return
        current = self.canvas.cycloid_record(self._edit_record_id) if self._edit_record_id else None
        snapshot = self._edit_snapshot
        if current and current != self._edit_snapshot:
            self.undo_stack.push(UpdateCycloidCommand(self.canvas, snapshot, current))
            self.statusBar().showMessage("Cycloid parameters updated.")
        self._edit_snapshot = None
        self._edit_record_id = None

    def _set_slider_values(self, parameters: CycloidParameters) -> None:
        self._radius_pixels_buffer = parameters.radius
        self._slider_update_guard = True
        self._configure_radius_spinbox()
        self.radius_spinbox.setValue(self._radius_pixels_to_display_value(self._radius_pixels_buffer))
        self.frequency_slider.setValue(int(round(parameters.frequency * 10)))
        self.phase_slider.setValue(int(round(parameters.phase_degrees)))
        self.curve_type_combo.setCurrentIndex(max(0, self.curve_type_combo.findData(parameters.curve_type)))
        self._slider_update_guard = False
        self._sync_parameter_display(self.current_parameters())

    def _sync_parameter_display(self, parameters: CycloidParameters) -> None:
        self.curve_type_value.setText(parameters.curve_type.capitalize())
        self.radius_unit_value.setText(self.radius_unit_combo.currentText())
        unit = str(self.radius_unit_combo.currentData())
        if unit == "m":
            self.radius_value.setText(f"{self.radius_spinbox.value():.2f} m")
        elif unit == "cm":
            self.radius_value.setText(f"{self.radius_spinbox.value():.1f} cm")
        else:
            self.radius_value.setText(f"{parameters.radius:.1f}px")
        self.frequency_value.setText(f"{parameters.frequency:.1f} turns")
        self.phase_value.setText(f"{parameters.phase_degrees:.0f}°")
        pixels_per_meter = self.canvas.calibration_pixels_per_meter()
        if pixels_per_meter:
            self.calibration_value.setText(f"Scale: 1 m = {pixels_per_meter:.1f} px")
        else:
            self.calibration_value.setText("Scale: not calibrated")
        self.canvas.set_current_parameters(parameters)

    def current_parameters(self) -> CycloidParameters:
        return CycloidParameters(
            radius=self._radius_pixels_buffer,
            frequency=float(self.frequency_slider.value()) / 10.0,
            phase_degrees=float(self.phase_slider.value()),
            curve_type=str(self.curve_type_combo.currentData()),
        )

    def _on_curve_type_changed(self) -> None:
        parameters = self.current_parameters()
        self._sync_parameter_display(parameters)
        if self._slider_update_guard:
            return
        selected = self.canvas.selected_cycloid_record()
        if not selected or selected.parameters.curve_type == parameters.curve_type:
            return
        self.undo_stack.push(UpdateCycloidCommand(self.canvas, selected, replace(selected, parameters=parameters)))
        self.statusBar().showMessage(f"{parameters.curve_type.capitalize()} cycloid selected.")

    def _on_radius_unit_changed(self) -> None:
        if not self._sync_radius_unit_to_calibration():
            return
        self._slider_update_guard = True
        self._configure_radius_spinbox()
        self.radius_spinbox.setValue(self._radius_pixels_to_display_value(self._radius_pixels_buffer))
        self._slider_update_guard = False
        self._sync_parameter_display(self.current_parameters())

    def _reset_metrics_display(self) -> None:
        self.metrics_label.setText("Average distance: —\nRMSE: —\nMax distance: —\nLength ratio: —\nSimilarity score: —")

    def _sync_ui_to_canvas_state(self) -> None:
        self._sync_radius_unit_to_calibration()
        self._handle_selection_changed(self.canvas.selected_cycloid_record())

    def _sync_ui_after_canvas_state_redo(self) -> None:
        self.canvas.reset_zoom()
        self._sync_ui_to_canvas_state()

    def _replace_canvas_state(
        self,
        after: CanvasStateRecord,
        label: str,
        status_message: str | None = None,
        restore_after_selection: bool = False,
    ) -> None:
        before = self.canvas.capture_state()
        self.undo_stack.push(
            ReplaceCanvasStateCommand(
                self.canvas,
                before,
                after,
                label,
                on_redo_applied=self._sync_ui_after_canvas_state_redo,
                on_undo_applied=self._sync_ui_to_canvas_state,
                restore_after_selection=restore_after_selection,
            )
        )
        if status_message:
            self.statusBar().showMessage(status_message)

    def compare_selected_cycloid(self) -> None:
        cycloid_points = self.canvas.selected_cycloid_points()
        trace_points = self.canvas.movement_trace_points()
        if len(cycloid_points) < 2 or len(trace_points) < 2:
            QMessageBox.information(
                self,
                "Comparison unavailable",
                "Select a cycloid and create a movement trace before running comparison.",
            )
            return

        metrics = compare_paths(trace_points, cycloid_points)
        pixels_per_meter = self.canvas.calibration_pixels_per_meter()
        average_distance = metrics["average_distance"] / pixels_per_meter if pixels_per_meter else metrics["average_distance"]
        rmse = metrics["rmse"] / pixels_per_meter if pixels_per_meter else metrics["rmse"]
        max_distance = metrics["max_distance"] / pixels_per_meter if pixels_per_meter else metrics["max_distance"]
        self.metrics_label.setText(
            "\n".join(
                [
                    f"Average distance: {self._format_distance(average_distance, pixels_per_meter)}",
                    f"RMSE: {self._format_distance(rmse, pixels_per_meter)}",
                    f"Max distance: {self._format_distance(max_distance, pixels_per_meter)}",
                    f"Length ratio: {metrics['path_length_ratio']:.3f}",
                    f"Similarity score: {metrics['similarity_score']:.3f}",
                ]
            )
        )
        self.statusBar().showMessage("Comparison metrics updated.")

    def load_demo_assets(self) -> None:
        samples_dir = self._samples_dir()
        image_path = samples_dir / "demo_background.png"
        trace_path = samples_dir / "demo_movement_trace.json"

        try:
            pixmap = load_png_pixmap(str(image_path))
            with trace_path.open("r", encoding="utf-8") as file_handle:
                payload = json.load(file_handle)
            points = [(float(point[0]), float(point[1])) for point in payload["points"]]
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            QMessageBox.warning(self, "Unable to load demo assets", f"The bundled demo could not be loaded.\n\n{error}")
            return
        self._replace_canvas_state(
            CanvasStateRecord(QPixmap(pixmap), [], MovementTraceRecord("movement-trace", points), None, []),
            "Load demo",
            "Bundled demo loaded. Draw or adjust cycloids on top of the sample movement frame.",
        )

    def _radius_display_value_to_pixels_with_unit(self, value: float, unit: str) -> float:
        pixels_per_meter = self.canvas.calibration_pixels_per_meter()
        if unit == "m" and pixels_per_meter:
            return value * pixels_per_meter
        if unit == "cm" and pixels_per_meter:
            return (value / 100.0) * pixels_per_meter
        return value

    def _radius_display_value_to_pixels(self, value: float, unit_override: str | None = None) -> float:
        return self._radius_display_value_to_pixels_with_unit(value, unit_override or str(self.radius_unit_combo.currentData()))

    def _radius_pixels_to_display_value(self, pixels: float) -> float:
        unit = str(self.radius_unit_combo.currentData())
        pixels_per_meter = self.canvas.calibration_pixels_per_meter()
        if unit == "m" and pixels_per_meter:
            return pixels / pixels_per_meter
        if unit == "cm" and pixels_per_meter:
            return (pixels / pixels_per_meter) * 100.0
        return pixels

    def _sync_radius_unit_to_calibration(self) -> bool:
        if str(self.radius_unit_combo.currentData()) != "px" and self.canvas.calibration_pixels_per_meter() is None:
            selected = self.canvas.selected_cycloid_record()
            pixels = selected.parameters.radius if selected else self.canvas.current_parameters().radius
            self._radius_pixels_buffer = pixels
            self._slider_update_guard = True
            self.radius_unit_combo.setCurrentIndex(self.radius_unit_combo.findData("px"))
            self._configure_radius_spinbox()
            self.radius_spinbox.setValue(pixels)
            self._slider_update_guard = False
            self.statusBar().showMessage("Calibrate the image with the 1 m ruler before using metres or centimetres.")
            self._sync_parameter_display(self.current_parameters())
            return False
        return True

    def _configure_radius_spinbox(self) -> None:
        unit = str(self.radius_unit_combo.currentData())
        if unit == "m":
            self.radius_spinbox.setDecimals(3)
            self.radius_spinbox.setSingleStep(0.01)
            self.radius_spinbox.setRange(0.01, 100.0)
        elif unit == "cm":
            self.radius_spinbox.setDecimals(1)
            self.radius_spinbox.setSingleStep(1.0)
            self.radius_spinbox.setRange(0.1, 10000.0)
        else:
            self.radius_spinbox.setDecimals(1)
            self.radius_spinbox.setSingleStep(1.0)
            self.radius_spinbox.setRange(0.1, 5000.0)

    def _format_distance(self, value: float, pixels_per_meter: float | None) -> str:
        if pixels_per_meter:
            return f"{value:.3f} m"
        return f"{value:.2f}px"

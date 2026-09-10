from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
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

from cycloid_analyzer.canvas import CanvasStateRecord, CanvasView, CycloidRecord, MovementTraceRecord
from cycloid_analyzer.commands import AddCycloidCommand, ReplaceCanvasStateCommand, ReplaceMovementTraceCommand, UpdateCycloidCommand
from cycloid_analyzer.comparison import compare_paths
from cycloid_analyzer.cycloid import CycloidParameters
from cycloid_analyzer.image_tools import load_png_pixmap


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
        self.radius_slider = self._build_slider(5, 120, 40)
        self.frequency_slider = self._build_slider(10, 60, 20)
        self.phase_slider = self._build_slider(0, 360, 0)

        self.radius_value = QLabel()
        self.frequency_value = QLabel()
        self.phase_value = QLabel()
        self.selection_label = QLabel("Selected cycloid: none")

        compare_button = QPushButton("Compare selected cycloid to movement trace")
        compare_button.clicked.connect(self.compare_selected_cycloid)

        self.metrics_label = QLabel("Average distance: —\nRMSE: —\nMax distance: —\nLength ratio: —\nSimilarity score: —")
        self.metrics_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        panel = QWidget()
        layout = QVBoxLayout(panel)
        form = QFormLayout()
        form.addRow("Radius", self._labeled_control(self.radius_slider, self.radius_value))
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

        for slider in (self.radius_slider, self.frequency_slider, self.phase_slider):
            slider.sliderPressed.connect(self._begin_parameter_edit)
            slider.valueChanged.connect(self._on_slider_changed)
            slider.sliderReleased.connect(self._commit_parameter_edit)

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
            "trace": "Drag to trace movement. Right-click to finish the current trace.",
            "pan": "Drag the view to pan the image and overlays.",
        }
        self.statusBar().showMessage(messages[mode])

    def _samples_dir(self) -> Path:
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS) / "cycloid_analyzer" / "samples"
        return Path(__file__).resolve().parent / "samples"

    def _labeled_control(self, slider: QSlider, value_label: QLabel) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(slider)
        layout.addWidget(value_label)
        return container

    def _connect_signals(self) -> None:
        self.canvas.cycloid_drawn.connect(self._handle_cycloid_drawn)
        self.canvas.movement_trace_drawn.connect(self._handle_movement_trace_drawn)
        self.canvas.cycloid_selection_changed.connect(self._handle_selection_changed)

    def open_png_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Open PNG image", "", "PNG Images (*.png)")
        if file_path:
            pixmap = self._load_png(file_path)
            if pixmap is not None:
                self._replace_canvas_state(
                    CanvasStateRecord(QPixmap(pixmap), [], None),
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

    def _handle_selection_changed(self, record: CycloidRecord | None) -> None:
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
        self._slider_update_guard = True
        self.radius_slider.setValue(int(round(parameters.radius)))
        self.frequency_slider.setValue(int(round(parameters.frequency * 10)))
        self.phase_slider.setValue(int(round(parameters.phase_degrees)))
        self._slider_update_guard = False
        self._sync_parameter_display(self.current_parameters())

    def _sync_parameter_display(self, parameters: CycloidParameters) -> None:
        self.radius_value.setText(f"{parameters.radius:.0f}px")
        self.frequency_value.setText(f"{parameters.frequency:.1f} turns")
        self.phase_value.setText(f"{parameters.phase_degrees:.0f}°")
        self.canvas.set_current_parameters(parameters)

    def current_parameters(self) -> CycloidParameters:
        return CycloidParameters(
            radius=float(self.radius_slider.value()),
            frequency=float(self.frequency_slider.value()) / 10.0,
            phase_degrees=float(self.phase_slider.value()),
        )

    def _reset_metrics_display(self) -> None:
        self.metrics_label.setText("Average distance: —\nRMSE: —\nMax distance: —\nLength ratio: —\nSimilarity score: —")

    def _sync_ui_to_canvas_state(self) -> None:
        self._handle_selection_changed(self.canvas.selected_cycloid_record())

    def _replace_canvas_state(self, after: CanvasStateRecord, label: str, status_message: str | None = None) -> None:
        before = self.canvas.capture_state()
        self.undo_stack.push(
            ReplaceCanvasStateCommand(
                self.canvas,
                before,
                after,
                label,
                on_applied=self._sync_ui_to_canvas_state,
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
        self.metrics_label.setText(
            "\n".join(
                [
                    f"Average distance: {metrics['average_distance']:.2f}px",
                    f"RMSE: {metrics['rmse']:.2f}px",
                    f"Max distance: {metrics['max_distance']:.2f}px",
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
            CanvasStateRecord(QPixmap(pixmap), [], MovementTraceRecord("movement-trace", points)),
            "Load demo",
            "Bundled demo loaded. Draw or adjust cycloids on top of the sample movement frame.",
        )

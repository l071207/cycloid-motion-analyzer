# Cycloid Motion Analyzer

Cycloid Motion Analyzer is a Windows-friendly PyQt5 desktop application for drawing, editing, and comparing cycloid paths over PNG images of human movement.

## Features

- Load PNG movement images as a zoomable, pannable background
- Draw cycloid paths directly on top of the image with real-time preview
- Adjust cycloid radius, frequency, and phase with live sliders
- Select existing cycloid paths and refine them with live parameter controls
- Trace a movement path from the image and compare it to a selected cycloid
- Undo and redo drawing, trace replacement, and parameter edits
- Load bundled demo assets for a quick first run

## Project structure

- `/cycloid_analyzer/image_tools.py` - PNG validation and loading
- `/cycloid_analyzer/cycloid.py` - cycloid generation math
- `/cycloid_analyzer/comparison.py` - path comparison metrics
- `/cycloid_analyzer/canvas.py` - image/cycloid rendering and interaction
- `/cycloid_analyzer/main_window.py` - menus, tools, parameter panel, and analysis UI
- `/cycloid_analyzer/commands.py` - undo/redo commands
- `/cycloid_analyzer/samples/` - demo PNG and movement trace
- `/tests/` - focused unit tests for math, metrics, and undo commands

## Quick start for Windows development

1. Install Python 3.10 or newer.
2. Open PowerShell in the repository root.
3. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

5. Run the application:

   ```powershell
   python -m cycloid_analyzer
   ```

## Usage

1. Use **File → Open PNG…** to load a movement image, or **File → Load bundled demo**.
2. Choose **Draw Cycloid** and drag on the image to create a cycloid path.
3. Choose **Trace Movement** and draw a freehand trace over the observed motion.
4. Select a cycloid and adjust **Radius**, **Frequency**, and **Phase** in the right panel.
5. Click **Compare selected cycloid to movement trace** to generate metrics.
6. Use **Undo** and **Redo** from the toolbar or Edit menu as needed.

## Comparison metrics

The app currently reports:

- Average point-to-point distance
- Root mean square error (RMSE)
- Maximum point-to-point distance
- Path length ratio
- A simple similarity score derived from average distance

## Building a standalone Windows executable

The repository includes:

- `cycloid_motion_analyzer.spec` for PyInstaller
- `installer.iss` for Inno Setup
- `scripts/build_windows.ps1` to automate both steps

### Build only the executable

```powershell
pyinstaller --noconfirm cycloid_motion_analyzer.spec
```

The app will be created in `dist\CycloidMotionAnalyzer\`.

### Build the installer

1. Install [Inno Setup](https://jrsoftware.org/isinfo.php).
2. Run:

   ```powershell
   .\scripts\build_windows.ps1
   ```

If Inno Setup is installed, the installer will be written to `dist\installer\`.

## Validation

Run the focused tests with:

```powershell
python -m unittest discover -s tests
```

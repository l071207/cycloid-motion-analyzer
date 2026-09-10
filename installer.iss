[Setup]
AppName=Cycloid Motion Analyzer
AppVersion=0.1.0
WizardStyle=modern
DefaultDirName={autopf}\Cycloid Motion Analyzer
DefaultGroupName=Cycloid Motion Analyzer
OutputDir=dist\installer
OutputBaseFilename=CycloidMotionAnalyzerSetup
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\CycloidMotionAnalyzer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Cycloid Motion Analyzer"; Filename: "{app}\CycloidMotionAnalyzer.exe"
Name: "{autodesktop}\Cycloid Motion Analyzer"; Filename: "{app}\CycloidMotionAnalyzer.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\CycloidMotionAnalyzer.exe"; Description: "Launch Cycloid Motion Analyzer"; Flags: nowait postinstall skipifsilent


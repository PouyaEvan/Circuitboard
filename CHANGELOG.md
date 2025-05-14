## [Unreleased]

### Added
- Grid snapping toggle and visual grid drawing on the canvas
- Orthogonal wire routing preview and hover feedback on component pins
- Menubar with File, Edit, View, Analysis (DC and Transient), and Help (Instructions, Changelog)
- Settings dialog for transient analysis with end time and time step inputs
- .gitignore file to ignore Python caches, IDE settings, virtualenvs, logs, and circuit files

### Changed
- Refactored component base class to remove circular imports and streamline pin and wire management
- Improved inductor rendering using precise semicircular arcs
- Restored block-style resistor with gradient fill and amber border
- Refactored wire routing code for orthogonal fallback and dynamic wire updates on component move
- Polished toolbar and properties panel styling and behavior

### Fixed
- Circular imports between config.py and canvas.py on startup
- Item position snapping and grid alignment for component movement

---

## [0.5.0] - 2024-06-01 (BETA)

### Added
- Export simulation results to CSV
- Support for inductors and diodes
- Batch simulation mode

### Changed
- Optimized simulation performance for large circuits

### Fixed
- Fixed crash when parsing empty netlists

---

## [0.2.0] - 2024-05-15 (ALPHA)

### Added
- Graphical visualization of circuit topology
- Support for DC analysis

### Changed
- Improved CLI help messages

### Fixed
- Fixed bug in voltage source handling

---

## [0.1.0] - 2024-05-01 (ALPHA)

### Added
- Initial project setup
- Basic netlist parsing
- Simple resistor network simulation

### Changed
- N/A

### Fixed
- N/A



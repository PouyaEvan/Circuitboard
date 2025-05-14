import os
import json
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QGraphicsScene, QMessageBox,
    QFileDialog, QToolBar, QDialog, QDialogButtonBox, QFormLayout, QInputDialog
)
from PyQt6.QtGui import QKeySequence, QPainter, QAction
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtCore import Qt, QPointF

from gui.canvas import CircuitCanvas
from gui.properties_panel import PropertiesPanel
from gui.dialogs import SettingsDialog, InstructionsDialog
from core.netlist import CircuitNetlist
from core.simulator import CircuitSimulator
from components.wire import Wire
from components.resistor import Resistor
from components.vs import VoltageSource
from components.cs import CurrentSource
from components.inductor import Inductor
from components.capacitor import Capacitor
from components.ground import Ground
from config import Component, GRID_SIZE
from core.simulator import Node
from PyQt6.QtWidgets import QApplication

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Circuit Simulator")
        self.setGeometry(100, 100, 1200, 800) # Increased window size

        self.setStyleSheet("""
            QMainWindow {
                background-color: #f7f9fa;
            }
            QToolBar {
                background-color: #e8eaf0;
                spacing: 8px;
                padding: 8px;
                border-bottom: 1px solid #cfd8dc;
            }
            QToolButton {
                padding: 10px;
                border: 1px solid #b0bec5;
                border-radius: 6px;
                background-color: #ffffff;
                text-align: left;
                min-width: 110px;
                font-size: 15px;
            }
            QToolButton:hover {
                background-color: #e3f2fd;
                border-color: #90caf9;
            }
            QToolButton:checked {
                background-color: #b3e5fc;
            }
            QGraphicsView {
                border: 1px solid #b0bec5;
                background-color: #f5f7fa;
            }
            QMessageBox {
                background-color: #f8f8f8;
                font-family: "Segoe UI";
            }
            QMessageBox QLabel {
                color: #333333;
            }
            QMessageBox QPushButton {
                padding: 6px 18px;
                border: 1px solid #b0bec5;
                border-radius: 5px;
                background-color: #e0e0e0;
            }
            QMessageBox QPushButton:hover {
                background-color: #b3e5fc;
            }
            QMessageBox QPushButton:pressed {
                background-color: #90caf9;
            }
            QDockWidget {
                border: 1px solid #b0bec5;
                titlebar-background-color: #e8eaf0;
            }
            QDockWidget::title {
                text-align: center;
                background-color: #e8eaf0;
                padding: 4px;
            }
            QListWidget {
                border: 1px solid #b0bec5;
                background-color: #ffffff;
            }
            QListWidget::item {
                padding: 7px;
            }
            QListWidget::item:selected {
                background-color: #b3e5fc;
            }
            QFormLayout QLabel {
                font-weight: bold;
            }
            QLineEdit {
                padding: 7px;
                border: 1px solid #b0bec5;
                border-radius: 4px;
            }
            QPushButton {
                padding: 10px;
                border: 1px solid #b0bec5;
                border-radius: 6px;
                background-color: #ffffff;
            }
            QPushButton:hover {
                background-color: #e3f2fd;
            }
            QPushButton:pressed {
                background-color: #b3e5fc;
            }
        """)
        # Initialize application menus
        self.setup_menubar() # Changed from self.init_menus()

        self.component_counters = {"R": 0, "V": 0, "L": 0, "C": 0, "I": 0, "Other": 0, "GND": 0}
        self.used_component_names = {"R": set(), "V": set(), "L": set(), "C": set(), "I": set(), "Other": set(), "GND": set()}

        self._simulation_results_visible = False
        self._clipboard = [] # Added clipboard for copy/paste

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-2000, -1500, 4000, 3000)

        self.canvas = CircuitCanvas(self.scene, self)
        layout.addWidget(self.canvas)

        self.netlist = CircuitNetlist(self.canvas)

        self.properties_panel = PropertiesPanel(self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_panel)

        self.setup_toolbar()
        # self.setup_menubar() # Removed duplicate menubar setup

        self.activate_tool(self.findChild(QAction, "select_action"), None)

        self.simulation_results = None


    def setup_menubar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        new_action = QAction("&New", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.clear_circuit)
        file_menu.addAction(new_action)

        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_circuit)
        file_menu.addAction(open_action)

        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_circuit)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self.save_circuit_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        print_action = QAction("&Print...", self) # Added Print action
        print_action.setShortcut(QKeySequence.StandardKey.Print)
        print_action.triggered.connect(self.print_circuit) # Connect to print_circuit method
        file_menu.addAction(print_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menubar.addMenu("&Edit")

        copy_action = QAction("&Copy", self) # Added Copy action
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.triggered.connect(self.copy_selected_items)
        edit_menu.addAction(copy_action)

        paste_action = QAction("&Paste", self) # Added Paste action
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        paste_action.triggered.connect(self.paste_items)
        edit_menu.addAction(paste_action)


        view_menu = menubar.addMenu("&View")

        zoom_to_fit_action = QAction("&Zoom to Fit", self) # Added Zoom to Fit action
        zoom_to_fit_action.setShortcut(Qt.Key.Key_F)
        zoom_to_fit_action.triggered.connect(self.zoom_to_fit)
        view_menu.addAction(zoom_to_fit_action)

        # Analysis menu with DC and Transient actions
        analysis_menu = menubar.addMenu("&Analysis")
        dc_action = QAction("DC Analysis", self)
        dc_action.triggered.connect(self.start_simulation)
        analysis_menu.addAction(dc_action)
        transient_action = QAction("Transient Analysis", self)
        transient_action.triggered.connect(self.run_transient_analysis)
        analysis_menu.addAction(transient_action)
        # Help menu for Instructions and Changelog
        help_menu = menubar.addMenu("&Help")
        instr_action = QAction("Instructions", self)
        instr_action.triggered.connect(self.show_instructions)
        help_menu.addAction(instr_action)
        changelog_action = QAction("Changelog", self)
        changelog_action.triggered.connect(self.show_changelog)
        help_menu.addAction(changelog_action)


    def setup_toolbar(self):
        toolbar = QToolBar("Tools")
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False); toolbar.setFloatable(False)
        toolbar.setOrientation(Qt.Orientation.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

        select_action = QAction("Select (Esc)", self)
        select_action.setObjectName("select_action")
        select_action.setToolTip("Select items (Esc)"); select_action.setCheckable(True)
        select_action.setShortcut(Qt.Key.Key_Escape)
        select_action.triggered.connect(lambda checked: self.activate_tool(select_action, None) if checked else None)

        resistor_action = QAction("Resistor (R)", self)
        resistor_action.setObjectName("resistor_action")
        resistor_action.setToolTip("Add Resistor (R)"); resistor_action.setCheckable(True)
        resistor_action.setShortcut(Qt.Key.Key_R)
        resistor_action.triggered.connect(lambda checked: self.activate_tool(resistor_action, 'resistor') if checked else None)

        voltage_action = QAction("Voltage Source (V)", self)
        voltage_action.setObjectName("voltage_action")
        voltage_action.setToolTip("Add Voltage Source (V)"); voltage_action.setCheckable(True)
        voltage_action.setShortcut(Qt.Key.Key_V)
        voltage_action.triggered.connect(lambda checked: self.activate_tool(voltage_action, 'voltage') if checked else None)

        current_source_action = QAction("Current Source (I)", self)
        current_source_action.setObjectName("current_source_action")
        current_source_action.setToolTip("Add Current Source (I)"); current_source_action.setCheckable(True)
        current_source_action.setShortcut(Qt.Key.Key_I)
        current_source_action.triggered.connect(lambda checked: self.activate_tool(current_source_action, 'currentsource') if checked else None)

        inductor_action = QAction("Inductor (L)", self)
        inductor_action.setObjectName("inductor_action")
        inductor_action.setToolTip("Add Inductor (L)"); inductor_action.setCheckable(True)
        inductor_action.setShortcut(Qt.Key.Key_L)
        inductor_action.triggered.connect(lambda checked: self.activate_tool(inductor_action, 'inductor') if checked else None)

        ground_action = QAction("Ground (G)", self)
        ground_action.setObjectName("ground_action")
        ground_action.setToolTip("Add Ground (G)"); ground_action.setCheckable(True)
        ground_action.setShortcut(Qt.Key.Key_G)
        ground_action.triggered.connect(lambda checked: self.activate_tool(ground_action, 'ground') if checked else None)

        capacitor_action = QAction("Capacitor (C)", self)
        capacitor_action.setObjectName("capacitor_action")
        capacitor_action.setToolTip("Add Capacitor (C)"); capacitor_action.setCheckable(True)
        capacitor_action.setShortcut(Qt.Key.Key_C)
        capacitor_action.triggered.connect(lambda checked: self.activate_tool(capacitor_action, 'capacitor') if checked else None)

        wire_action = QAction("Wire (W)", self)
        wire_action.setObjectName("wire_action")
        wire_action.setToolTip("Draw Wire (W)"); wire_action.setCheckable(True)
        wire_action.setShortcut(Qt.Key.Key_W)
        wire_action.triggered.connect(lambda checked: self.activate_tool(wire_action, 'wire') if checked else None)

        start_action = QAction("Simulate", self)
        start_action.setObjectName("start_action")
        start_action.setToolTip("Run Simulation")
        start_action.triggered.connect(self.start_simulation)

        plot_action = QAction("Plot Voltages", self)
        plot_action.setObjectName("plot_action")
        plot_action.setToolTip("Plot Node Voltages")
        plot_action.triggered.connect(self.show_voltage_plot)

        netlist_action = QAction("Show Netlist", self)
        netlist_action.setObjectName("netlist_action")
        netlist_action.setToolTip("Show Circuit Netlist")
        netlist_action.triggered.connect(self.show_netlist)

        results_action = QAction("Show Results", self)
        results_action.setObjectName("results_action")
        results_action.setToolTip("Show Simulation Results on Canvas")
        results_action.setCheckable(True)
        results_action.triggered.connect(self.toggle_simulation_results_display)

        snap_action = QAction("Snap to Grid", self)
        snap_action.setObjectName("snap_action")
        snap_action.setToolTip("Toggle Snap to Grid"); snap_action.setCheckable(True)
        snap_action.setChecked(self.canvas.snap_to_grid_enabled)
        snap_action.triggered.connect(self.toggle_snap_to_grid)


        self.tool_actions = [select_action, resistor_action, voltage_action, current_source_action, inductor_action, ground_action, capacitor_action, wire_action]
        self.simulation_actions = [start_action, plot_action]
        self.other_actions = [netlist_action, results_action, snap_action]

        toolbar.addAction(select_action)
        toolbar.addSeparator()
        toolbar.addAction(resistor_action)
        toolbar.addAction(voltage_action)
        toolbar.addAction(current_source_action)
        toolbar.addAction(inductor_action)
        toolbar.addAction(ground_action)
        toolbar.addAction(capacitor_action)
        toolbar.addSeparator()
        toolbar.addAction(wire_action)
        toolbar.addSeparator()
        toolbar.addAction(start_action)
        toolbar.addAction(plot_action)
        toolbar.addSeparator()
        toolbar.addAction(netlist_action)
        toolbar.addSeparator()
        toolbar.addAction(results_action)
        toolbar.addSeparator()
        toolbar.addAction(snap_action)


    def activate_tool(self, triggered_action, tool_name):
        for action in self.tool_actions:
            if action == triggered_action:
                action.setChecked(True)
            elif tool_name is None and action.objectName() == "select_action":
                 action.setChecked(True)
            else:
                action.setChecked(False)

        self.canvas.set_tool(tool_name)

    def get_next_component_name(self, prefix):
        if prefix not in self.component_counters:
            prefix = "Other"

        i = 1
        while f"{prefix}{i}" in self.used_component_names[prefix]:
            i += 1

        name = f"{prefix}{i}"
        self.used_component_names[prefix].add(name)
        self.component_counters[prefix] = max(self.component_counters[prefix], i)
        return name

    def deregister_component_name(self, prefix, name):
        if prefix in self.used_component_names and name in self.used_component_names[prefix]:
            self.used_component_names[prefix].remove(name)

    def register_component_name(self, prefix, name):
        if prefix not in self.used_component_names:
             prefix = "Other"
        self.used_component_names[prefix].add(name)

    def start_simulation(self):
        print("Simulation Started...")
        if not NUMPY_AVAILABLE:
             QMessageBox.warning(self, "Simulation Error", "NumPy is not installed. Simulation cannot run.")
             print("Simulation failed: NumPy not available.")
             return

        simulator = CircuitSimulator(self.netlist)
        result_message = simulator.run_dc_analysis()

        if "Simulation completed." in result_message:
             self.simulation_results = simulator
             results_description = simulator.get_results_description(include_wire_currents=False)
             QMessageBox.information(self, "Simulation Results", results_description)
             print("Simulation successful.")
             print(results_description)

             results_action = self.findChild(QAction, "results_action")
             if results_action and results_action.isChecked():
                  self._simulation_results_visible = True
                  self.display_simulation_results()


        else:
             self.simulation_results = None
             self.hide_simulation_results()
             QMessageBox.warning(self, "Simulation Error", result_message)
             print("Simulation failed.")
             print(result_message)

    def stop_simulation(self):
        print("Simulation Stopped (Placeholder)")
        QMessageBox.information(self, "Simulation", "Simulation Stopped (Placeholder)")

    def restart_simulation(self):
        print("Simulation Restarted (Placeholder)")
        QMessageBox.information(self, "Simulation", "Simulation Restarted (Placeholder)")

    def show_netlist(self):
        netlist_description = self.netlist.generate_netlist_description()
        QMessageBox.information(self, "Circuit Netlist", netlist_description)

    def clear_circuit(self):
        # Clear all items from the scene
        for item in list(self.scene.items()):
            if item and item.scene():
                 self.scene.removeItem(item)

        # Re-initialize netlist and component counters
        self.netlist = CircuitNetlist(self.canvas)
        self.component_counters = {"R": 0, "V": 0, "L": 0, "C": 0, "I": 0, "Other": 0, "GND": 0}
        self.used_component_names = {"R": set(), "V": set(), "L": set(), "C": set(), "I": set(), "Other": set(), "GND": set()}

        # Clear simulation results and hide display
        self.simulation_results = None
        self._simulation_results_visible = False
        results_action = self.findChild(QAction, "results_action")
        if results_action:
             results_action.setChecked(False)

        # Update UI elements
        self.properties_panel.update_component_list()
        self.properties_panel.clear_properties_display()
        self.canvas.update_node_visuals() # Ensure node visuals are cleared


    def open_circuit(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Circuit", "", "Circuit Files (*.circuit);;All Files (*)")
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    circuit_data = json.load(f)
                self.load_circuit_from_dict(circuit_data)
                QMessageBox.information(self, "Open Circuit", f"Circuit loaded from {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.warning(self, "Open Error", f"Could not load circuit: {e}")

    def save_circuit(self):
        if not hasattr(self, '_current_file_path') or not self._current_file_path:
            self.save_circuit_as()
        else:
            try:
                circuit_data = self.save_circuit_to_dict()
                with open(self._current_file_path, 'w') as f:
                    json.dump(circuit_data, f, indent=4)
                QMessageBox.information(self, "Save Circuit", f"Circuit saved to {os.path.basename(self._current_file_path)}")
            except Exception as e:
                QMessageBox.warning(self, "Save Error", f"Could not save circuit: {e}")


    def save_circuit_as(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Circuit As", "", "Circuit Files (*.circuit);;All Files (*)")
        if file_path:
            if not file_path.lower().endswith(".circuit"):
                 file_path += ".circuit"
            self._current_file_path = file_path
            self.save_circuit()

    def save_circuit_to_dict(self):
        circuit_data = {
            "components": [],
            "wires": [],
            "ground_node_id": self.netlist.ground_node_id,
            "component_counters": self.component_counters,
            "used_component_names": {prefix: list(names) for prefix, names in self.used_component_names.items()} # Convert sets to lists for JSON
        }

        for component in self.netlist.components:
            circuit_data["components"].append(component.to_dict())

        for wire in self.netlist.wires:
            circuit_data["wires"].append(wire.to_dict())

        return circuit_data

    def load_circuit_from_dict(self, circuit_data):
        self.clear_circuit() # Start with a clean slate

        # Load component counters and used names first
        self.component_counters = circuit_data.get("component_counters", {"R": 0, "V": 0, "L": 0, "C": 0, "I": 0, "Other": 0, "GND": 0})
        used_names_data = circuit_data.get("used_component_names", {"R": [], "V": [], "L": [], "C": [], "I": [], "Other": [], "GND": []})
        self.used_component_names = {prefix: set(names) for prefix, names in used_names_data.items()} # Convert lists back to sets

        # Create components
        component_map = {} # Map component name to object for wire linking
        for comp_data in circuit_data.get("components", []):
            component = Component.from_dict(comp_data, self.netlist)
            if component:
                self.scene.addItem(component)
                self.netlist.add_component(component) # This adds to netlist.components and updates properties panel
                component_map[component.component_name] = component

        # Create nodes and link pins
        # This needs to be done after components are added but before wires
        # Iterate through components and their pins to create/link nodes
        max_node_id = -1 # Track the maximum node ID encountered
        for component in self.netlist.components:
             for pin_item in component.get_pins():
                  # Check if this pin is already connected to a node (e.g., from a previously processed component)
                  if pin_item.data(3) is None:
                       # Create a new node for this unconnected pin
                       new_node_id = self.netlist._get_next_node_id()
                       new_node = Node(new_node_id)
                       self.netlist.nodes[new_node_id] = new_node
                       new_node.add_pin_connection(component, pin_item.data(1), pin_item)
                       print(f"Created Node {new_node_id} for unconnected pin {component.component_name}.{pin_item.data(1)}")
                       max_node_id = max(max_node_id, new_node_id)
                  else:
                       # Pin is already connected, ensure the node has the correct connection
                       node = pin_item.data(3)
                       node.add_pin_connection(component, pin_item.data(1), pin_item) # Add connection if not already present
                       max_node_id = max(max_node_id, node.node_id)

        # Update the next node ID counter based on loaded nodes
        self.netlist._next_node_id = max_node_id + 1
        print(f"Updated _next_node_id to {self.netlist._next_node_id} after loading.")


        # Create wires
        for wire_data in circuit_data.get("wires", []):
            start_comp_name = wire_data["start_pin"]["component"]
            start_pin_name = wire_data["start_pin"]["pin"]
            end_comp_name = wire_data["end_pin"]["component"]
            end_pin_name = wire_data["end_pin"]["pin"]

            start_comp = component_map.get(start_comp_name)
            end_comp = component_map.get(end_comp_name)

            if start_comp and end_comp:
                start_pin = None
                for pin in start_comp.get_pins():
                    if pin.data(1) == start_pin_name:
                        start_pin = pin
                        break

                end_pin = None
                for pin in end_comp.get_pins():
                    if pin.data(1) == end_pin_name:
                        end_pin = pin
                        break

                if start_pin and end_pin:
                    wire = Wire(start_pin, end_pin)
                    self.scene.addItem(wire)
                    self.netlist.add_wire(wire) # This handles node merging/creation
                    wire.update_positions()
                else:
                    print(f"Warning: Could not find pins for wire between {start_comp_name}.{start_pin_name} and {end_comp_name}.{end_pin_name}")
            else:
                print(f"Warning: Could not find components for wire between {start_comp_name} and {end_comp_name}")

        # Set ground node after all nodes are potentially created/merged
        ground_node_id = circuit_data.get("ground_node_id")
        if ground_node_id is not None and ground_node_id in self.netlist.nodes:
             self.netlist.set_ground_node(ground_node_id)
        elif ground_node_id is not None:
             print(f"Warning: Saved ground node ID {ground_node_id} not found in loaded nodes.")


        self.canvas.update_node_visuals() # Update node visuals after loading

    def toggle_simulation_results_display(self, checked):
        self._simulation_results_visible = checked
        if checked:
            if self.simulation_results:
                self.display_simulation_results()
            else:
                QMessageBox.information(self, "Show Results", "No simulation results to display. Run simulation first.")
                results_action = self.findChild(QAction, "results_action")
                if results_action:
                     results_action.setChecked(False)
                     self._simulation_results_visible = False
        else:
            self.hide_simulation_results()

    def display_simulation_results(self):
        if not self.simulation_results or not self._simulation_results_visible:
            return

        print("Displaying simulation results on canvas...")

        def format_voltage(val):
            abs_val = abs(val)
            if abs_val >= 1:
                return f"{val:.2f} V"
            elif abs_val >= 1e-3:
                return f"{val*1e3:.2f} mV"
            elif abs_val >= 1e-6:
                return f"{val*1e6:.2f} μV"
            else:
                return f"{val:.2e} V"

        for node_id, node in self.netlist.nodes.items():
            voltage = self.simulation_results.get_node_voltage(node_id)
            if voltage is not None and node.voltage_text_item:
                node.voltage_text_item.setPlainText(format_voltage(voltage))
                node.voltage_text_item.setVisible(True)

        for component in self.netlist.components:
             if isinstance(component, (Resistor, VoltageSource, CurrentSource, Inductor, Capacitor)):
                  if isinstance(component, Resistor):
                       current_label = "Current (in to out)"
                  elif isinstance(component, VoltageSource):
                       current_label = "Current (out of +)"
                  elif isinstance(component, CurrentSource):
                       current_label = "Current (out of +)"
                  elif isinstance(component, Inductor):
                       current_label = "Current (in to out)"
                  elif isinstance(component, Capacitor):
                       current_label = "Current"
                  else:
                       continue

                  current_value = self.simulation_results.get_component_current(component, current_label)
                  if current_value is not None:
                       component.display_current(current_value)

    def hide_simulation_results(self):
        print("Hiding simulation results on canvas...")

        for node_id, node in self.netlist.nodes.items():
            if node.voltage_text_item:
                node.voltage_text_item.setVisible(False)

        for component in self.netlist.components:
             component.hide_current_display()

    def toggle_snap_to_grid(self, checked):
        """Toggles the snap-to-grid feature."""
        self.canvas.snap_to_grid_enabled = checked
        self.canvas.scene().update() # Redraw scene to show/hide grid


    def zoom_to_fit(self):
        """Zooms the canvas to fit all items in the scene."""
        if not self.scene.items():
            return

        # Get the bounding rectangle of all items
        rect = self.scene.itemsBoundingRect()
        if rect.isNull():
            return

        # Add some padding
        padding = 50
        rect.adjust(-padding, -padding, padding, padding)

        # Fit the view to the rectangle
        self.canvas.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)


    def copy_selected_items(self):
        """Copies the selected components and wires to the clipboard."""
        selected_items = self.scene().selectedItems()
        self._clipboard = []

        # Copy components first
        component_copies = {} # Map original component to its copied data
        for item in selected_items:
            if isinstance(item, Component):
                 comp_data = item.to_dict()
                 self._clipboard.append({"type": "component", "data": comp_data})
                 component_copies[item] = comp_data # Store reference to copied data

        # Copy wires, linking them to the copied components
        for item in selected_items:
            if isinstance(item, Wire):
                 # Check if both connected components were also copied
                 if item.start_comp in component_copies and item.end_comp in component_copies:
                      wire_data = item.to_dict()
                      self._clipboard.append({"type": "wire", "data": wire_data})
                 else:
                      print(f"Skipping wire copy: Connected components not selected for wire {item}")

        print(f"Copied {len(self._clipboard)} items to clipboard.")


    def paste_items(self):
        """Pasts items from the clipboard to the scene."""
        if not self._clipboard:
            print("Clipboard is empty.")
            return

        # Create a mapping from original component names in clipboard data to new component objects
        copied_name_to_new_comp = {}
        new_items = []
        paste_offset = QPointF(GRID_SIZE * 2, GRID_SIZE * 2) # Offset for pasted items

        # Create components first
        for item_data in self._clipboard:
            if item_data["type"] == "component":
                 comp_data = item_data["data"]
                 original_name = comp_data["name"]
                 comp_type = comp_data["type"]
                 original_pos = QPointF(comp_data["position"]["x"], comp_data["position"]["y"])

                 # Generate a new unique name for the pasted component
                 new_name = self.get_next_component_name(comp_type[0])
                 comp_data["name"] = new_name # Update name in copied data

                 # Create the new component instance
                 new_component = Component.from_dict(comp_data, self.netlist)
                 if new_component:
                      # Offset the position
                      new_component.setPos(original_pos + paste_offset)
                      self.scene.addItem(new_component)
                      self.netlist.add_component(new_component) # Add to netlist
                      new_items.append(new_component)
                      copied_name_to_new_comp[original_name] = new_component

        # Create wires, linking them to the newly created components
        for item_data in self._clipboard:
            if item_data["type"] == "wire":
                 wire_data = item_data["data"]
                 start_comp_name = wire_data["start_pin"]["component"]
                 start_pin_name = wire_data["start_pin"]["pin"]
                 end_comp_name = wire_data["end_pin"]["component"]
                 end_pin_name = wire_data["end_pin"]["pin"]

                 # Find the new component objects based on the original names
                 new_start_comp = copied_name_to_new_comp.get(start_comp_name)
                 new_end_comp = copied_name_to_new_comp.get(end_comp_name)

                 if new_start_comp and new_end_comp:
                      # Find the corresponding pins on the new components
                      new_start_pin = None
                      for pin in new_start_comp.get_pins():
                           if pin.data(1) == start_pin_name:
                                new_start_pin = pin
                                break

                      new_end_pin = None
                      for pin in new_end_comp.get_pins():
                           if pin.data(1) == end_pin_name:
                                new_end_pin = pin
                                break

                      if new_start_pin and new_end_pin:
                           new_wire = Wire(new_start_pin, new_end_pin)
                           self.scene.addItem(new_wire)
                           self.netlist.add_wire(new_wire) # Add to netlist
                           new_wire.update_positions()
                           new_items.append(new_wire)
                      else:
                           print(f"Warning: Could not find pins for pasted wire between {start_comp_name}.{start_pin_name} and {end_comp_name}.{end_pin_name}")
                 else:
                      print(f"Warning: Could not find components for pasted wire between {start_comp_name} and {end_comp_name}")

        # Select the newly pasted items
        self.scene.clearSelection()
        for item in new_items:
             item.setSelected(True)

        self.canvas.update_node_visuals() # Update node visuals after pasting
        if hasattr(self, 'hide_simulation_results'):
             self.hide_simulation_results()


    def show_voltage_plot(self):
        if not MATPLOTLIB_AVAILABLE:
            QMessageBox.warning(self, "Plotting Error", "Matplotlib is not installed. Plotting cannot run.")
            print("Plotting failed: Matplotlib not available.")
            return

        if not self.simulation_results or not self.simulation_results.node_voltages:
            QMessageBox.information(self, "Plot Voltages", "No simulation results available to plot. Run simulation first.")
            return

        print("Plotting node voltages...")
        print(f"Node voltages data: {self.simulation_results.node_voltages}")

        nodes_to_plot = {node_id: voltage for node_id, voltage in self.simulation_results.node_voltages.items()}
        ground_node = self.netlist.get_ground_node()
        if ground_node and ground_node.node_id in nodes_to_plot and abs(nodes_to_plot[ground_node.node_id]) < 1e-9:
             node_obj = self.netlist.nodes.get(ground_node.node_id)
             if node_obj and any(isinstance(comp, Ground) for comp, pin_name, pin_item in node_obj.connected_pins):
                  pass
             elif node_obj and len(node_obj.connected_pins) == 0:
                  print(f"Excluding isolated Node {ground_node.node_id} from plot.")
                  del nodes_to_plot[ground_node.node_id]
             elif node_obj and len(node_obj.connected_pins) > 0 and all(abs(v) < 1e-9 for v in nodes_to_plot.values()):
                  pass

        if not nodes_to_plot:
             QMessageBox.information(self, "Plot Voltages", "No non-ground nodes with voltage results to plot.")
             print("No non-ground nodes with voltage results to plot.")
             return

        node_ids = sorted(nodes_to_plot.keys())
        voltages = [nodes_to_plot[node_id] for node_id in node_ids]
        node_labels = [f"Node {node_id}" for node_id in node_ids]

        print(f"Node IDs for plot: {node_ids}")
        print(f"Voltages for plot: {voltages}")
        print(f"Node labels for plot: {node_labels}")

        plt.style.use('seaborn-v0_8-whitegrid')
        plt.figure(figsize=(12, 7))
        bars = plt.bar(node_labels, voltages, color='teal')

        plt.ylabel("Voltage (V)", fontsize=12)
        plt.title("Node Voltages", fontsize=14)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2.0, yval, f'{yval:.2f}V', va='bottom', ha='center', fontsize=9)

        plt.show()
        print("Voltage plot displayed.")


    def print_circuit(self):
        """Prints the current circuit scene."""
        printer = QPrinter()
        print_dialog = QPrintDialog(printer, self)

        if print_dialog.exec() == QPrintDialog.DialogCode.Accepted:
            painter = QPainter(printer)
            # Get the bounding rectangle of all items in the scene
            scene_rect = self.scene.itemsBoundingRect()
            if scene_rect.isNull():
                QMessageBox.information(self, "Print", "No items to print.")
                return

            # Add some margin around the circuit
            margin = 50
            scene_rect.adjust(-margin, -margin, margin, margin)

            # Calculate scaling factor to fit the scene into the printer's page
            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            x_scale = page_rect.width() / scene_rect.width()
            y_scale = page_rect.height() / scene_rect.height()
            scale = min(x_scale, y_scale) # Use the smaller scale to maintain aspect ratio

            # Center the scene on the page
            scene_center = scene_rect.center()
            page_center = page_rect.center()
            offset = page_center - scene_center * scale

            # Apply transformation for scaling and centering
            painter.translate(offset.x(), offset.y())
            painter.scale(scale, scale)
            painter.translate(-scene_center.x(), -scene_center.y())

            # Render the scene to the painter
            self.scene.render(painter, scene_rect, scene_rect)

            painter.end()
            print("Circuit printed.")
        else:
            print("Print cancelled.")

    def run_transient_analysis(self):
        # Prompt for simulation settings
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            t_end, t_step = dlg.time_end, dlg.time_step
            simulator = self.netlist_simulator
            # Show progress dialog
            from PyQt6.QtWidgets import QProgressDialog
            progress = QProgressDialog('Simulating transient...', 'Cancel', 0, 100, self)
            progress.setWindowTitle('Transient Analysis')
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            def update_progress(val):
                progress.setValue(val)
                QApplication.processEvents()
                if progress.wasCanceled():
                    raise InterruptedError('Simulation canceled')
            try:
                results = simulator.simulate_transient(t_end, t_step, update_progress)
                progress.setValue(100)
                if MATPLOTLIB_AVAILABLE:
                    import matplotlib.pyplot as plt
                    plt.figure()
                    plt.plot(results['time'], results['voltage'])
                    plt.title('Transient Response')
                    plt.xlabel('Time (s)')
                    plt.ylabel('Voltage (V)')
                    plt.show()
                else:
                    QMessageBox.warning(self, 'Simulation', 'Matplotlib not available.')
            except InterruptedError:
                QMessageBox.information(self, 'Simulation', 'Transient simulation canceled.')

    def show_instructions(self):
        dlg = InstructionsDialog(self)
        dlg.exec()

    def show_changelog(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle('Changelog')
        dlg.resize(700, 500)
        layout = QVBoxLayout(dlg)
        text_edit = QTextEdit(dlg)
        text_edit.setReadOnly(True)
        text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        try:
            with open('CHANGELOG.md', 'r') as f:
                changelog = f.read()
        except Exception as e:
            changelog = f"Could not load changelog: {e}"
        text_edit.setPlainText(changelog)
        layout.addWidget(text_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        dlg.exec()

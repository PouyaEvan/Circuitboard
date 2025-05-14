import sys
import os
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QToolBar, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
                             QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsTextItem,
                             QGraphicsItemGroup, QMenu, QInputDialog, QMessageBox,
                             QGraphicsPathItem, QFileDialog, QDockWidget, QListWidget,
                             QLabel, QLineEdit, QFormLayout, QPushButton, QCheckBox,
                             QDialog, QDialogButtonBox, QDoubleSpinBox, QTextEdit)
from PyQt6.QtGui import (QAction, QIcon, QPainter, QPen, QBrush, QColor, QFont,
                         QTransform, QFontMetrics, QPainterPath, QKeySequence)
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtCore import (Qt, QPointF, QRectF, QLineF, QByteArray, QDataStream,
                          QIODevice)

from gui.canvas import CircuitCanvas

from config import *

from components.wire import Wire
from components.capacitor import Capacitor
from components.ground import Ground
from components.inductor import Inductor
from components.resistor import Resistor
from components.vs import VoltageSource
from components.cs import CurrentSource
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("Warning: NumPy not found. Simulation features will be disabled. Please install NumPy (`pip install numpy`).")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: Matplotlib not found. Plotting features will be disabled. Please install Matplotlib (`pip install matplotlib`).")



class Node:
    def __init__(self, node_id):
        self.node_id = node_id
        self.connected_pins = []
        self.voltage_text_item = None
        self.is_ground = False
        self.junction_item = None # Visual item for the junction dot


    def add_pin_connection(self, component, pin_name, pin_item):
        connection = (component, pin_name, pin_item)
        if connection not in self.connected_pins:
            self.connected_pins.append(connection)
            pin_item.setData(3, self)

    def remove_pin_connection(self, component, pin_name):
        connection_to_remove = None
        for comp, name, item in self.connected_pins:
            if comp == component and name == pin_name:
                connection_to_remove = (comp, name, item)
                break

        if connection_to_remove:
            self.connected_pins.remove(connection_to_remove)
            pass


    def __repr__(self):
        return f"Node({self.node_id}, Connections: {len(self.connected_pins)}, Ground: {self.is_ground})"

class CircuitNetlist:
    def __init__(self, canvas):
        self.canvas = canvas
        self.nodes = {}
        self.components = []
        self.wires = []

        self._next_node_id = 0
        self.ground_node_id = None

        self.node_visuals = {}
        self.junction_visuals = {} # Dictionary for junction dots

    def get_node_at_pos(self, scene_pos, tolerance=GRID_SIZE/2):
        return None

    def add_component(self, component):
        self.components.append(component)
        if isinstance(component, Ground):
             ground_pin = component.get_pins()[0]
             connected_node = ground_pin.data(3)
             if connected_node:
                  self.set_ground_node(connected_node.node_id)
             else:
                  print(f"Warning: Ground component {component.component_name} is not connected to a node.")

        if self.canvas and hasattr(self.canvas.main_window, 'hide_simulation_results'):
             self.canvas.main_window.hide_simulation_results()
        if self.canvas:
             self.canvas.main_window.properties_panel.update_component_list()


    def remove_component(self, component):
        if component in self.components:
            self.components.remove(component)
            nodes_to_clean = set()
            for pin_item in component.get_pins():
                 node = pin_item.data(3)
                 if node and node in self.nodes.values():
                      node.remove_pin_connection(component, pin_item.data(1))
                      if not node.connected_pins and (self.ground_node_id is None or node.node_id != self.ground_node_id):
                           print(f"Removing empty node: {node.node_id}")
                           del self.nodes[node.node_id]
                      pin_item.setData(3, None)

            if isinstance(component, Ground):
                 connected_node = component.get_pins()[0].data(3)
                 if connected_node and connected_node.node_id == self.ground_node_id:
                      other_grounds_on_node = [c for c in self.components if isinstance(c, Ground) and c != component and c.get_pins()[0].data(3) == connected_node]
                      if not other_grounds_on_node:
                           self.set_ground_node(None)


            if self.canvas and hasattr(self.canvas.main_window, 'hide_simulation_results'):
                 self.canvas.main_window.hide_simulation_results()
            if self.canvas:
                 self.canvas.main_window.properties_panel.update_component_list()


    def add_wire(self, wire):
        self.wires.append(wire)

        start_pin = wire.start_pin
        end_pin = wire.end_pin

        start_node = start_pin.data(3)
        end_node = end_pin.data(3)

        start_comp = start_pin.data(2)
        end_comp = end_pin.data(2)
        start_pin_name = start_pin.data(1)
        end_pin_name = end_pin.data(1)

        print(f"Attempting to add wire between {start_comp.component_name} ({start_pin_name}) [Node: {start_node.node_id if start_node else 'None'}] and {end_comp.component_name} ({end_pin_name}) [Node: {end_node.node_id if end_node else 'None'}]")


        if start_node is None and end_node is None:
            new_node_id = self._get_next_node_id()
            new_node = Node(new_node_id)
            self.nodes[new_node_id] = new_node
            new_node.add_pin_connection(start_comp, start_pin_name, start_pin)
            new_node.add_pin_connection(end_comp, end_pin_name, end_pin)
            print(f"Created new node {new_node_id} for wire.")


        elif start_node is None and end_node is not None:
            end_node.add_pin_connection(start_comp, start_pin_name, start_pin)
            print(f"Added start pin ({start_comp.component_name} {start_pin_name}) to existing node {end_node.node_id}.")


        elif start_node is not None and end_node is None:
            start_node.add_pin_connection(end_comp, end_pin_name, end_pin)
            print(f"Added end pin ({end_comp.component_name} {end_pin_name}) to existing node {start_node.node_id}.")


        elif start_node is not None and end_node is not None and start_node != end_node:
             print(f"Wire connecting two existing nodes ({start_node.node_id} and {end_node.node_id}). Merging nodes.")
             if start_node.node_id == self.ground_node_id:
                  target_node = start_node
                  merged_node = end_node
             elif end_node.node_id == self.ground_node_id:
                  target_node = end_node
                  merged_node = start_node
             elif len(start_node.connected_pins) >= len(end_node.connected_pins):
                  target_node = start_node
                  merged_node = end_node
             else:
                  target_node = end_node
                  merged_node = start_node

             for comp, pin_name, pin_item in list(merged_node.connected_pins):
                  target_node.add_pin_connection(comp, pin_name, pin_item)

             if merged_node.node_id in self.nodes and merged_node.node_id != self.ground_node_id:
                 del self.nodes[merged_node.node_id]
                 print(f"Removed merged node: {merged_node.node_id}")


        elif start_node is not None and end_node is not None and start_node == end_node:
             print(f"Wire creating a loop within node {start_node.node_id}.")
             pass

        print("Current Nodes in Netlist:")
        for node_id, node in self.nodes.items():
            print(f"  Node {node_id}: Pins: {[f'{c.component_name}.{pn}' for c, pn, pi in node.connected_pins]}")

        if self.canvas:
            self.canvas.update_node_visuals()

        if self.canvas and hasattr(self.canvas.main_window, 'hide_simulation_results'):
             self.canvas.main_window.hide_simulation_results()
        if self.canvas:
             self.canvas.main_window.properties_panel.update_component_list()


    def remove_wire(self, wire):
        print(f"Attempting to remove wire object: {wire}")
        if wire not in self.wires:
            print("Attempted to remove wire not in netlist. Skipping.")
            return

        print(f"Wire found in netlist. Removing wire between {wire.start_comp.component_name if wire.start_comp else 'Unknown'} ({wire.start_pin.data(1) if wire.start_pin else 'Unknown'}) and {wire.end_comp.component_name if wire.end_comp else 'Unknown'} ({wire.end_pin.data(1) if wire.end_pin else 'Unknown'})")

        self.wires.remove(wire)
        print("Wire removed from netlist.wires list.")

        start_pin = wire.start_pin
        end_pin = wire.end_pin

        start_node = start_pin.data(3) if start_pin else None
        end_node = end_pin.data(3) if end_pin else None

        start_comp = wire.start_comp
        end_comp = wire.end_comp
        start_pin_name = start_pin.data(1) if start_pin else None
        end_pin_name = end_pin.data(1) if end_pin else None

        nodes_to_check = set()
        if start_node: nodes_to_check.add(start_node)
        if end_node and end_node != start_node:
            nodes_to_check.add(end_node)

        print(f"Checking nodes for pin connections to remove: {[n.node_id for n in nodes_to_check]}")

        for node in nodes_to_check:
            connections_to_remove = []
            for comp, pin_name, pin_item in node.connected_pins:
                 if (comp == start_comp and pin_name == start_pin_name and pin_item == start_pin) or \
                    (comp == end_comp and pin_name == end_pin_name and pin_item == end_pin):
                     connections_to_remove.append((comp, pin_name, pin_item))

            for connection in connections_to_remove:
                 node.connected_pins.remove(connection)
                 connection[2].setData(3, None)
                 print(f"Removed pin connection {connection[0].component_name}.{connection[1]} from Node {node.node_id}")

            if node.node_id in self.nodes and not node.connected_pins and (self.ground_node_id is None or node.node_id != self.ground_node_id):
                print(f"Removing empty node: {node.node_id}")
                del self.nodes[node.node_id]

        if wire.start_comp: wire.start_comp.remove_connected_wire(self)
        if wire.end_comp: wire.end_comp.remove_connected_wire(self)

        scene = wire.scene()
        if scene:
             print(f"Removing wire item from scene: {wire}")
             scene.removeItem(wire)
             print("Wire item removed from scene.")
        else:
             print("Wire has no scene, cannot remove item.")

        print("Current Nodes in Netlist after wire removal:")
        for node_id, node in self.nodes.items():
            print(f"  Node {node_id}: Pins: {[f'{c.component_name}.{pn}' for c, pn, pi in node.connected_pins]}")

        if self.canvas:
            self.canvas.update_node_visuals()

        if self.canvas and hasattr(self.canvas.main_window, 'hide_simulation_results'):
             self.canvas.main_window.hide_simulation_results()
        if self.canvas:
             self.canvas.main_window.properties_panel.update_component_list()


    def _get_next_node_id(self):
        node_id = self._next_node_id
        self._next_node_id += 1
        return node_id

    def set_ground_node(self, node_id):
        if node_id is not None and node_id not in self.nodes:
             print(f"Warning: Attempted to set non-existent node {node_id} as ground.")
             return

        if self.ground_node_id is not None and self.ground_node_id in self.nodes:
             self.nodes[self.ground_node_id].is_ground = False

        self.ground_node_id = node_id

        if node_id is not None and node_id in self.nodes:
             self.nodes[node_id].is_ground = True

        print(f"Ground node set to: {self.ground_node_id}")

        if self.canvas:
            self.canvas.update_node_visuals()
        if self.canvas and hasattr(self.canvas.main_window, 'hide_simulation_results'):
             self.canvas.main_window.hide_simulation_results()


    def get_ground_node(self):
        if self.ground_node_id is not None and self.ground_node_id in self.nodes:
            return self.nodes[self.ground_node_id]
        return None

    def find_automatic_ground_node_id(self):
        if not self.nodes:
            return None
        most_connected_node = None
        max_connections = -1
        for node_id, node in self.nodes.items():
            if len(node.connected_pins) > max_connections:
                max_connections = len(node.connected_pins)
                most_connected_node = node_id
        return most_connected_node


    def generate_netlist_description(self):
        description = "Circuit Netlist:\n"
        description += "Components:\n"
        for comp in self.components:
            description += f"  {comp.component_name} ({comp.component_type})\n"

        description += "\nNodes:\n"
        sorted_node_ids = sorted(self.nodes.keys())
        for node_id in sorted_node_ids:
            node = self.nodes[node_id]
            description += f"  Node {node_id} {'(Ground)' if node.is_ground else ''}:\n"
            for comp, pin, pin_item in node.connected_pins:
                description += f"    - {comp.component_name} Pin: {pin}\n"

        description += "\nComponent Pin Connections:\n"
        for comp in self.components:
             description += f"  {comp.component_name}:\n"
             for pin_item in comp.get_pins():
                  pin_name = pin_item.data(1) if pin_item.data(1) else "Unnamed Pin"
                  node = pin_item.data(3)
                  node_id = node.node_id if node else "Not Connected"
                  description += f"    - {pin_name}: Node {node_id}\n"

        description += "\nWires:\n"
        if self.wires:
             for wire in self.wires:
                  start_comp_name = wire.start_comp.component_name if wire.start_comp else "Unknown"
                  start_pin_name = wire.start_pin.data(1) if wire.start_pin else "Unknown"
                  end_comp_name = wire.end_comp.component_name if wire.end_comp else "Unknown"
                  end_pin_name = wire.end_pin.data(1) if wire.end_pin else "Unknown"
                  description += f"  - {start_comp_name} ({start_pin_name}) to {end_comp_name} ({end_pin_name})\n"
        else:
             description += "  No wires in circuit.\n"


        return description

class CircuitSimulator:
    def __init__(self, netlist):
        if not NUMPY_AVAILABLE:
            print("NumPy not available, simulation cannot run.")
            self.netlist = None
            self.node_voltages = {}
            self.component_currents = {}
            self.wire_currents = {}
        else:
            self.netlist = netlist
            self.node_voltages = {}
            self.component_currents = {}
            self.wire_currents = {}


    def run_dc_analysis(self):
        if not self.netlist or not NUMPY_AVAILABLE:
            self.node_voltages = {}
            self.component_currents = {}
            self.wire_currents = {}
            return "Simulation requires a netlist and NumPy."

        # --- Simulation Setup ---
        # Ensure a ground node exists. If not, try to find a suitable one.
        ground_node = self.netlist.get_ground_node()
        auto_ground_warning = ""
        if ground_node is None:
             auto_ground_id = self.netlist.find_automatic_ground_node_id()
             if auto_ground_id is not None and auto_ground_id in self.netlist.nodes:
                  ground_node = self.netlist.nodes[auto_ground_id]
                  print(f"No explicit ground node found. Automatically setting Node {auto_ground_id} as ground for simulation.")
                  ground_node.is_ground = True # Temporarily set as ground for simulation
                  auto_ground_warning = f"Warning: No explicit ground component found. Node {auto_ground_id} was automatically set as ground."
             else:
                  # No nodes or no suitable node to auto-ground
                  self.node_voltages = {}
                  self.component_currents = {}
                  self.wire_currents = {}
                  return "Simulation failed: No ground node found and could not automatically determine one."

        # Identify unknown nodes (all nodes except the ground node)
        nodes = list(self.netlist.nodes.values())
        unknown_nodes = [node for node in nodes if not node.is_ground]
        num_unknown_nodes = len(unknown_nodes)

        # Identify components that introduce unknown currents (Voltage Sources, Inductors in DC)
        voltage_sources = [comp for comp in self.netlist.components if isinstance(comp, VoltageSource)]
        inductors = [comp for comp in self.netlist.components if isinstance(comp, Inductor)]
        num_voltage_sources = len(voltage_sources)
        num_inductors = len(inductors)

        # Total number of variables in the MNA matrix: unknown node voltages + unknown branch currents (Vs, L)
        num_variables = num_unknown_nodes + num_voltage_sources + num_inductors

        # Handle trivial cases (empty circuit or only ground)
        if num_variables == 0:
             self.node_voltages = {ground_node.node_id: 0.0} if ground_node else {}
             self.component_currents = {}
             self.wire_currents = {}
             # Revert temporary ground setting if it was auto-assigned
             if ground_node and auto_ground_warning:
                  ground_node.is_ground = False
             return "Simulation completed." + (" " + auto_ground_warning if auto_ground_warning else "")


        # Create mappings from node/component objects to matrix indices
        node_id_to_matrix_index = {node.node_id: i for i, node in enumerate(unknown_nodes)}
        voltage_source_to_matrix_index = {vs: num_unknown_nodes + i for i, vs in enumerate(voltage_sources)}
        inductor_to_matrix_index = {ind: num_unknown_nodes + num_voltage_sources + i for i, ind in enumerate(inductors)}

        # Initialize MNA matrix (A) and right-hand side vector (B)
        A = np.zeros((num_variables, num_variables))
        B = np.zeros(num_variables)

        # --- Populate MNA Matrix and Vector ---
        for component in self.netlist.components:
            if isinstance(component, Resistor):
                resistance = component.resistance
                if resistance == 0:
                    # Handle zero resistance - treat as a short circuit, may lead to singular matrix if in series with Vs
                    print(f"Warning: Resistor {component.component_name} has zero resistance. Treating as a short.")
                    continue # Skip adding conductance to matrix for R=0

                conductance = 1.0 / resistance

                pin_in = None
                pin_out = None
                for pin in component.get_pins():
                    if pin.data(1) == "in": pin_in = pin
                    elif pin.data(1) == "out": pin_out = pin

                if pin_in and pin_out:
                    node_in = pin_in.data(3)
                    node_out = pin_out.data(3)

                    if node_in and node_out:
                        node_in_id = node_in.node_id
                        node_out_id = node_out.node_id

                        index_in = node_id_to_matrix_index.get(node_in_id, -1) # -1 if ground node
                        index_out = node_id_to_matrix_index.get(node_out_id, -1) # -1 if ground node

                        # Add conductance stamps to the A matrix
                        if not node_in.is_ground:
                             A[index_in, index_in] += conductance
                             if not node_out.is_ground:
                                  A[index_in, index_out] -= conductance

                        if not node_out.is_ground:
                             A[index_out, index_out] += conductance
                             if not node_in.is_ground:
                                  A[index_out, index_in] -= conductance


            elif isinstance(component, VoltageSource):
                voltage = component.voltage
                vs_index = voltage_source_to_matrix_index[component]

                pin_pos = None
                pin_neg = None
                for pin in component.get_pins():
                    if pin.data(1) == "+": pin_pos = pin
                    elif pin.data(1) == "-": pin_neg = pin

                if pin_pos and pin_neg:
                    node_pos = pin_pos.data(3)
                    node_neg = pin_neg.data(3)

                    if node_pos and node_neg:
                        node_pos_id = node_pos.node_id
                        node_neg_id = node_neg.node_id

                        index_pos = node_id_to_matrix_index.get(node_pos_id, -1)
                        index_neg = node_id_to_matrix_index.get(node_neg_id, -1)

                        # Voltage source constraint: V_pos - V_neg = Voltage
                        constraint_row = vs_index

                        if not node_pos.is_ground:
                            A[constraint_row, index_pos] += 1
                            # Add mutual term for current variable (current flows out of + into the node)
                            A[index_pos, constraint_row] += 1 # Corrected sign

                        if not node_neg.is_ground:
                            A[constraint_row, index_neg] -= 1
                            # Add mutual term for current variable (current flows out of + away from the node)
                            A[index_neg, constraint_row] -= 1 # Corrected sign

                        B[constraint_row] = voltage

            elif isinstance(component, CurrentSource):
                current = component.current

                pin_pos = None
                pin_neg = None
                for pin in component.get_pins():
                    if pin.data(1) == "+": pin_pos = pin
                    elif pin.data(1) == "-": pin_neg = pin

                if pin_pos and pin_neg:
                    node_pos = pin_pos.data(3)
                    node_neg = pin_neg.data(3)

                    if node_pos and node_neg:
                        node_pos_id = node_pos.node_id
                        node_neg_id = node_neg.node_id

                        index_pos = node_id_to_matrix_index.get(node_pos_id, -1)
                        index_neg = node_id_to_matrix_index.get(node_neg_id, -1)

                        # Add current source contribution to the B vector
                        if not node_pos.is_ground:
                            B[index_pos] -= current # Current flows out of the positive terminal

                        if not node_neg.is_ground:
                            B[index_neg] += current # Current flows into the negative terminal

            elif isinstance(component, Inductor):
                 # In DC analysis, an inductor is treated as a short circuit.
                 # It introduces an unknown current variable.
                 pin_in = None
                 pin_out = None
                 for pin in component.get_pins():
                      if pin.data(1) == "in": pin_in = pin
                      elif pin.data(1) == "out": pin_out = pin

                 if pin_in and pin_out:
                      node_in = pin_in.data(3)
                      node_out = pin_out.data(3)

                      if node_in and node_out:
                           node_in_id = node_in.node_id
                           node_out_id = node_out.node_id

                           index_in = node_id_to_matrix_index.get(node_in_id, -1)
                           index_out = node_id_to_matrix_index.get(node_out_id, -1)

                           inductor_index = inductor_to_matrix_index[component] # Index for the inductor's current variable

                           # Inductor constraint (V_in - V_out = 0) and current contribution
                           constraint_row = inductor_index

                           if not node_in.is_ground:
                                A[constraint_row, index_in] += 1 # V_in term
                                # Add mutual term for current variable (current flows into node_in)
                                A[index_in, constraint_row] += 1

                           if not node_out.is_ground:
                                A[constraint_row, index_out] -= 1 # -V_out term
                                # Add mutual term for current variable (current flows out of node_out)
                                A[index_out, constraint_row] -= 1

                           B[constraint_row] = 0 # Right side of the voltage constraint is 0

            elif isinstance(component, Capacitor):
                 # In DC analysis, a capacitor is treated as an open circuit.
                 # It does not contribute to the MNA matrix in DC.
                 pass

        # --- Solve the System ---
        try:
            # Check for singular matrix before solving
            if num_variables > 0 and np.linalg.matrix_rank(A) < num_variables:
                 singular_hint = "Simulation failed: Circuit matrix is singular. This usually means:\n"
                 singular_hint += "- Some components or nodes are not connected to the ground node.\n"
                 singular_hint += "- There is a loop containing only voltage sources and/or inductors.\n"
                 singular_hint += "- There is a cut set containing only current sources.\n"
                 singular_hint += "- Check for components with zero resistance or floating nodes/sub-circuits."

                 # Attempt to identify potentially unconnected components
                 unconnected_components = [comp for comp in self.netlist.components if all(pin.data(3) is None or pin.data(3).node_id not in self.netlist.nodes for pin in comp.get_pins())]
                 if unconnected_components:
                      singular_hint += "\nPotential Issue: The following components appear unconnected or not properly linked to the main circuit:\n"
                      for comp in unconnected_components:
                           singular_hint += f"- {comp.component_name}\n"

                 print(f"Linear algebra error during simulation: Singular matrix.")
                 self.node_voltages = {}
                 self.component_currents = {}
                 self.wire_currents = {}
                 # Revert temporary ground setting if it was auto-assigned
                 if ground_node and auto_ground_warning:
                       ground_node.is_ground = False
                 return singular_hint

            # Solve the linear system Ax = B
            solution = np.linalg.solve(A, B)

            # --- Extract Results ---
            # Extract node voltages
            for i, node in enumerate(unknown_nodes):
                self.node_voltages[node.node_id] = solution[i]

            # The ground node voltage is always 0
            if ground_node:
                 self.node_voltages[ground_node.node_id] = 0.0

            # Extract branch currents (Voltage Sources, Inductors)
            for vs in voltage_sources:
                 vs_index = voltage_source_to_matrix_index[vs]
                 self.component_currents[(vs, "Current (out of +)")] = solution[vs_index]

            for ind in inductors:
                 ind_index = inductor_to_matrix_index[ind]
                 self.component_currents[(ind, "Current (in to out)")] = solution[ind_index]

            # Calculate currents for other components (Resistors, Capacitors)
            self.wire_currents = {} # Clear previous wire currents

            for component in self.netlist.components:
                if isinstance(component, Resistor):
                     pin_in = None
                     pin_out = None
                     for pin in component.get_pins():
                          if pin.data(1) == "in": pin_in = pin
                          elif pin.data(1) == "out": pin_out = pin

                     if pin_in and pin_out:
                          node_in = pin_in.data(3)
                          node_out = pin_out.data(3)

                          if node_in and node_out:
                               v_in = self.node_voltages.get(node_in.node_id, 0.0)
                               v_out = self.node_voltages.get(node_out.node_id, 0.0)
                               resistance = component.resistance

                               if resistance != 0:
                                    current = (v_in - v_out) / resistance
                                    self.component_currents[(component, "Current (in to out)")] = current

                                    # Determine wire currents based on component current
                                    wires_connected_to_in = self.find_wires_connected_to_pin(pin_in)
                                    wires_connected_to_out = self.find_wires_connected_to_pin(pin_out)

                                    current_magnitude = abs(current)

                                    # Assign current magnitude and direction to wires connected to resistor pins
                                    for wire in wires_connected_to_in:
                                         if current > 1e-9: # Current flows from in to out
                                              if wire.start_pin == pin_in: self.wire_currents[(wire, -1)] = current_magnitude # Electron flow into pin_in
                                              elif wire.end_pin == pin_in: self.wire_currents[(wire, 1)] = current_magnitude # Electron flow out of pin_in
                                         elif current < -1e-9: # Current flows from out to in
                                              if wire.start_pin == pin_in: self.wire_currents[(wire, 1)] = current_magnitude # Electron flow out of pin_in
                                              elif wire.end_pin == pin_in: self.wire_currents[(wire, -1)] = current_magnitude # Electron flow into pin_in
                                         else:
                                              self.wire_currents[(wire, 0)] = 0.0 # Zero current

                                    for wire in wires_connected_to_out:
                                         if current > 1e-9: # Current flows from in to out
                                              if wire.start_pin == pin_out: self.wire_currents[(wire, 1)] = current_magnitude # Electron flow out of pin_out
                                              elif wire.end_pin == pin_out: self.wire_currents[(wire, -1)] = current_magnitude # Electron flow into pin_out
                                         elif current < -1e-9: # Current flows from out to in
                                              if wire.start_pin == pin_out: self.wire_currents[(wire, -1)] = current_magnitude # Electron flow into pin_out
                                              elif wire.end_pin == pin_out: self.wire_currents[(wire, 1)] = current_magnitude # Electron flow out of pin_out
                                         else:
                                              self.wire_currents[(wire, 0)] = 0.0 # Zero current


                               else:
                                    self.component_currents[(component, "Current (in to out)")] = float('nan') # Indicate undefined current for R=0
                                    for pin in [pin_in, pin_out]:
                                         for wire in self.find_wires_connected_to_pin(pin):
                                              self.wire_currents[(wire, 0)] = float('nan')


                     else:
                          self.component_currents[(component, "Current (in to out)")] = "Unconnected Pin"


                elif isinstance(component, VoltageSource):
                     vs_current = self.component_currents.get((component, "Current (out of +)"), None)
                     if vs_current is not None:
                          pin_pos = None
                          pin_neg = None
                          for pin in component.get_pins():
                               if pin.data(1) == "+": pin_pos = pin
                               elif pin.data(1) == "-": pin_neg = pin

                          if pin_pos and pin_neg:
                               wires_pos = self.find_wires_connected_to_pin(pin_pos)
                               wires_neg = self.find_wires_connected_to_pin(pin_neg)

                               current_magnitude = abs(vs_current)

                               # Assign current magnitude and direction to wires connected to voltage source pins
                               for wire in wires_pos:
                                    if vs_current > 1e-9: # Current flows out of +
                                         if wire.start_pin == pin_pos: self.wire_currents[(wire, -1)] = current_magnitude # Electron flow into pin_pos
                                         elif wire.end_pin == pin_pos: self.wire_currents[(wire, 1)] = current_magnitude # Electron flow out of pin_pos
                                    elif vs_current < -1e-9: # Current flows into +
                                         if wire.start_pin == pin_pos: self.wire_currents[(wire, 1)] = current_magnitude # Electron flow out of pin_pos
                                         elif wire.end_pin == pin_pos: self.wire_currents[(wire, -1)] = current_magnitude # Electron flow into pin_pos
                                    else:
                                         self.wire_currents[(wire, 0)] = 0.0

                               for wire in wires_neg:
                                    if vs_current > 1e-9: # Current flows out of + (into -)
                                         if wire.start_pin == pin_neg: self.wire_currents[(wire, 1)] = current_magnitude # Electron flow out of pin_neg
                                         elif wire.end_pin == pin_neg: self.wire_currents[(wire, -1)] = current_magnitude # Electron flow into pin_neg
                                    elif vs_current < -1e-9: # Current flows into + (out of -)
                                         if wire.start_pin == pin_neg: self.wire_currents[(wire, -1)] = current_magnitude # Electron flow into pin_neg
                                         elif wire.end_pin == pin_neg: self.wire_currents[(wire, 1)] = current_magnitude # Electron flow out of pin_neg
                                    else:
                                         self.wire_currents[(wire, 0)] = 0.0

                elif isinstance(component, CurrentSource):
                     current = component.current
                     pin_pos = None
                     pin_neg = None
                     for pin in component.get_pins():
                          if pin.data(1) == "+": pin_pos = pin
                          elif pin.data(1) == "-": pin_neg = pin

                     if pin_pos and pin_neg:
                          self.component_currents[(component, "Current (out of +)")] = current # Current is defined by the source

                          wires_pos = self.find_wires_connected_to_pin(pin_pos)
                          wires_neg = self.find_wires_connected_to_pin(pin_neg)

                          current_magnitude = abs(current)

                          # Assign current magnitude and direction to wires connected to current source pins
                          for wire in wires_pos:
                               if current > 1e-9: # Current flows out of +
                                    if wire.start_pin == pin_pos: self.wire_currents[(wire, -1)] = current_magnitude # Electron flow into pin_pos
                                    elif wire.end_pin == pin_pos: self.wire_currents[(wire, 1)] = current_magnitude # Electron flow out of pin_pos
                               elif current < -1e-9: # Current flows into +
                                    if wire.start_pin == pin_pos: self.wire_currents[(wire, 1)] = current_magnitude # Electron flow out of pin_pos
                                    elif wire.end_pin == pin_pos: self.wire_currents[(wire, -1)] = current_magnitude # Electron flow into pin_pos
                               else:
                                    self.wire_currents[(wire, 0)] = 0.0

                          for wire in wires_neg:
                               if current > 1e-9: # Current flows out of + (into -)
                                    if wire.start_pin == pin_neg: self.wire_currents[(wire, 1)] = current_magnitude # Electron flow out of pin_neg
                                    elif wire.end_pin == pin_neg: self.wire_currents[(wire, -1)] = current_magnitude # Electron flow into pin_neg
                               elif current < -1e-9: # Current flows into + (out of -)
                                    if wire.start_pin == pin_neg: self.wire_currents[(wire, -1)] = current_magnitude # Electron flow into pin_neg
                                    elif wire.end_pin == pin_neg: self.wire_currents[(wire, 1)] = current_magnitude # Electron flow out of pin_neg
                               else:
                                    self.wire_currents[(wire, 0)] = 0.0


                elif isinstance(component, Inductor):
                     # Current for inductors is extracted directly from the MNA solution
                     ind_current = self.component_currents.get((component, "Current (in to out)"), None)
                     if ind_current is not None:
                          pin_in = None
                          pin_out = None
                          for pin in component.get_pins():
                               if pin.data(1) == "in": pin_in = pin
                               elif pin.data(1) == "out": pin_out = pin

                          if pin_in and pin_out:
                               wires_in = self.find_wires_connected_to_pin(pin_in)
                               wires_out = self.find_wires_connected_to_pin(pin_out)

                               current_magnitude = abs(ind_current)

                               # Assign current magnitude and direction to wires connected to inductor pins
                               for wire in wires_in:
                                    if ind_current > 1e-9: # Current flows from in to out
                                         if wire.start_pin == pin_in: self.wire_currents[(wire, -1)] = current_magnitude # Electron flow into pin_in
                                         elif wire.end_pin == pin_in: self.wire_currents[(wire, 1)] = current_magnitude # Electron flow out of pin_in
                                    elif ind_current < -1e-9: # Current flows from out to in
                                         if wire.start_pin == pin_in: self.wire_currents[(wire, 1)] = current_magnitude # Electron flow out of pin_in
                                         elif wire.end_pin == pin_in: self.wire_currents[(wire, -1)] = current_magnitude # Electron flow into pin_in
                                    else:
                                         self.wire_currents[(wire, 0)] = 0.0

                               for wire in wires_out:
                                    if ind_current > 1e-9: # Current flows from in to out
                                         if wire.start_pin == pin_out: self.wire_currents[(wire, 1)] = current_magnitude # Electron flow out of pin_out
                                         elif wire.end_pin == pin_out: self.wire_currents[(wire, -1)] = current_magnitude # Electron flow into pin_out
                                    elif ind_current < -1e-9: # Current flows from out to in
                                         if wire.start_pin == pin_out: self.wire_currents[(wire, -1)] = current_magnitude # Electron flow into pin_out
                                         elif wire.end_pin == pin_out: self.wire_currents[(wire, 1)] = current_magnitude # Electron flow out of pin_out
                                    else:
                                         self.wire_currents[(wire, 0)] = 0.0


                elif isinstance(component, Capacitor):
                     # In DC, current through a capacitor is 0
                     self.component_currents[(component, "Current")] = 0.0
                     for pin in component.get_pins():
                          for wire in self.find_wires_connected_to_pin(pin):
                               self.wire_currents[(wire, 0)] = 0.0 # Zero current for wires connected to capacitor


            # Ensure all wires have a current entry (even if 0)
            for wire in self.netlist.wires:
                 has_current_entry = False
                 for (w, direction) in self.wire_currents.keys():
                      if w == wire:
                           has_current_entry = True
                           break
                 if not has_current_entry:
                      self.wire_currents[(wire, 0)] = 0.0 # Default to zero current if not calculated

            # Revert temporary ground setting if it was auto-assigned
            if ground_node and auto_ground_warning:
                 ground_node.is_ground = False

            return "Simulation completed." + (" " + auto_ground_warning if auto_ground_warning else "")


        except np.linalg.LinAlgError as e:
            print(f"Linear algebra error during simulation: {e}")
            self.node_voltages = {}
            self.component_currents = {}
            self.wire_currents = {}
            # Revert temporary ground setting if it was auto-assigned
            if ground_node and auto_ground_warning:
                 ground_node.is_ground = False
            return f"Simulation failed: Could not solve circuit equations. Check for unconnected components or loops without sources/resistors. Error: {e}"
        except Exception as e:
            print(f"An unexpected error occurred during simulation: {e}")
            self.node_voltages = {}
            self.component_currents = {}
            self.wire_currents = {}
            # Revert temporary ground setting if it was auto-assigned
            if ground_node and auto_ground_warning:
                 ground_node.is_ground = False
            return f"Simulation failed: An unexpected error occurred. Error: {e}"

    def find_wire_between_pins(self, pin1, pin2):
        for wire in self.netlist.wires:
            if (wire.start_pin == pin1 and wire.end_pin == pin2) or \
               (wire.start_pin == pin2 and wire.end_pin == pin1):
                return wire
        return None

    def find_wires_connected_to_pin(self, pin):
        connected_wires = []
        for wire in self.netlist.wires:
             if wire.start_pin == pin or wire.end_pin == pin:
                  connected_wires.append(wire)
        return connected_wires

    def get_results_description(self, include_wire_currents=False):
        if not self.node_voltages:
            return "No simulation results available. Run simulation first."

        description = "Simulation Results:\n"
        description += "\nNode Voltages:\n"
        sorted_node_ids = sorted(self.node_voltages.keys())
        for node_id in sorted_node_ids:
             voltage = self.node_voltages[node_id]
             description += f"  Node {node_id}: {voltage:.4f} V\n"

        description += "\nComponent Currents:\n"
        if self.component_currents:
             sorted_current_items = sorted(self.component_currents.items(), key=lambda item: (item[0][0].component_name, item[0][1]))
             for (component, current_label), current in sorted_current_items:
                  if isinstance(current, (int, float)):
                       description += f"  {component.component_name} ({current_label}): {current:.4f} A\n"
                  else:
                       description += f"  {component.component_name} ({current_label}): {current}\n"
        else:
             description += "  No component currents calculated (possibly an empty or unconnected circuit).\n"

        if include_wire_currents:
             description += "\nWire Currents (Electron Flow Magnitude):\n"
             if self.wire_currents:
                  sorted_wire_currents = sorted(self.wire_currents.items(),
                                                key=lambda item: (item[0][0].start_comp.component_name if item[0][0].start_comp else "",
                                                                  item[0][0].end_comp.component_name if item[0][0].end_comp else "",
                                                                  item[0][1]))
                  for (wire, direction), current in sorted_wire_currents:
                       start_comp_name = wire.start_comp.component_name if wire.start_comp else "Unknown"
                       start_pin_name = wire.start_pin.data(1) if wire.start_pin else "Unknown"
                       end_comp_name = wire.end_comp.component_name if wire.end_comp else "Unknown"
                       end_pin_name = wire.end_pin.data(1) if wire.end_pin else "Unknown"
                       direction_str = "Start->End" if direction == 1 else ("End->Start" if direction == -1 else "Zero")
                       if isinstance(current, (int, float)):
                            description += f"  Wire ({start_comp_name}.{start_pin_name} to {end_comp_name}.{end_pin_name}) [{direction_str}]: {current:.4f} A\n"
                       else:
                            description += f"  Wire ({start_comp_name}.{start_pin_name} to {end_comp_name}.{end_pin_name}) [{direction_str}]: {current}\n"
             else:
                  description += "  No wire currents calculated.\n"


        return description

    def get_node_voltage(self, node_id):
        return self.node_voltages.get(node_id, None)

    def get_component_current(self, component, current_label):
        return self.component_currents.get((component, current_label), None)

    def get_wire_current_info(self, wire):
        current_magnitude = self.wire_currents.get((wire, 1), self.wire_currents.get((wire, -1), self.wire_currents.get((wire, 0), None)))

        direction = 0
        if (wire, 1) in self.wire_currents:
             direction = 1
        elif (wire, -1) in self.wire_currents:
             direction = -1
        elif (wire, 0) in self.wire_currents:
             direction = 0
        else:
             pass

        return current_magnitude, direction

    def simulate_transient(self, t_end, dt, progress_callback=None):
        """Simulates transient behavior for simple circuits (RC, RL, RLC)."""
        import numpy as np
        # Identify components
        resistors = [c for c in self.netlist.components if hasattr(c, 'resistance')]
        capacitors = [c for c in self.netlist.components if hasattr(c, 'capacitance')]
        inductors = [c for c in self.netlist.components if hasattr(c, 'inductance')]
        vsources = [c for c in self.netlist.components if hasattr(c, 'voltage')]
        num_steps = int(t_end / dt) + 1
        times = np.linspace(0, t_end, num_steps)
        # RC series circuit
        if len(resistors)==1 and len(capacitors)==1 and len(vsources)==1 and not inductors:
            R = resistors[0].resistance
            C = capacitors[0].capacitance
            V = vsources[0].voltage
            tau = R * C
            voltage = V * (1 - np.exp(-times / tau))
            for i, t in enumerate(times):
                if progress_callback: progress_callback(int(i/(num_steps-1)*100))
            return {'time': times, 'voltage': voltage}
        # RL series circuit
        if len(resistors)==1 and len(inductors)==1 and len(vsources)==1 and not capacitors:
            R = resistors[0].resistance
            L = inductors[0].inductance
            V = vsources[0].voltage
            alpha = R / L
            current = V / R * (1 - np.exp(-alpha * times))
            for i, t in enumerate(times):
                if progress_callback: progress_callback(int(i/(num_steps-1)*100))
            return {'time': times, 'voltage': current}
        # RLC series underdamped circuit
        if len(resistors)==1 and len(capacitors)==1 and len(inductors)==1 and len(vsources)==1:
            R = resistors[0].resistance; L = inductors[0].inductance; C = capacitors[0].capacitance; V = vsources[0].voltage
            alpha = R/(2*L); omega0 = 1/np.sqrt(L*C)
            if alpha < omega0:
                omega_d = np.sqrt(omega0**2 - alpha**2)
                # Voltage across capacitor
                A = V
                B = (alpha/(omega_d))*V
                voltage = V - np.exp(-alpha*times)*(A*np.cos(omega_d*times) + B*np.sin(omega_d*times))
                for i, t in enumerate(times):
                    if progress_callback: progress_callback(int(i/(num_steps-1)*100))
                return {'time': times, 'voltage': voltage}
        # Fallback: constant DC
        self.run_dc_analysis()
        voltage = np.array([self.node_voltages.get(n.node_id,0.0) for n in self.netlist.nodes.values()])
        voltage = np.tile(voltage[0] if voltage.size else 0.0, num_steps)
        if progress_callback: progress_callback(100)
        return {'time': times, 'voltage': voltage}




class PropertiesPanel(QDockWidget):
    def __init__(self, main_window):
        super().__init__("Properties", main_window)
        self.main_window = main_window
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)

        self.central_widget = QWidget()
        self.setWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.component_list_label = QLabel("Select a component:")
        self.layout.addWidget(self.component_list_label)

        self.component_list_widget = QListWidget()
        self.component_list_widget.currentItemChanged.connect(self.on_component_selected)
        self.layout.addWidget(self.component_list_widget)

        self.properties_form_layout = QFormLayout()
        self.layout.addLayout(self.properties_form_layout)

        self.property_editors = {} # Dictionary to store QLineEdit editors for properties

        self.save_button = QPushButton("Apply Changes")
        self.save_button.clicked.connect(self.apply_property_changes)
        self.layout.addWidget(self.save_button)

        self.selected_component = None

    def update_component_list(self):
        """Populates the list widget with components from the netlist."""
        self.component_list_widget.clear()
        for component in self.main_window.netlist.components:
            self.component_list_widget.addItem(component.component_name)

    def on_component_selected(self, current, previous):
        """Displays properties of the selected component."""
        self.clear_properties_display()
        if current:
            component_name = current.text()
            # Find the component object by name
            self.selected_component = None
            for comp in self.main_window.netlist.components:
                if comp.component_name == component_name:
                    self.selected_component = comp
                    break

            if self.selected_component:
                properties = self.selected_component.get_properties()
                for name, value in properties.items():
                    label = QLabel(name + ":")
                    editor = QLineEdit(str(value))
                    self.properties_form_layout.addRow(label, editor)
                    self.property_editors[name] = editor
        else:
            self.selected_component = None


    def update_properties_display(self, selected_items):
        """Updates the properties panel based on items selected on the canvas."""
        self.clear_properties_display()
        self.selected_component = None

        # Find the first selected component
        for item in selected_items:
            if isinstance(item, Component):
                self.selected_component = item
                break

        if self.selected_component:
            # Select the component in the list widget
            items = self.component_list_widget.findItems(self.selected_component.component_name, Qt.MatchFlag.MatchExactly)
            if items:
                 self.component_list_widget.setCurrentItem(items[0])
            else:
                 # If the component is not in the list yet (e.g., just placed), update the list first
                 self.update_component_list()
                 items = self.component_list_widget.findItems(self.selected_component.component_name, Qt.MatchFlag.MatchExactly)
                 if items:
                      self.component_list_widget.setCurrentItem(items[0])


            properties = self.selected_component.get_properties()
            for name, value in properties.items():
                label = QLabel(name + ":")
                editor = QLineEdit(str(value))
                self.properties_form_layout.addRow(label, editor)
                self.property_editors[name] = editor


    def clear_properties_display(self):
        """Clears the property editors from the layout."""
        while self.properties_form_layout.count():
            item = self.properties_form_layout.takeRow(0)
            if item.fieldItem: item.fieldItem.widget().deleteLater()
            if item.labelItem: item.labelItem.widget().deleteLater()
        self.property_editors.clear()

    def apply_property_changes(self):
        """Applies the changes made in the property editors to the selected component."""
        if self.selected_component:
            changes_applied = False
            for name, editor in self.property_editors.items():
                new_value_text = editor.text()
                # Attempt to set the property using the component's method
                if self.selected_component.set_property(name, new_value_text):
                     changes_applied = True
                else:
                     # If setting failed, revert the editor's text to the current property value
                     editor.setText(str(self.selected_component.get_properties().get(name, "")))

            if changes_applied:
                 print(f"Properties updated for {self.selected_component.component_name}")
                 if hasattr(self.main_window, 'hide_simulation_results'):
                      self.main_window.hide_simulation_results()
                 # Re-select the component in the list to refresh the display (especially for Name changes)
                 items = self.component_list_widget.findItems(self.selected_component.component_name, Qt.MatchFlag.MatchExactly)
                 if items:
                      self.component_list_widget.setCurrentItem(items[0])


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Circuit Simulator")
        self.setGeometry(100, 100, 1200, 800) # Increased window size

        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QToolBar {
                background-color: #e8e8e8;
                spacing: 5px;
                padding: 5px;
                border-bottom: 1px solid #d0d0d0;
            }
             QToolButton {
                padding: 8px;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background-color: #ffffff;
                text-align: left;
                min-width: 100px;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
                border-color: #c0c0c0;
            }
            QToolButton:checked {
                background-color: #c0c0c0;
                border-color: #a0a0a0;
            }
            QGraphicsView {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
            }
             QMessageBox {
                background-color: #f8f8f8;
                font-family: "Segoe UI";
            }
            QMessageBox QLabel {
                color: #333333;
            }
            QMessageBox QPushButton {
                padding: 5px 15px;
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #e0e0e0;
            }
            QMessageBox QPushButton:hover {
                background-color: #d0d0d0;
            }
            QMessageBox QPushButton:pressed {
                background-color: #c0c0c0;
            }
            QDockWidget {
                border: 1px solid #d0d0d0;
                titlebar-background-color: #e8e8e8;
            }
            QDockWidget::title {
                text-align: center;
                background-color: #e8e8e8;
                padding: 3px;
            }
            QListWidget {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #c0c0c0;
            }
            QFormLayout QLabel {
                font-weight: bold;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #d0d0d0;
                border-radius: 3px;
            }
            QPushButton {
                padding: 8px;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
        """)
        # Initialize application menus
        self.init_menus()

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
        self.setup_menubar() # Added menubar for File actions

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

        for node_id, node in self.netlist.nodes.items():
            voltage = self.simulation_results.get_node_voltage(node_id)
            if voltage is not None and node.voltage_text_item:
                node.voltage_text_item.setPlainText(f"{voltage:.2f} V")
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

    def init_menus(self):
        menu_bar = self.menuBar()
        # File menu
        file_menu = menu_bar.addMenu("&File")
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        # Analysis menu
        analysis_menu = menu_bar.addMenu("&Analysis")
        transient_action = QAction("Transient Analysis", self)
        transient_action.triggered.connect(self.run_transient_analysis)
        analysis_menu.addAction(transient_action)
        # Help menu
        help_menu = menu_bar.addMenu("&Help")
        instr_action = QAction("Instructions", self)
        instr_action.triggered.connect(self.show_instructions)
        changelog_action = QAction("Changelog", self)
        changelog_action.triggered.connect(self.show_changelog)
        help_menu.addAction(instr_action)
        help_menu.addAction(changelog_action)

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
        QMessageBox.information(self, 'Changelog', open('CHANGELOG.md').read())


from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Transient Analysis Settings')
        layout = QFormLayout(self)
        self.time_end = 1.0
        self.time_step = 0.01
        from PyQt6.QtWidgets import QDoubleSpinBox
        sb_end = QDoubleSpinBox(); sb_end.setValue(self.time_end); sb_end.setSuffix(' s')
        sb_step = QDoubleSpinBox(); sb_step.setValue(self.time_step); sb_step.setSuffix(' s')
        layout.addRow('End Time:', sb_end)
        layout.addRow('Time Step:', sb_step)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(lambda: self.accept_settings(sb_end.value(), sb_step.value()))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept_settings(self, end, step):
        self.time_end = end
        self.time_step = step
        self.accept()

class InstructionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Instructions')
        from PyQt6.QtWidgets import QTextEdit, QVBoxLayout
        layout = QVBoxLayout(self)
        text = QTextEdit(self); text.setReadOnly(True)
        text.setPlainText('''  Welcome to CircuitSimulator V0.5 Beta

- Use the toolbar to place components.
- Draw wires by selecting the wire tool and clicking pins.
- Use the Analysis menu for DC and transient simulations.
- Access settings to configure simulation parameters.
- Press Delete to remove selections.
- View this help under Help > Instructions.
''')
        layout.addWidget(text)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec())

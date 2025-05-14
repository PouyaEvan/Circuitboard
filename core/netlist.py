import json
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

from core.netlist import CircuitNetlist, Node
from components.resistor import Resistor
from components.vs import VoltageSource
from components.cs import CurrentSource
from components.inductor import Inductor
from components.capacitor import Capacitor

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

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
                                              if wire.start_pin == pin_in: self.wire_currents[(wire, 1)] = current_magnitude # Conventional current flow out of pin_in
                                              elif wire.end_pin == pin_in: self.wire_currents[(wire, -1)] = current_magnitude # Conventional current flow into pin_in
                                         elif current < -1e-9: # Current flows from out to in
                                              if wire.start_pin == pin_in: self.wire_currents[(wire, -1)] = current_magnitude # Conventional current flow into pin_in
                                              elif wire.end_pin == pin_in: self.wire_currents[(wire, 1)] = current_magnitude # Conventional current flow out of pin_in
                                         else:
                                              self.wire_currents[(wire, 0)] = 0.0 # Zero current

                                    for wire in wires_connected_to_out:
                                         if current > 1e-9: # Current flows from in to out
                                              if wire.start_pin == pin_out: self.wire_currents[(wire, -1)] = current_magnitude # Conventional current flow into pin_out
                                              elif wire.end_pin == pin_out: self.wire_currents[(wire, 1)] = current_magnitude # Conventional current flow out of pin_out
                                         elif current < -1e-9: # Current flows from out to in
                                              if wire.start_pin == pin_out: self.wire_currents[(wire, 1)] = current_magnitude # Conventional current flow out of pin_out
                                              elif wire.end_pin == pin_out: self.wire_currents[(wire, -1)] = current_magnitude # Conventional current flow into pin_out
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
                                         if wire.start_pin == pin_pos: self.wire_currents[(wire, 1)] = current_magnitude # Conventional current flow out of pin_pos
                                         elif wire.end_pin == pin_pos: self.wire_currents[(wire, -1)] = current_magnitude # Conventional current flow into pin_pos
                                    elif vs_current < -1e-9: # Current flows into +
                                         if wire.start_pin == pin_pos: self.wire_currents[(wire, -1)] = current_magnitude # Conventional current flow into pin_pos
                                         elif wire.end_pin == pin_pos: self.wire_currents[(wire, 1)] = current_magnitude # Conventional current flow out of pin_pos
                                    else:
                                         self.wire_currents[(wire, 0)] = 0.0

                               for wire in wires_neg:
                                    if vs_current > 1e-9: # Current flows out of + (into -)
                                         if wire.start_pin == pin_neg: self.wire_currents[(wire, -1)] = current_magnitude # Conventional current flow into pin_neg
                                         elif wire.end_pin == pin_neg: self.wire_currents[(wire, 1)] = current_magnitude # Conventional current flow out of pin_neg
                                    elif vs_current < -1e-9: # Current flows into + (out of -)
                                         if wire.start_pin == pin_neg: self.wire_currents[(wire, 1)] = current_magnitude # Conventional current flow out of pin_neg
                                         elif wire.end_pin == pin_neg: self.wire_currents[(wire, -1)] = current_magnitude # Conventional current flow into pin_neg
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
                                    if wire.start_pin == pin_pos: self.wire_currents[(wire, 1)] = current_magnitude # Conventional current flow out of pin_pos
                                    elif wire.end_pin == pin_pos: self.wire_currents[(wire, -1)] = current_magnitude # Conventional current flow into pin_pos
                               elif current < -1e-9: # Current flows into +
                                    if wire.start_pin == pin_pos: self.wire_currents[(wire, -1)] = current_magnitude # Conventional current flow into pin_pos
                                    elif wire.end_pin == pin_pos: self.wire_currents[(wire, 1)] = current_magnitude # Conventional current flow out of pin_pos
                               else:
                                    self.wire_currents[(wire, 0)] = 0.0

                          for wire in wires_neg:
                               if current > 1e-9: # Current flows out of + (into -)
                                    if wire.start_pin == pin_neg: self.wire_currents[(wire, -1)] = current_magnitude # Conventional current flow into pin_neg
                                    elif wire.end_pin == pin_neg: self.wire_currents[(wire, 1)] = current_magnitude # Conventional current flow out of pin_neg
                               elif current < -1e-9: # Current flows into + (out of -)
                                    if wire.start_pin == pin_neg: self.wire_currents[(wire, 1)] = current_magnitude # Conventional current flow out of pin_neg
                                    elif wire.end_pin == pin_neg: self.wire_currents[(wire, -1)] = current_magnitude # Conventional current flow into pin_neg
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
                                         if wire.start_pin == pin_in: self.wire_currents[(wire, 1)] = current_magnitude # Conventional current flow out of pin_in
                                         elif wire.end_pin == pin_in: self.wire_currents[(wire, -1)] = current_magnitude # Conventional current flow into pin_in
                                    elif ind_current < -1e-9: # Current flows from out to in
                                         if wire.start_pin == pin_in: self.wire_currents[(wire, -1)] = current_magnitude # Conventional current flow into pin_in
                                         elif wire.end_pin == pin_in: self.wire_currents[(wire, 1)] = current_magnitude # Conventional current flow out of pin_in
                                    else:
                                         self.wire_currents[(wire, 0)] = 0.0

                               for wire in wires_out:
                                    if ind_current > 1e-9: # Current flows from in to out
                                         if wire.start_pin == pin_out: self.wire_currents[(wire, -1)] = current_magnitude # Conventional current flow into pin_out
                                         elif wire.end_pin == pin_out: self.wire_currents[(wire, 1)] = current_magnitude # Conventional current flow out of pin_out
                                    elif ind_current < -1e-9: # Current flows from out to in
                                         if wire.start_pin == pin_out: self.wire_currents[(wire, 1)] = current_magnitude # Conventional current flow out of pin_out
                                         elif wire.end_pin == pin_out: self.wire_currents[(wire, -1)] = current_magnitude # Conventional current flow into pin_out
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

    def _format_value_with_unit(self, value, unit):
        # Helper to format values with SI prefixes
        abs_val = abs(value)
        if unit == 'V':
            if abs_val >= 1:
                return f"{value:.2f} V"
            elif abs_val >= 1e-3:
                return f"{value*1e3:.2f} mV"
            elif abs_val >= 1e-6:
                return f"{value*1e6:.2f} μV"
            else:
                return f"{value:.2e} V"
        elif unit == 'A':
            if abs_val >= 1:
                return f"{value:.2f} A"
            elif abs_val >= 1e-3:
                return f"{value*1e3:.2f} mA"
            elif abs_val >= 1e-6:
                return f"{value*1e6:.2f} μA"
            elif abs_val >= 1e-9:
                return f"{value*1e9:.2f} nA"
            else:
                return f"{value:.2e} A"
        return f"{value} {unit}"

    def get_results_description(self, include_wire_currents=False):
        if not self.node_voltages and not self.component_currents:
            return "No simulation results available."

        description = "DC Simulation Results:\n"
        description += "Node Voltages:\n"
        if self.node_voltages:
            sorted_node_ids = sorted(self.node_voltages.keys())
            for node_id in sorted_node_ids:
                voltage = self.node_voltages[node_id]
                if voltage is None or (isinstance(voltage, float) and (np.isnan(voltage) or np.isinf(voltage))):
                    continue
                ground_status = " (Ground)" if self.netlist.nodes.get(node_id, None) and self.netlist.nodes[node_id].is_ground else ""
                description += f"  Node {node_id}{ground_status}: {self._format_value_with_unit(voltage, 'V')}\n"
        else:
            description += "  No node voltage data.\n"

        description += "\nComponent Currents:\n"
        if self.component_currents:
            for (component, current_label), current_val in self.component_currents.items():
                if isinstance(current_val, str):
                    description += f"  {component.component_name} ({current_label}): {current_val}\n"
                elif current_val is None or (isinstance(current_val, float) and (np.isnan(current_val) or np.isinf(current_val))):
                    continue
                else:
                    description += f"  {component.component_name} ({current_label}): {self._format_value_with_unit(current_val, 'A')}\n"
        else:
            description += "  No component current data.\n"

        if include_wire_currents:
            description += "\nWire Currents (Conventional Current Flow):\n"
            if self.wire_currents:
                processed_wires = set()
                for wire_obj in self.netlist.wires:
                    found_current_for_wire = False
                    for (wire, direction), current_val in self.wire_currents.items():
                        if wire == wire_obj:
                            if wire in processed_wires:
                                continue
                            start_pin_comp = wire.start_pin.data(2)
                            start_pin_name = wire.start_pin.data(1)
                            end_pin_comp = wire.end_pin.data(2)
                            end_pin_name = wire.end_pin.data(1)
                            wire_id_str = f"{start_pin_comp.component_name}.{start_pin_name} to {end_pin_comp.component_name}.{end_pin_name}"
                            flow_desc = "No current"
                            if abs(current_val) > 1e-9:
                                if direction == 1:
                                    flow_desc = f"Conventional current from {start_pin_comp.component_name}.{start_pin_name} to {end_pin_comp.component_name}.{end_pin_name}"
                                elif direction == -1:
                                    flow_desc = f"Conventional current from {end_pin_comp.component_name}.{end_pin_name} to {start_pin_comp.component_name}.{start_pin_name}"
                            description += f"  Wire ({wire_id_str}): {self._format_value_with_unit(current_val, 'A')} ({flow_desc})\n"
                            processed_wires.add(wire)
                            found_current_for_wire = True
                            break
                    if not found_current_for_wire:
                        start_pin_comp = wire_obj.start_pin.data(2)
                        start_pin_name = wire_obj.start_pin.data(1)
                        end_pin_comp = wire_obj.end_pin.data(2)
                        end_pin_name = wire_obj.end_pin.data(1)
                        wire_id_str = f"{start_pin_comp.component_name}.{start_pin_name} to {end_pin_comp.component_name}.{end_pin_name}"
                        zero_current_entry = self.wire_currents.get((wire_obj, 0))
                        if zero_current_entry is not None:
                             description += f"  Wire ({wire_id_str}): {self._format_value_with_unit(zero_current_entry, 'A')} (No current)\n"
                        else:
                             description += f"  Wire ({wire_id_str}): 0.00 A (No current / Not in results)\n"
                        processed_wires.add(wire_obj)
            else:
                description += "  No wire current data.\n"
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

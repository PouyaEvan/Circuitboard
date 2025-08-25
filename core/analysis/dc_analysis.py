"""
DC Analysis Engine - extracted from large run_dc_analysis function.

This module contains the core DC analysis logic that was previously
a 512-line function in the main simulator class.
"""

import numpy as np


class DCAnalysisEngine:
    """
    Modular DC analysis engine for circuit simulation.
    Handles the core DC analysis logic previously embedded in a large function.
    """
    
    def __init__(self, netlist):
        self.netlist = netlist
        self.node_voltages = {}
        self.component_currents = {}
        self.wire_currents = {}
    
    def run_analysis(self):
        """
        Run DC analysis with comprehensive error handling.
        Returns tuple: (success, message, results_dict)
        """
        try:
            # Dynamic import to avoid GUI dependencies
            from components.resistor import Resistor
            from components.vs import VoltageSource
            from components.cs import CurrentSource
            from components.inductor import Inductor
            from components.capacitor import Capacitor
            
            # Setup and validation
            setup_result = self._setup_analysis()
            if not setup_result['success']:
                return False, setup_result['message'], {}
            
            # Build and solve MNA system
            solve_result = self._solve_mna_system(setup_result['data'])
            if not solve_result['success']:
                return False, solve_result['message'], {}
            
            # Calculate component and wire currents
            self._calculate_currents(setup_result['data'], solve_result['solution'])
            
            # Post-process results
            self._post_process_results()
            
            # Cleanup temporary settings
            self._cleanup_analysis(setup_result['data'])
            
            results = {
                'node_voltages': self.node_voltages,
                'component_currents': self.component_currents,
                'wire_currents': self.wire_currents
            }
            
            message = "DC Analysis completed successfully."
            if setup_result['data'].get('auto_ground_warning'):
                message += " " + setup_result['data']['auto_ground_warning']
            
            return True, message, results
            
        except ImportError as e:
            return False, f"Component import error: {str(e)}", {}
        except Exception as e:
            return False, f"DC Analysis failed: {str(e)}", {}
    
    def _setup_analysis(self):
        """Setup analysis including ground node detection and variable mapping."""
        if not self.netlist:
            return {'success': False, 'message': "No netlist available for analysis."}
        
        # Ground node setup
        ground_setup = self._setup_ground_node()
        if not ground_setup['success']:
            return ground_setup
        
        # Identify circuit components
        components_data = self._identify_components()
        
        # Create variable mappings
        mappings = self._create_variable_mappings(components_data)
        
        # Check for trivial cases
        if mappings['num_variables'] == 0:
            self.node_voltages = {ground_setup['ground_node'].node_id: 0.0} if ground_setup['ground_node'] else {}
            self.component_currents = {}
            self.wire_currents = {}
            
            return {
                'success': True, 
                'message': "Trivial circuit analyzed.",
                'data': {
                    'trivial': True,
                    'ground_node': ground_setup['ground_node'],
                    'auto_ground_warning': ground_setup.get('auto_ground_warning', '')
                }
            }
        
        return {
            'success': True,
            'data': {
                'trivial': False,
                'ground_node': ground_setup['ground_node'],
                'auto_ground_warning': ground_setup.get('auto_ground_warning', ''),
                'components': components_data,
                'mappings': mappings
            }
        }
    
    def _setup_ground_node(self):
        """Setup ground node with automatic detection if needed."""
        ground_node = self.netlist.get_ground_node()
        auto_ground_warning = ""
        
        if ground_node is None:
            auto_ground_id = self.netlist.find_automatic_ground_node_id()
            if auto_ground_id is not None and auto_ground_id in self.netlist.nodes:
                ground_node = self.netlist.nodes[auto_ground_id]
                print(f"No explicit ground node found. Automatically setting Node {auto_ground_id} as ground.")
                ground_node.is_ground = True
                auto_ground_warning = f"Warning: Node {auto_ground_id} was automatically set as ground."
            else:
                return {'success': False, 'message': "No ground node found and could not automatically determine one."}
        
        return {
            'success': True,
            'ground_node': ground_node,
            'auto_ground_warning': auto_ground_warning
        }
    
    def _identify_components(self):
        """Identify and categorize circuit components."""
        # Dynamic import to avoid GUI dependencies
        from components.vs import VoltageSource
        from components.inductor import Inductor
        
        voltage_sources = [comp for comp in self.netlist.components if type(comp).__name__ == 'VoltageSource']
        inductors = [comp for comp in self.netlist.components if type(comp).__name__ == 'Inductor']
        nodes = list(self.netlist.nodes.values())
        unknown_nodes = [node for node in nodes if not node.is_ground]
        
        return {
            'voltage_sources': voltage_sources,
            'inductors': inductors,
            'unknown_nodes': unknown_nodes
        }
    
    def _create_variable_mappings(self, components_data):
        """Create mappings from components/nodes to matrix indices."""
        unknown_nodes = components_data['unknown_nodes']
        voltage_sources = components_data['voltage_sources']
        inductors = components_data['inductors']
        
        num_unknown_nodes = len(unknown_nodes)
        num_voltage_sources = len(voltage_sources)
        num_inductors = len(inductors)
        num_variables = num_unknown_nodes + num_voltage_sources + num_inductors
        
        node_id_to_matrix_index = {node.node_id: i for i, node in enumerate(unknown_nodes)}
        voltage_source_to_matrix_index = {vs: num_unknown_nodes + i for i, vs in enumerate(voltage_sources)}
        inductor_to_matrix_index = {ind: num_unknown_nodes + num_voltage_sources + i for i, ind in enumerate(inductors)}
        
        return {
            'num_variables': num_variables,
            'node_id_to_matrix_index': node_id_to_matrix_index,
            'voltage_source_to_matrix_index': voltage_source_to_matrix_index,
            'inductor_to_matrix_index': inductor_to_matrix_index
        }
    
    def _solve_mna_system(self, analysis_data):
        """Build and solve the Modified Nodal Analysis system."""
        if analysis_data['trivial']:
            return {'success': True, 'solution': np.array([])}
        
        mappings = analysis_data['mappings']
        num_variables = mappings['num_variables']
        
        # Initialize MNA matrices
        A = np.zeros((num_variables, num_variables))
        B = np.zeros(num_variables)
        
        # Populate matrices
        self._populate_mna_matrices(A, B, analysis_data)
        
        # Solve system
        try:
            # Check matrix conditioning
            if num_variables > 0:
                cond_number = np.linalg.cond(A)
                if cond_number > 1e12:
                    return {'success': False, 'message': f"Ill-conditioned matrix (condition: {cond_number:.2e})"}
                
                # Check for singular matrix
                if np.linalg.matrix_rank(A) < num_variables:
                    return {'success': False, 'message': self._generate_singular_matrix_hint()}
            
            solution = np.linalg.solve(A, B)
            return {'success': True, 'solution': solution}
            
        except np.linalg.LinAlgError as e:
            return {'success': False, 'message': f"Linear algebra error: {str(e)}"}
    
    def _populate_mna_matrices(self, A, B, analysis_data):
        """Populate the MNA matrices with component stamps."""
        mappings = analysis_data['mappings']
        
        for component in self.netlist.components:
            comp_type = type(component).__name__
            
            if comp_type == 'Resistor':
                self._add_resistor_stamp(A, component, mappings)
            elif comp_type == 'VoltageSource':
                self._add_voltage_source_stamp(A, B, component, mappings)
            elif comp_type == 'CurrentSource':
                self._add_current_source_stamp(B, component, mappings)
            elif comp_type == 'Inductor':
                self._add_inductor_stamp(A, B, component, mappings)
            # Capacitors are open circuits in DC analysis
    
    def _add_resistor_stamp(self, A, component, mappings):
        """Add resistor stamps to MNA matrix."""
        resistance = component.resistance
        if resistance == 0:
            print(f"Warning: Resistor {component.component_name} has zero resistance.")
            return
        
        conductance = 1.0 / resistance
        pin_in, pin_out = self._get_resistor_pins(component)
        
        if pin_in and pin_out:
            node_in, node_out = pin_in.data(3), pin_out.data(3)
            if node_in and node_out:
                self._apply_conductance_stamp(A, node_in, node_out, conductance, mappings)
    
    def _add_voltage_source_stamp(self, A, B, component, mappings):
        """Add voltage source stamps to MNA matrix."""
        voltage = component.voltage
        vs_index = mappings['voltage_source_to_matrix_index'][component]
        
        pin_pos, pin_neg = self._get_voltage_source_pins(component)
        if pin_pos and pin_neg:
            node_pos, node_neg = pin_pos.data(3), pin_neg.data(3)
            if node_pos and node_neg:
                self._apply_voltage_source_stamp(A, B, node_pos, node_neg, voltage, vs_index, mappings)
    
    def _add_current_source_stamp(self, B, component, mappings):
        """Add current source stamps to MNA matrix."""
        current = component.current
        pin_pos, pin_neg = self._get_current_source_pins(component)
        
        if pin_pos and pin_neg:
            node_pos, node_neg = pin_pos.data(3), pin_neg.data(3)
            if node_pos and node_neg:
                self._apply_current_source_stamp(B, node_pos, node_neg, current, mappings)
    
    def _add_inductor_stamp(self, A, B, component, mappings):
        """Add inductor stamps to MNA matrix (short circuit in DC)."""
        pin_in, pin_out = self._get_inductor_pins(component)
        if pin_in and pin_out:
            node_in, node_out = pin_in.data(3), pin_out.data(3)
            if node_in and node_out:
                inductor_index = mappings['inductor_to_matrix_index'][component]
                self._apply_inductor_stamp(A, B, node_in, node_out, inductor_index, mappings)
    
    def _get_resistor_pins(self, component):
        """Get resistor input and output pins."""
        pin_in = pin_out = None
        for pin in component.get_pins():
            if pin.data(1) == "in": pin_in = pin
            elif pin.data(1) == "out": pin_out = pin
        return pin_in, pin_out
    
    def _get_voltage_source_pins(self, component):
        """Get voltage source positive and negative pins."""
        pin_pos = pin_neg = None
        for pin in component.get_pins():
            if pin.data(1) == "+": pin_pos = pin
            elif pin.data(1) == "-": pin_neg = pin
        return pin_pos, pin_neg
    
    def _get_current_source_pins(self, component):
        """Get current source positive and negative pins."""
        return self._get_voltage_source_pins(component)  # Same pin structure
    
    def _get_inductor_pins(self, component):
        """Get inductor input and output pins."""
        return self._get_resistor_pins(component)  # Same pin structure
    
    def _apply_conductance_stamp(self, A, node_in, node_out, conductance, mappings):
        """Apply conductance stamp for resistor."""
        index_in = mappings['node_id_to_matrix_index'].get(node_in.node_id, -1)
        index_out = mappings['node_id_to_matrix_index'].get(node_out.node_id, -1)
        
        if not node_in.is_ground:
            A[index_in, index_in] += conductance
            if not node_out.is_ground:
                A[index_in, index_out] -= conductance
        
        if not node_out.is_ground:
            A[index_out, index_out] += conductance
            if not node_in.is_ground:
                A[index_out, index_in] -= conductance
    
    def _apply_voltage_source_stamp(self, A, B, node_pos, node_neg, voltage, vs_index, mappings):
        """Apply voltage source stamp."""
        index_pos = mappings['node_id_to_matrix_index'].get(node_pos.node_id, -1)
        index_neg = mappings['node_id_to_matrix_index'].get(node_neg.node_id, -1)
        
        if not node_pos.is_ground:
            A[vs_index, index_pos] += 1
            A[index_pos, vs_index] += 1
        
        if not node_neg.is_ground:
            A[vs_index, index_neg] -= 1
            A[index_neg, vs_index] -= 1
        
        B[vs_index] = voltage
    
    def _apply_current_source_stamp(self, B, node_pos, node_neg, current, mappings):
        """Apply current source stamp."""
        index_pos = mappings['node_id_to_matrix_index'].get(node_pos.node_id, -1)
        index_neg = mappings['node_id_to_matrix_index'].get(node_neg.node_id, -1)
        
        if not node_pos.is_ground:
            B[index_pos] -= current
        
        if not node_neg.is_ground:
            B[index_neg] += current
    
    def _apply_inductor_stamp(self, A, B, node_in, node_out, inductor_index, mappings):
        """Apply inductor stamp (short circuit in DC)."""
        index_in = mappings['node_id_to_matrix_index'].get(node_in.node_id, -1)
        index_out = mappings['node_id_to_matrix_index'].get(node_out.node_id, -1)
        
        if not node_in.is_ground:
            A[inductor_index, index_in] += 1
            A[index_in, inductor_index] += 1
        
        if not node_out.is_ground:
            A[inductor_index, index_out] -= 1
            A[index_out, inductor_index] -= 1
        
        B[inductor_index] = 0
    
    def _calculate_currents(self, analysis_data, solution):
        """Calculate component and wire currents from solution."""
        if analysis_data['trivial']:
            return
        
        mappings = analysis_data['mappings']
        components_data = analysis_data['components']
        
        # Extract node voltages
        for i, node in enumerate(components_data['unknown_nodes']):
            self.node_voltages[node.node_id] = solution[i]
        
        # Ground node is always 0V
        if analysis_data['ground_node']:
            self.node_voltages[analysis_data['ground_node'].node_id] = 0.0
        
        # Extract branch currents
        for vs in components_data['voltage_sources']:
            vs_index = mappings['voltage_source_to_matrix_index'][vs]
            self.component_currents[(vs, "Current (out of +)")] = solution[vs_index]
        
        for ind in components_data['inductors']:
            ind_index = mappings['inductor_to_matrix_index'][ind]
            self.component_currents[(ind, "Current (in to out)")] = solution[ind_index]
        
        # Calculate currents for other components
        try:
            from .current_calculator import CurrentCalculator
            calculator = CurrentCalculator(self.netlist, self.node_voltages)
            
            additional_currents = calculator.calculate_all_currents()
            self.component_currents.update(additional_currents['component_currents'])
            self.wire_currents.update(additional_currents['wire_currents'])
        except ImportError:
            print("Warning: Current calculator not available")
    
    def _post_process_results(self):
        """Post-process results to clean up small numerical errors."""
        tolerance = 1e-12
        
        for k, v in list(self.node_voltages.items()):
            if isinstance(v, float) and abs(v) < tolerance:
                self.node_voltages[k] = 0.0
        
        for k, v in list(self.component_currents.items()):
            if isinstance(v, float) and abs(v) < tolerance:
                self.component_currents[k] = 0.0
        
        for k, v in list(self.wire_currents.items()):
            if isinstance(v, float) and abs(v) < tolerance:
                self.wire_currents[k] = 0.0
        
        # Ensure all wires have current entries
        for wire in self.netlist.wires:
            has_current_entry = any(w == wire for (w, direction) in self.wire_currents.keys())
            if not has_current_entry:
                self.wire_currents[(wire, 0)] = 0.0
    
    def _cleanup_analysis(self, analysis_data):
        """Clean up temporary analysis settings."""
        if analysis_data.get('auto_ground_warning') and analysis_data.get('ground_node'):
            analysis_data['ground_node'].is_ground = False
    
    def _generate_singular_matrix_hint(self):
        """Generate helpful message for singular matrix errors."""
        hint = "Simulation failed: Circuit matrix is singular. This usually means:\n"
        hint += "- Some components or nodes are not connected to ground.\n"
        hint += "- There is a loop containing only voltage sources and/or inductors.\n"
        hint += "- There is a cut set containing only current sources.\n"
        hint += "- Check for components with zero resistance or floating nodes/sub-circuits."
        
        # Try to identify unconnected components
        unconnected_components = [
            comp for comp in self.netlist.components 
            if all(pin.data(3) is None or pin.data(3).node_id not in self.netlist.nodes 
                  for pin in comp.get_pins())
        ]
        
        if unconnected_components:
            hint += "\nPotential unconnected components:\n"
            for comp in unconnected_components:
                hint += f"- {comp.component_name}\n"
        
        return hint
    """
    Modular DC analysis engine for circuit simulation.
    Handles the core DC analysis logic previously embedded in a large function.
    """
    
    def __init__(self, netlist):
        self.netlist = netlist
        self.node_voltages = {}
        self.component_currents = {}
        self.wire_currents = {}
    
    def run_analysis(self):
        """
        Run DC analysis with comprehensive error handling.
        Returns tuple: (success, message, results_dict)
        """
        try:
            # Setup and validation
            setup_result = self._setup_analysis()
            if not setup_result['success']:
                return False, setup_result['message'], {}
            
            # Build and solve MNA system
            solve_result = self._solve_mna_system(setup_result['data'])
            if not solve_result['success']:
                return False, solve_result['message'], {}
            
            # Calculate component and wire currents
            self._calculate_currents(setup_result['data'], solve_result['solution'])
            
            # Post-process results
            self._post_process_results()
            
            # Cleanup temporary settings
            self._cleanup_analysis(setup_result['data'])
            
            results = {
                'node_voltages': self.node_voltages,
                'component_currents': self.component_currents,
                'wire_currents': self.wire_currents
            }
            
            message = "DC Analysis completed successfully."
            if setup_result['data'].get('auto_ground_warning'):
                message += " " + setup_result['data']['auto_ground_warning']
            
            return True, message, results
            
        except Exception as e:
            return False, f"DC Analysis failed: {str(e)}", {}
    
    def _setup_analysis(self):
        """Setup analysis including ground node detection and variable mapping."""
        if not self.netlist:
            return {'success': False, 'message': "No netlist available for analysis."}
        
        # Ground node setup
        ground_setup = self._setup_ground_node()
        if not ground_setup['success']:
            return ground_setup
        
        # Identify circuit components
        components_data = self._identify_components()
        
        # Create variable mappings
        mappings = self._create_variable_mappings(components_data)
        
        # Check for trivial cases
        if mappings['num_variables'] == 0:
            self.node_voltages = {ground_setup['ground_node'].node_id: 0.0} if ground_setup['ground_node'] else {}
            self.component_currents = {}
            self.wire_currents = {}
            
            return {
                'success': True, 
                'message': "Trivial circuit analyzed.",
                'data': {
                    'trivial': True,
                    'ground_node': ground_setup['ground_node'],
                    'auto_ground_warning': ground_setup.get('auto_ground_warning', '')
                }
            }
        
        return {
            'success': True,
            'data': {
                'trivial': False,
                'ground_node': ground_setup['ground_node'],
                'auto_ground_warning': ground_setup.get('auto_ground_warning', ''),
                'components': components_data,
                'mappings': mappings
            }
        }
    
    def _setup_ground_node(self):
        """Setup ground node with automatic detection if needed."""
        ground_node = self.netlist.get_ground_node()
        auto_ground_warning = ""
        
        if ground_node is None:
            auto_ground_id = self.netlist.find_automatic_ground_node_id()
            if auto_ground_id is not None and auto_ground_id in self.netlist.nodes:
                ground_node = self.netlist.nodes[auto_ground_id]
                print(f"No explicit ground node found. Automatically setting Node {auto_ground_id} as ground.")
                ground_node.is_ground = True
                auto_ground_warning = f"Warning: Node {auto_ground_id} was automatically set as ground."
            else:
                return {'success': False, 'message': "No ground node found and could not automatically determine one."}
        
        return {
            'success': True,
            'ground_node': ground_node,
            'auto_ground_warning': auto_ground_warning
        }
    
    def _identify_components(self):
        """Identify and categorize circuit components."""
        voltage_sources = [comp for comp in self.netlist.components if isinstance(comp, VoltageSource)]
        inductors = [comp for comp in self.netlist.components if isinstance(comp, Inductor)]
        nodes = list(self.netlist.nodes.values())
        unknown_nodes = [node for node in nodes if not node.is_ground]
        
        return {
            'voltage_sources': voltage_sources,
            'inductors': inductors,
            'unknown_nodes': unknown_nodes
        }
    
    def _create_variable_mappings(self, components_data):
        """Create mappings from components/nodes to matrix indices."""
        unknown_nodes = components_data['unknown_nodes']
        voltage_sources = components_data['voltage_sources']
        inductors = components_data['inductors']
        
        num_unknown_nodes = len(unknown_nodes)
        num_voltage_sources = len(voltage_sources)
        num_inductors = len(inductors)
        num_variables = num_unknown_nodes + num_voltage_sources + num_inductors
        
        node_id_to_matrix_index = {node.node_id: i for i, node in enumerate(unknown_nodes)}
        voltage_source_to_matrix_index = {vs: num_unknown_nodes + i for i, vs in enumerate(voltage_sources)}
        inductor_to_matrix_index = {ind: num_unknown_nodes + num_voltage_sources + i for i, ind in enumerate(inductors)}
        
        return {
            'num_variables': num_variables,
            'node_id_to_matrix_index': node_id_to_matrix_index,
            'voltage_source_to_matrix_index': voltage_source_to_matrix_index,
            'inductor_to_matrix_index': inductor_to_matrix_index
        }
    
    def _solve_mna_system(self, analysis_data):
        """Build and solve the Modified Nodal Analysis system."""
        if analysis_data['trivial']:
            return {'success': True, 'solution': np.array([])}
        
        mappings = analysis_data['mappings']
        num_variables = mappings['num_variables']
        
        # Initialize MNA matrices
        A = np.zeros((num_variables, num_variables))
        B = np.zeros(num_variables)
        
        # Populate matrices
        self._populate_mna_matrices(A, B, analysis_data)
        
        # Solve system
        try:
            # Check matrix conditioning
            if num_variables > 0:
                cond_number = np.linalg.cond(A)
                if cond_number > 1e12:
                    return {'success': False, 'message': f"Ill-conditioned matrix (condition: {cond_number:.2e})"}
                
                # Check for singular matrix
                if np.linalg.matrix_rank(A) < num_variables:
                    return {'success': False, 'message': self._generate_singular_matrix_hint()}
            
            solution = np.linalg.solve(A, B)
            return {'success': True, 'solution': solution}
            
        except np.linalg.LinAlgError as e:
            return {'success': False, 'message': f"Linear algebra error: {str(e)}"}
    
    def _populate_mna_matrices(self, A, B, analysis_data):
        """Populate the MNA matrices with component stamps."""
        mappings = analysis_data['mappings']
        
        for component in self.netlist.components:
            if isinstance(component, Resistor):
                self._add_resistor_stamp(A, component, mappings)
            elif isinstance(component, VoltageSource):
                self._add_voltage_source_stamp(A, B, component, mappings)
            elif isinstance(component, CurrentSource):
                self._add_current_source_stamp(B, component, mappings)
            elif isinstance(component, Inductor):
                self._add_inductor_stamp(A, B, component, mappings)
            # Capacitors are open circuits in DC analysis
    
    def _add_resistor_stamp(self, A, component, mappings):
        """Add resistor stamps to MNA matrix."""
        resistance = component.resistance
        if resistance == 0:
            print(f"Warning: Resistor {component.component_name} has zero resistance.")
            return
        
        conductance = 1.0 / resistance
        pin_in, pin_out = self._get_resistor_pins(component)
        
        if pin_in and pin_out:
            node_in, node_out = pin_in.data(3), pin_out.data(3)
            if node_in and node_out:
                self._apply_conductance_stamp(A, node_in, node_out, conductance, mappings)
    
    def _add_voltage_source_stamp(self, A, B, component, mappings):
        """Add voltage source stamps to MNA matrix."""
        voltage = component.voltage
        vs_index = mappings['voltage_source_to_matrix_index'][component]
        
        pin_pos, pin_neg = self._get_voltage_source_pins(component)
        if pin_pos and pin_neg:
            node_pos, node_neg = pin_pos.data(3), pin_neg.data(3)
            if node_pos and node_neg:
                self._apply_voltage_source_stamp(A, B, node_pos, node_neg, voltage, vs_index, mappings)
    
    def _add_current_source_stamp(self, B, component, mappings):
        """Add current source stamps to MNA matrix."""
        current = component.current
        pin_pos, pin_neg = self._get_current_source_pins(component)
        
        if pin_pos and pin_neg:
            node_pos, node_neg = pin_pos.data(3), pin_neg.data(3)
            if node_pos and node_neg:
                self._apply_current_source_stamp(B, node_pos, node_neg, current, mappings)
    
    def _add_inductor_stamp(self, A, B, component, mappings):
        """Add inductor stamps to MNA matrix (short circuit in DC)."""
        pin_in, pin_out = self._get_inductor_pins(component)
        if pin_in and pin_out:
            node_in, node_out = pin_in.data(3), pin_out.data(3)
            if node_in and node_out:
                inductor_index = mappings['inductor_to_matrix_index'][component]
                self._apply_inductor_stamp(A, B, node_in, node_out, inductor_index, mappings)
    
    def _get_resistor_pins(self, component):
        """Get resistor input and output pins."""
        pin_in = pin_out = None
        for pin in component.get_pins():
            if pin.data(1) == "in": pin_in = pin
            elif pin.data(1) == "out": pin_out = pin
        return pin_in, pin_out
    
    def _get_voltage_source_pins(self, component):
        """Get voltage source positive and negative pins."""
        pin_pos = pin_neg = None
        for pin in component.get_pins():
            if pin.data(1) == "+": pin_pos = pin
            elif pin.data(1) == "-": pin_neg = pin
        return pin_pos, pin_neg
    
    def _get_current_source_pins(self, component):
        """Get current source positive and negative pins."""
        return self._get_voltage_source_pins(component)  # Same pin structure
    
    def _get_inductor_pins(self, component):
        """Get inductor input and output pins."""
        return self._get_resistor_pins(component)  # Same pin structure
    
    def _apply_conductance_stamp(self, A, node_in, node_out, conductance, mappings):
        """Apply conductance stamp for resistor."""
        index_in = mappings['node_id_to_matrix_index'].get(node_in.node_id, -1)
        index_out = mappings['node_id_to_matrix_index'].get(node_out.node_id, -1)
        
        if not node_in.is_ground:
            A[index_in, index_in] += conductance
            if not node_out.is_ground:
                A[index_in, index_out] -= conductance
        
        if not node_out.is_ground:
            A[index_out, index_out] += conductance
            if not node_in.is_ground:
                A[index_out, index_in] -= conductance
    
    def _apply_voltage_source_stamp(self, A, B, node_pos, node_neg, voltage, vs_index, mappings):
        """Apply voltage source stamp."""
        index_pos = mappings['node_id_to_matrix_index'].get(node_pos.node_id, -1)
        index_neg = mappings['node_id_to_matrix_index'].get(node_neg.node_id, -1)
        
        if not node_pos.is_ground:
            A[vs_index, index_pos] += 1
            A[index_pos, vs_index] += 1
        
        if not node_neg.is_ground:
            A[vs_index, index_neg] -= 1
            A[index_neg, vs_index] -= 1
        
        B[vs_index] = voltage
    
    def _apply_current_source_stamp(self, B, node_pos, node_neg, current, mappings):
        """Apply current source stamp."""
        index_pos = mappings['node_id_to_matrix_index'].get(node_pos.node_id, -1)
        index_neg = mappings['node_id_to_matrix_index'].get(node_neg.node_id, -1)
        
        if not node_pos.is_ground:
            B[index_pos] -= current
        
        if not node_neg.is_ground:
            B[index_neg] += current
    
    def _apply_inductor_stamp(self, A, B, node_in, node_out, inductor_index, mappings):
        """Apply inductor stamp (short circuit in DC)."""
        index_in = mappings['node_id_to_matrix_index'].get(node_in.node_id, -1)
        index_out = mappings['node_id_to_matrix_index'].get(node_out.node_id, -1)
        
        if not node_in.is_ground:
            A[inductor_index, index_in] += 1
            A[index_in, inductor_index] += 1
        
        if not node_out.is_ground:
            A[inductor_index, index_out] -= 1
            A[index_out, inductor_index] -= 1
        
        B[inductor_index] = 0
    
    def _calculate_currents(self, analysis_data, solution):
        """Calculate component and wire currents from solution."""
        if analysis_data['trivial']:
            return
        
        mappings = analysis_data['mappings']
        components_data = analysis_data['components']
        
        # Extract node voltages
        for i, node in enumerate(components_data['unknown_nodes']):
            self.node_voltages[node.node_id] = solution[i]
        
        # Ground node is always 0V
        if analysis_data['ground_node']:
            self.node_voltages[analysis_data['ground_node'].node_id] = 0.0
        
        # Extract branch currents
        for vs in components_data['voltage_sources']:
            vs_index = mappings['voltage_source_to_matrix_index'][vs]
            self.component_currents[(vs, "Current (out of +)")] = solution[vs_index]
        
        for ind in components_data['inductors']:
            ind_index = mappings['inductor_to_matrix_index'][ind]
            self.component_currents[(ind, "Current (in to out)")] = solution[ind_index]
        
        # Calculate currents for other components
        from .current_calculator import CurrentCalculator
        calculator = CurrentCalculator(self.netlist, self.node_voltages)
        
        additional_currents = calculator.calculate_all_currents()
        self.component_currents.update(additional_currents['component_currents'])
        self.wire_currents.update(additional_currents['wire_currents'])
    
    def _post_process_results(self):
        """Post-process results to clean up small numerical errors."""
        tolerance = 1e-12
        
        for k, v in list(self.node_voltages.items()):
            if isinstance(v, float) and abs(v) < tolerance:
                self.node_voltages[k] = 0.0
        
        for k, v in list(self.component_currents.items()):
            if isinstance(v, float) and abs(v) < tolerance:
                self.component_currents[k] = 0.0
        
        for k, v in list(self.wire_currents.items()):
            if isinstance(v, float) and abs(v) < tolerance:
                self.wire_currents[k] = 0.0
        
        # Ensure all wires have current entries
        for wire in self.netlist.wires:
            has_current_entry = any(w == wire for (w, direction) in self.wire_currents.keys())
            if not has_current_entry:
                self.wire_currents[(wire, 0)] = 0.0
    
    def _cleanup_analysis(self, analysis_data):
        """Clean up temporary analysis settings."""
        if analysis_data.get('auto_ground_warning') and analysis_data.get('ground_node'):
            analysis_data['ground_node'].is_ground = False
    
    def _generate_singular_matrix_hint(self):
        """Generate helpful message for singular matrix errors."""
        hint = "Simulation failed: Circuit matrix is singular. This usually means:\n"
        hint += "- Some components or nodes are not connected to ground.\n"
        hint += "- There is a loop containing only voltage sources and/or inductors.\n"
        hint += "- There is a cut set containing only current sources.\n"
        hint += "- Check for components with zero resistance or floating nodes/sub-circuits."
        
        # Try to identify unconnected components
        unconnected_components = [
            comp for comp in self.netlist.components 
            if all(pin.data(3) is None or pin.data(3).node_id not in self.netlist.nodes 
                  for pin in comp.get_pins())
        ]
        
        if unconnected_components:
            hint += "\nPotential unconnected components:\n"
            for comp in unconnected_components:
                hint += f"- {comp.component_name}\n"
        
        return hint
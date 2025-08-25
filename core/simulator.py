from core.netlist import CircuitNetlist, Node

try:
    import numpy as np
    NUMPY_AVAILABLE = True
    # Import enhanced simulator if available
    try:
        from core.advanced_simulator import AdvancedCircuitSimulator, SimulationSettings, AnalysisType
        ADVANCED_SIMULATOR_AVAILABLE = True
    except ImportError:
        ADVANCED_SIMULATOR_AVAILABLE = False
    
    # Import modular analysis components
    try:
        from core.analysis.dc_analysis import DCAnalysisEngine
        from core.analysis.results_formatter import ResultsFormatter
        MODULAR_ANALYSIS_AVAILABLE = True
    except ImportError:
        MODULAR_ANALYSIS_AVAILABLE = False
except ImportError:
    NUMPY_AVAILABLE = False
    ADVANCED_SIMULATOR_AVAILABLE = False
    MODULAR_ANALYSIS_AVAILABLE = False

class CircuitSimulator:
    def __init__(self, netlist):
        if not NUMPY_AVAILABLE:
            print("NumPy not available, simulation cannot run.")
            self.netlist = None
            self.node_voltages = {}
            self.component_currents = {}
            self.wire_currents = {}
            self.advanced_simulator = None
            self.modular_dc_engine = None
        else:
            self.netlist = netlist
            self.node_voltages = {}
            self.component_currents = {}
            self.wire_currents = {}
            
            # Initialize advanced simulator if available
            if ADVANCED_SIMULATOR_AVAILABLE:
                try:
                    settings = SimulationSettings(
                        use_sparse=True,
                        tolerance=1e-12,
                        enable_debug=False
                    )
                    self.advanced_simulator = AdvancedCircuitSimulator(netlist, settings)
                    print("Advanced simulator initialized successfully.")
                except Exception as e:
                    print(f"Failed to initialize advanced simulator: {e}")
                    self.advanced_simulator = None
            else:
                self.advanced_simulator = None
            
            # Initialize modular DC analysis engine
            if MODULAR_ANALYSIS_AVAILABLE:
                try:
                    self.modular_dc_engine = DCAnalysisEngine(netlist)
                    print("Modular DC analysis engine initialized successfully.")
                except Exception as e:
                    print(f"Failed to initialize modular DC engine: {e}")
                    self.modular_dc_engine = None
            else:
                self.modular_dc_engine = None


    def run_dc_analysis(self):
        # Try advanced simulator first
        if self.advanced_simulator is not None:
            try:
                print("Using advanced simulator for DC analysis...")
                result = self.advanced_simulator.run_dc_analysis()
                
                if result.success:
                    # Extract results for compatibility
                    self.node_voltages = {}
                    self.component_currents = {}
                    self.wire_currents = {}
                    
                    # Convert complex results to real for DC analysis
                    for node_id, voltage in result.node_voltages.items():
                        if isinstance(voltage, complex):
                            self.node_voltages[node_id] = voltage.real
                        else:
                            self.node_voltages[node_id] = voltage
                    
                    for (comp, label), current in result.component_currents.items():
                        if isinstance(current, complex):
                            self.component_currents[(comp, label)] = current.real
                        else:
                            self.component_currents[(comp, label)] = current
                    
                    for (wire, direction), current in result.wire_currents.items():
                        if isinstance(current, complex):
                            self.wire_currents[(wire, direction)] = current.real
                        else:
                            self.wire_currents[(wire, direction)] = current
                    
                    return result.message
                else:
                    print(f"Advanced simulator failed: {result.message}")
                    print("Falling back to modular DC engine...")
            except Exception as e:
                print(f"Advanced simulator error: {e}")
                print("Falling back to modular DC engine...")
        
        # Try modular DC analysis engine
        if self.modular_dc_engine is not None:
            try:
                print("Using modular DC analysis engine...")
                success, message, results = self.modular_dc_engine.run_analysis()
                
                if success:
                    self.node_voltages = results.get('node_voltages', {})
                    self.component_currents = results.get('component_currents', {})
                    self.wire_currents = results.get('wire_currents', {})
                    return message
                else:
                    print(f"Modular DC engine failed: {message}")
                    print("Falling back to legacy DC analysis...")
            except Exception as e:
                print(f"Modular DC engine error: {e}")
                print("Falling back to legacy DC analysis...")
        
        # Fallback to minimal legacy implementation (simplified for emergency use)
        return self._legacy_dc_analysis_fallback()

    def _legacy_dc_analysis_fallback(self):
        """Minimal legacy DC analysis implementation for emergency fallback."""
        if not self.netlist or not NUMPY_AVAILABLE:
            self.node_voltages = {}
            self.component_currents = {}
            self.wire_currents = {}
            return "Simulation requires a netlist and NumPy."
        
        # Very basic analysis - just handle simple resistor circuits
        print("Using minimal legacy fallback analysis...")
        self.node_voltages = {}
        self.component_currents = {}
        self.wire_currents = {}
        
        # Try to find ground
        ground_node = self.netlist.get_ground_node()
        if ground_node:
            self.node_voltages[ground_node.node_id] = 0.0
        
        return "Legacy fallback analysis completed (limited functionality)."
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

    def get_results_description(self, include_wire_currents=False):
        # Use modular results formatter if available
        if MODULAR_ANALYSIS_AVAILABLE:
            try:
                formatter = ResultsFormatter(
                    self.node_voltages, 
                    self.component_currents, 
                    self.wire_currents, 
                    self.netlist
                )
                return formatter.get_results_description(include_wire_currents)
            except Exception as e:
                print(f"Modular formatter error: {e}, falling back to basic formatter")
        
        # Basic fallback formatter
        if not self.node_voltages and not self.component_currents:
            return "No simulation results available."
        
        description = "DC Simulation Results:\n"
        description += "Node Voltages:\n"
        
        if self.node_voltages:
            for node_id, voltage in sorted(self.node_voltages.items()):
                description += f"  Node {node_id}: {voltage:.6g} V\n"
        else:
            description += "  No node voltage data.\n"
        
        description += "\nComponent Currents:\n"
        if self.component_currents:
            for (component, label), current in self.component_currents.items():
                if isinstance(current, str):
                    description += f"  {component.component_name} ({label}): {current}\n"
                else:
                    description += f"  {component.component_name} ({label}): {current:.6g} A\n"
        else:
            description += "  No component current data.\n"
        
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

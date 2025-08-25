"""
Results Formatter - extracted from large results formatting logic.

This module handles the formatting and presentation of simulation results,
which was previously embedded in a large function.
"""

import numpy as np


class ResultsFormatter:
    """
    Handles formatting and presentation of simulation results.
    """
    
    def __init__(self, node_voltages, component_currents, wire_currents, netlist):
        self.node_voltages = node_voltages
        self.component_currents = component_currents
        self.wire_currents = wire_currents
        self.netlist = netlist
    
    def get_results_description(self, include_wire_currents=False):
        """
        Generate comprehensive description of simulation results.
        """
        if not self.node_voltages and not self.component_currents:
            return "No simulation results available."
        
        description = "DC Simulation Results:\n"
        description += self._format_node_voltages()
        description += self._format_component_currents()
        
        if include_wire_currents:
            description += self._format_wire_currents()
        
        return description
    
    def _format_node_voltages(self):
        """Format node voltage results."""
        description = "Node Voltages:\n"
        
        if not self.node_voltages:
            return description + "  No node voltage data.\n"
        
        sorted_node_ids = sorted(self.node_voltages.keys())
        for node_id in sorted_node_ids:
            voltage = self.node_voltages[node_id]
            
            if self._is_invalid_value(voltage):
                continue
            
            ground_status = self._get_ground_status(node_id)
            formatted_voltage = self._format_value_with_unit(voltage, 'V')
            description += f"  Node {node_id}{ground_status}: {formatted_voltage}\n"
        
        return description + "\n"
    
    def _format_component_currents(self):
        """Format component current results."""
        description = "Component Currents:\n"
        
        if not self.component_currents:
            return description + "  No component current data.\n"
        
        for (component, current_label), current_val in self.component_currents.items():
            if isinstance(current_val, str):
                description += f"  {component.component_name} ({current_label}): {current_val}\n"
            elif self._is_invalid_value(current_val):
                continue
            else:
                arrow = "→" if current_val >= 0 else "←"
                formatted_current = self._format_value_with_unit(abs(current_val), 'A')
                description += f"  {component.component_name} ({current_label}): {formatted_current} {arrow}\n"
        
        return description + "\n"
    
    def _format_wire_currents(self):
        """Format wire current results."""
        description = "Wire Currents (Conventional Current Flow):\n"
        
        if not self.wire_currents:
            return description + "  No wire current data.\n"
        
        processed_wires = set()
        
        for wire_obj in self.netlist.wires:
            if wire_obj in processed_wires:
                continue
            
            current_info = self._get_wire_current_info(wire_obj)
            if current_info:
                description += current_info + "\n"
                processed_wires.add(wire_obj)
        
        return description
    
    def _get_wire_current_info(self, wire_obj):
        """Get formatted current information for a specific wire."""
        # Find current entry for this wire
        wire_current_entry = None
        direction = 0
        
        for (wire, dir_val), current_val in self.wire_currents.items():
            if wire == wire_obj:
                wire_current_entry = current_val
                direction = dir_val
                break
        
        if wire_current_entry is None:
            # Check for zero current entry
            zero_entry = self.wire_currents.get((wire_obj, 0))
            if zero_entry is not None:
                wire_current_entry = zero_entry
                direction = 0
            else:
                wire_current_entry = 0.0
                direction = 0
        
        # Generate wire description
        wire_desc = self._get_wire_description(wire_obj)
        flow_desc = self._get_flow_description(wire_obj, direction, wire_current_entry)
        arrow = self._get_current_arrow(direction)
        formatted_current = self._format_value_with_unit(abs(wire_current_entry), 'A')
        
        return f"  Wire ({wire_desc}): {formatted_current} {arrow} ({flow_desc})"
    
    def _get_wire_description(self, wire_obj):
        """Get description of wire endpoints."""
        try:
            start_comp = wire_obj.start_pin.data(2)
            start_pin = wire_obj.start_pin.data(1)
            end_comp = wire_obj.end_pin.data(2)
            end_pin = wire_obj.end_pin.data(1)
            
            return f"{start_comp.component_name}.{start_pin} to {end_comp.component_name}.{end_pin}"
        except (AttributeError, IndexError):
            return "Unknown wire"
    
    def _get_flow_description(self, wire_obj, direction, current_val):
        """Get description of current flow direction."""
        if abs(current_val) <= 1e-9:
            return "No current"
        
        try:
            start_comp = wire_obj.start_pin.data(2)
            start_pin = wire_obj.start_pin.data(1)
            end_comp = wire_obj.end_pin.data(2)
            end_pin = wire_obj.end_pin.data(1)
            
            if direction == 1:
                return f"Conventional current from {start_comp.component_name}.{start_pin} to {end_comp.component_name}.{end_pin}"
            elif direction == -1:
                return f"Conventional current from {end_comp.component_name}.{end_pin} to {start_comp.component_name}.{start_pin}"
            else:
                return "No current"
        except (AttributeError, IndexError):
            return "Unknown flow direction"
    
    def _get_current_arrow(self, direction):
        """Get arrow symbol for current direction."""
        if direction == 1:
            return "→"
        elif direction == -1:
            return "←"
        else:
            return "-"
    
    def _get_ground_status(self, node_id):
        """Get ground status annotation for node."""
        node = self.netlist.nodes.get(node_id)
        if node and node.is_ground:
            return " (Ground)"
        return ""
    
    def _is_invalid_value(self, value):
        """Check if value is invalid (None, NaN, or infinite)."""
        if value is None:
            return True
        if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
            return True
        return False
    
    def _format_value_with_unit(self, value, unit):
        """Format numerical value with appropriate SI prefix and unit."""
        abs_val = abs(value)
        
        if unit == 'V':
            return self._format_voltage(value, abs_val)
        elif unit == 'A':
            return self._format_current(value, abs_val)
        else:
            return f"{value} {unit}"
    
    def _format_voltage(self, value, abs_val):
        """Format voltage with appropriate prefix."""
        if abs_val >= 1:
            return f"{value:.6g} V"
        elif abs_val >= 1e-3:
            return f"{value*1e3:.6g} mV"
        elif abs_val >= 1e-6:
            return f"{value*1e6:.6g} μV"
        elif abs_val >= 1e-9:
            return f"{value*1e9:.6g} nV"
        else:
            return f"{value:.2e} V"
    
    def _format_current(self, value, abs_val):
        """Format current with appropriate prefix."""
        if abs_val >= 1:
            return f"{value:.6g} A"
        elif abs_val >= 1e-3:
            return f"{value*1e3:.6g} mA"
        elif abs_val >= 1e-6:
            return f"{value*1e6:.6g} μA"
        elif abs_val >= 1e-9:
            return f"{value*1e9:.6g} nA"
        else:
            return f"{value:.2e} A"
    
    def get_summary_stats(self):
        """Get summary statistics of the simulation results."""
        stats = {
            'num_nodes': len(self.node_voltages),
            'num_components': len(self.component_currents),
            'num_wires': len([w for (w, d) in self.wire_currents.keys()]),
            'max_voltage': max(self.node_voltages.values()) if self.node_voltages else 0,
            'min_voltage': min(self.node_voltages.values()) if self.node_voltages else 0,
        }
        
        # Component current stats
        component_current_values = [
            v for v in self.component_currents.values() 
            if isinstance(v, (int, float)) and not np.isnan(v) and not np.isinf(v)
        ]
        
        if component_current_values:
            stats['max_current'] = max(component_current_values)
            stats['min_current'] = min(component_current_values)
        else:
            stats['max_current'] = 0
            stats['min_current'] = 0
        
        return stats
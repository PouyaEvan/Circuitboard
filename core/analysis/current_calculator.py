"""
Current Calculator - extracted from large current calculation logic.

This module handles the calculation of component and wire currents
from node voltages, which was previously embedded in the main analysis function.
"""

import numpy as np


class CurrentCalculator:
    """
    Handles calculation of component and wire currents from node voltages.
    """
    
    def __init__(self, netlist, node_voltages):
        self.netlist = netlist
        self.node_voltages = node_voltages
        self.component_currents = {}
        self.wire_currents = {}
    
    def calculate_all_currents(self):
        """
        Calculate currents for all components and wires.
        Returns dict with component_currents and wire_currents.
        """
        self.component_currents = {}
        self.wire_currents = {}
        
        for component in self.netlist.components:
            comp_type = type(component).__name__
            
            if comp_type == 'Resistor':
                self._calculate_resistor_current(component)
            elif comp_type == 'VoltageSource':
                self._calculate_voltage_source_wire_currents(component)
            elif comp_type == 'CurrentSource':
                self._calculate_current_source_wire_currents(component)
            elif comp_type == 'Inductor':
                self._calculate_inductor_wire_currents(component)
            elif comp_type == 'Capacitor':
                self._calculate_capacitor_current(component)
        
        return {
            'component_currents': self.component_currents,
            'wire_currents': self.wire_currents
        }
    
    def _calculate_resistor_current(self, component):
        """Calculate current through resistor and connected wires."""
        pin_in, pin_out = self._get_component_pins(component, ["in", "out"])
        
        if not (pin_in and pin_out):
            self.component_currents[(component, "Current (in to out)")] = "Unconnected Pin"
            return
        
        node_in = pin_in.data(3)
        node_out = pin_out.data(3)
        
        if not (node_in and node_out):
            self.component_currents[(component, "Current (in to out)")] = "Unconnected Pin"
            return
        
        v_in = self.node_voltages.get(node_in.node_id, 0.0)
        v_out = self.node_voltages.get(node_out.node_id, 0.0)
        resistance = component.resistance
        
        if resistance == 0:
            self.component_currents[(component, "Current (in to out)")] = float('nan')
            self._assign_wire_currents_for_pins([pin_in, pin_out], float('nan'), 0)
            return
        
        current = (v_in - v_out) / resistance
        self.component_currents[(component, "Current (in to out)")] = current
        
        # Assign wire currents based on resistor current direction
        self._assign_resistor_wire_currents(pin_in, pin_out, current)
    
    def _calculate_voltage_source_wire_currents(self, component):
        """Calculate wire currents for voltage source (current already calculated in MNA)."""
        vs_current = self.component_currents.get((component, "Current (out of +)"))
        if vs_current is None:
            return
        
        pin_pos, pin_neg = self._get_component_pins(component, ["+", "-"])
        if pin_pos and pin_neg:
            self._assign_source_wire_currents(pin_pos, pin_neg, vs_current)
    
    def _calculate_current_source_wire_currents(self, component):
        """Calculate wire currents for current source."""
        current = component.current
        self.component_currents[(component, "Current (out of +)")] = current
        
        pin_pos, pin_neg = self._get_component_pins(component, ["+", "-"])
        if pin_pos and pin_neg:
            self._assign_source_wire_currents(pin_pos, pin_neg, current)
    
    def _calculate_inductor_wire_currents(self, component):
        """Calculate wire currents for inductor (current already calculated in MNA)."""
        ind_current = self.component_currents.get((component, "Current (in to out)"))
        if ind_current is None:
            return
        
        pin_in, pin_out = self._get_component_pins(component, ["in", "out"])
        if pin_in and pin_out:
            self._assign_resistor_wire_currents(pin_in, pin_out, ind_current)
    
    def _calculate_capacitor_current(self, component):
        """Calculate capacitor current (zero in DC analysis)."""
        self.component_currents[(component, "Current")] = 0.0
        
        for pin in component.get_pins():
            wires = self._find_wires_connected_to_pin(pin)
            for wire in wires:
                self.wire_currents[(wire, 0)] = 0.0
    
    def _assign_resistor_wire_currents(self, pin_in, pin_out, current):
        """Assign wire currents for resistor-like components."""
        current_magnitude = abs(current)
        
        # Wires connected to input pin
        wires_in = self._find_wires_connected_to_pin(pin_in)
        for wire in wires_in:
            if current > 1e-9:  # Current flows from in to out
                direction = 1 if wire.start_pin == pin_in else -1
            elif current < -1e-9:  # Current flows from out to in
                direction = -1 if wire.start_pin == pin_in else 1
            else:
                direction = 0
            self.wire_currents[(wire, direction)] = current_magnitude if direction != 0 else 0.0
        
        # Wires connected to output pin
        wires_out = self._find_wires_connected_to_pin(pin_out)
        for wire in wires_out:
            if current > 1e-9:  # Current flows from in to out
                direction = -1 if wire.start_pin == pin_out else 1
            elif current < -1e-9:  # Current flows from out to in
                direction = 1 if wire.start_pin == pin_out else -1
            else:
                direction = 0
            self.wire_currents[(wire, direction)] = current_magnitude if direction != 0 else 0.0
    
    def _assign_source_wire_currents(self, pin_pos, pin_neg, current):
        """Assign wire currents for voltage/current sources."""
        current_magnitude = abs(current)
        
        # Wires connected to positive pin
        wires_pos = self._find_wires_connected_to_pin(pin_pos)
        for wire in wires_pos:
            if current > 1e-9:  # Current flows out of +
                direction = 1 if wire.start_pin == pin_pos else -1
            elif current < -1e-9:  # Current flows into +
                direction = -1 if wire.start_pin == pin_pos else 1
            else:
                direction = 0
            self.wire_currents[(wire, direction)] = current_magnitude if direction != 0 else 0.0
        
        # Wires connected to negative pin
        wires_neg = self._find_wires_connected_to_pin(pin_neg)
        for wire in wires_neg:
            if current > 1e-9:  # Current flows out of + (into -)
                direction = -1 if wire.start_pin == pin_neg else 1
            elif current < -1e-9:  # Current flows into + (out of -)
                direction = 1 if wire.start_pin == pin_neg else -1
            else:
                direction = 0
            self.wire_currents[(wire, direction)] = current_magnitude if direction != 0 else 0.0
    
    def _assign_wire_currents_for_pins(self, pins, current_value, direction):
        """Assign current to all wires connected to given pins."""
        for pin in pins:
            wires = self._find_wires_connected_to_pin(pin)
            for wire in wires:
                self.wire_currents[(wire, direction)] = current_value
    
    def _get_component_pins(self, component, pin_names):
        """Get pins with specified names from component."""
        pins = [None] * len(pin_names)
        for pin in component.get_pins():
            pin_name = pin.data(1)
            if pin_name in pin_names:
                pins[pin_names.index(pin_name)] = pin
        return pins if len(pins) > 1 else pins[0] if pins else None
    
    def _find_wires_connected_to_pin(self, pin):
        """Find all wires connected to a specific pin."""
        connected_wires = []
        for wire in self.netlist.wires:
            if wire.start_pin == pin or wire.end_pin == pin:
                connected_wires.append(wire)
        return connected_wires
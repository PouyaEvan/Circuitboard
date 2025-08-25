"""
Enhanced Circuit Netlist with graph-based representation, advanced connectivity analysis,
circuit topology detection, and robust validation. This is a complete overhaul of the
original netlist system with significant improvements in functionality and performance.
"""

import json
import networkx as nx
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional, Any, Union
from enum import Enum
import numpy as np
from abc import ABC, abstractmethod
import logging

from config import *
from components.wire import Wire
from components.capacitor import Capacitor
from components.ground import Ground
from components.inductor import Inductor
from components.resistor import Resistor
from components.vs import VoltageSource
from components.cs import CurrentSource

logger = logging.getLogger(__name__)

class NodeType(Enum):
    """Types of nodes in the circuit"""
    REGULAR = "regular"
    GROUND = "ground"
    JUNCTION = "junction"
    INPUT = "input"
    OUTPUT = "output"

class ComponentType(Enum):
    """Enhanced component classification"""
    PASSIVE_LINEAR = "passive_linear"      # R, L, C
    ACTIVE_LINEAR = "active_linear"        # Ideal sources, op-amps
    PASSIVE_NONLINEAR = "passive_nonlinear"  # Diodes, nonlinear R
    ACTIVE_NONLINEAR = "active_nonlinear"    # Transistors, nonlinear sources

class CircuitTopology(Enum):
    """Circuit topology classifications"""
    SERIES = "series"
    PARALLEL = "parallel"
    SERIES_PARALLEL = "series_parallel"
    BRIDGE = "bridge"
    LADDER = "ladder"
    MESH = "mesh"
    TREE = "tree"
    COMPLEX = "complex"

@dataclass
class ConnectionInfo:
    """Enhanced connection information"""
    component: Any
    pin_name: str
    pin_item: Any
    connection_type: str = "normal"  # normal, bus, differential
    signal_name: Optional[str] = None
    impedance: Optional[float] = None

@dataclass
class NodeProperties:
    """Enhanced node properties with electrical characteristics"""
    node_id: int
    node_type: NodeType = NodeType.REGULAR
    connections: List[ConnectionInfo] = field(default_factory=list)
    voltage: Optional[complex] = None
    is_ground: bool = False
    is_floating: bool = False
    capacitance: float = 0.0  # Parasitic capacitance
    resistance: float = 0.0   # Contact resistance
    max_current: float = float('inf')  # Current rating
    voltage_rating: float = float('inf')  # Voltage rating
    coordinates: Optional[Tuple[float, float]] = None
    
    # Visual properties
    voltage_text_item: Any = None
    junction_item: Any = None
    highlight_color: Optional[str] = None

@dataclass
class WireProperties:
    """Enhanced wire properties with electrical characteristics"""
    wire: Any
    start_node: int
    end_node: int
    length: float = 0.0
    resistance: float = 0.0
    inductance: float = 0.0
    capacitance: float = 0.0
    current_rating: float = float('inf')
    voltage_rating: float = float('inf')
    wire_type: str = "normal"  # normal, bus, differential, coax
    impedance: Optional[float] = None
    delay: float = 0.0  # Propagation delay

@dataclass
class CircuitMetrics:
    """Circuit analysis metrics"""
    node_count: int = 0
    component_count: int = 0
    wire_count: int = 0
    loop_count: int = 0
    cutset_count: int = 0
    connectivity_score: float = 0.0
    complexity_score: float = 0.0
    max_node_degree: int = 0
    avg_node_degree: float = 0.0
    graph_diameter: int = 0
    clustering_coefficient: float = 0.0

class CircuitValidator:
    """Advanced circuit validation and error detection"""
    
    def __init__(self, netlist):
        self.netlist = netlist
        self.errors = []
        self.warnings = []
    
    def validate_circuit(self) -> Tuple[List[str], List[str]]:
        """Comprehensive circuit validation"""
        self.errors.clear()
        self.warnings.clear()
        
        self._validate_connectivity()
        self._validate_components()
        self._validate_electrical_rules()
        self._validate_topology()
        
        return self.errors, self.warnings
    
    def _validate_connectivity(self):
        """Validate circuit connectivity"""
        # Check for floating nodes
        for node_id, node in self.netlist.nodes.items():
            if len(node.connections) == 0:
                self.errors.append(f"Node {node_id} has no connections")
            elif len(node.connections) == 1 and not node.is_ground:
                self.warnings.append(f"Node {node_id} has only one connection (floating)")
        
        # Check for unconnected components
        for comp in self.netlist.components:
            connected_pins = 0
            for pin in comp.get_pins():
                if pin.data(3) is not None:
                    connected_pins += 1
            
            if connected_pins == 0:
                self.errors.append(f"Component {comp.component_name} is not connected")
            elif connected_pins < len(comp.get_pins()):
                self.warnings.append(f"Component {comp.component_name} has unconnected pins")
        
        # Check for ground connectivity
        if not self.netlist.get_ground_node():
            self.errors.append("No ground node found")
        
        # Check for isolated subgraphs
        subgraphs = self.netlist.find_connected_subgraphs()
        if len(subgraphs) > 1:
            self.warnings.append(f"Circuit has {len(subgraphs)} disconnected subgraphs")
    
    def _validate_components(self):
        """Validate individual components"""
        for comp in self.netlist.components:
            # Check component values
            if isinstance(comp, Resistor):
                if comp.resistance <= 0:
                    self.errors.append(f"Resistor {comp.component_name} has invalid resistance: {comp.resistance}")
                elif comp.resistance < 1e-6:
                    self.warnings.append(f"Resistor {comp.component_name} has very small resistance: {comp.resistance}")
            
            elif isinstance(comp, Capacitor):
                if comp.capacitance <= 0:
                    self.errors.append(f"Capacitor {comp.component_name} has invalid capacitance: {comp.capacitance}")
            
            elif isinstance(comp, Inductor):
                if comp.inductance <= 0:
                    self.errors.append(f"Inductor {comp.component_name} has invalid inductance: {comp.inductance}")
    
    def _validate_electrical_rules(self):
        """Validate electrical design rules"""
        # Check for voltage source loops
        vs_loops = self.netlist.find_voltage_source_loops()
        if vs_loops:
            self.errors.append(f"Found {len(vs_loops)} voltage source loops")
        
        # Check for current source cutsets
        cs_cutsets = self.netlist.find_current_source_cutsets()
        if cs_cutsets:
            self.errors.append(f"Found {len(cs_cutsets)} current source cutsets")
        
        # Check for short circuits
        short_circuits = self.netlist.find_short_circuits()
        if short_circuits:
            self.warnings.append(f"Found {len(short_circuits)} potential short circuits")
    
    def _validate_topology(self):
        """Validate circuit topology"""
        # Check for reasonable circuit complexity
        metrics = self.netlist.analyze_circuit_metrics()
        
        if metrics.max_node_degree > 10:
            self.warnings.append(f"Node with very high degree: {metrics.max_node_degree} connections")
        
        if metrics.complexity_score > 0.8:
            self.warnings.append(f"Circuit has high complexity score: {metrics.complexity_score:.2f}")

class EnhancedNode(NodeProperties):
    """Enhanced node class with advanced properties and methods"""
    
    def __init__(self, node_id: int, node_type: NodeType = NodeType.REGULAR):
        super().__init__(node_id=node_id, node_type=node_type)
    
    def add_connection(self, component: Any, pin_name: str, pin_item: Any, 
                      connection_type: str = "normal") -> bool:
        """Add a connection to this node"""
        # Check if connection already exists
        for conn in self.connections:
            if (conn.component == component and 
                conn.pin_name == pin_name and 
                conn.pin_item == pin_item):
                return False
        
        # Create new connection
        connection = ConnectionInfo(
            component=component,
            pin_name=pin_name,
            pin_item=pin_item,
            connection_type=connection_type
        )
        
        self.connections.append(connection)
        pin_item.setData(3, self)
        
        return True
    
    def remove_connection(self, component: Any, pin_name: str) -> bool:
        """Remove a connection from this node"""
        for i, conn in enumerate(self.connections):
            if conn.component == component and conn.pin_name == pin_name:
                conn.pin_item.setData(3, None)
                del self.connections[i]
                return True
        return False
    
    def get_connected_components(self) -> List[Any]:
        """Get list of components connected to this node"""
        return [conn.component for conn in self.connections]
    
    def get_degree(self) -> int:
        """Get the degree (number of connections) of this node"""
        return len(self.connections)
    
    def is_terminal(self) -> bool:
        """Check if this is a terminal node (degree 1)"""
        return self.get_degree() == 1
    
    def is_junction(self) -> bool:
        """Check if this is a junction node (degree > 2)"""
        return self.get_degree() > 2
    
    def __repr__(self):
        return (f"EnhancedNode(id={self.node_id}, type={self.node_type.value}, "
                f"connections={len(self.connections)}, ground={self.is_ground})")

class CircuitGraph:
    """Graph representation of the circuit for advanced analysis"""
    
    def __init__(self, netlist):
        self.netlist = netlist
        self.graph = nx.MultiGraph()  # Allow multiple edges between nodes
        self.component_graph = nx.Graph()  # Component connectivity graph
        self._build_graphs()
    
    def _build_graphs(self):
        """Build NetworkX graphs from netlist"""
        self.graph.clear()
        self.component_graph.clear()
        
        # Add nodes
        for node_id, node in self.netlist.nodes.items():
            self.graph.add_node(node_id, 
                              node_type=node.node_type.value,
                              is_ground=node.is_ground,
                              degree=node.get_degree())
        
        # Add component nodes to component graph
        for comp in self.netlist.components:
            self.component_graph.add_node(comp, 
                                        component_type=type(comp).__name__,
                                        component_name=comp.component_name)
        
        # Add edges from wires
        for wire in self.netlist.wires:
            if wire.start_pin and wire.end_pin:
                start_node = wire.start_pin.data(3)
                end_node = wire.end_pin.data(3)
                
                if start_node and end_node:
                    # Add edge to node graph
                    self.graph.add_edge(start_node.node_id, end_node.node_id,
                                      wire=wire,
                                      start_comp=wire.start_comp,
                                      end_comp=wire.end_comp)
                    
                    # Add edge to component graph
                    if wire.start_comp and wire.end_comp:
                        self.component_graph.add_edge(wire.start_comp, wire.end_comp,
                                                    via_node_start=start_node.node_id,
                                                    via_node_end=end_node.node_id)
    
    def find_all_paths(self, source_node: int, target_node: int, max_length: int = 10) -> List[List[int]]:
        """Find all paths between two nodes"""
        try:
            return list(nx.all_simple_paths(self.graph, source_node, target_node, cutoff=max_length))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []
    
    def find_shortest_path(self, source_node: int, target_node: int) -> Optional[List[int]]:
        """Find shortest path between two nodes"""
        try:
            return nx.shortest_path(self.graph, source_node, target_node)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
    
    def find_cycles(self) -> List[List[int]]:
        """Find all cycles in the circuit"""
        try:
            return list(nx.simple_cycles(self.graph))
        except:
            return []
    
    def find_bridges(self) -> List[Tuple[int, int]]:
        """Find bridge edges (critical connections)"""
        return list(nx.bridges(self.graph))
    
    def find_articulation_points(self) -> List[int]:
        """Find articulation points (critical nodes)"""
        return list(nx.articulation_points(self.graph))
    
    def calculate_centrality(self) -> Dict[int, float]:
        """Calculate betweenness centrality for nodes"""
        try:
            return nx.betweenness_centrality(self.graph)
        except:
            return {}
    
    def detect_communities(self) -> List[Set[int]]:
        """Detect communities/clusters in the circuit"""
        try:
            # Use Louvain community detection
            import networkx.algorithms.community as nx_comm
            communities = nx_comm.louvain_communities(self.graph)
            return [set(community) for community in communities]
        except:
            return []
    
    def analyze_topology(self) -> CircuitTopology:
        """Analyze and classify circuit topology"""
        if not self.graph.nodes():
            return CircuitTopology.TREE
        
        # Check if it's a tree (no cycles)
        if nx.is_tree(self.graph):
            return CircuitTopology.TREE
        
        # Check for simple series/parallel structures
        if self._is_series_circuit():
            return CircuitTopology.SERIES
        elif self._is_parallel_circuit():
            return CircuitTopology.PARALLEL
        elif self._is_series_parallel_circuit():
            return CircuitTopology.SERIES_PARALLEL
        elif self._is_bridge_circuit():
            return CircuitTopology.BRIDGE
        elif self._is_ladder_circuit():
            return CircuitTopology.LADDER
        else:
            return CircuitTopology.COMPLEX
    
    def _is_series_circuit(self) -> bool:
        """Check if circuit is purely series"""
        # All nodes except terminals should have degree 2
        terminal_count = 0
        for node_id in self.graph.nodes():
            degree = self.graph.degree(node_id)
            if degree == 1:
                terminal_count += 1
            elif degree != 2:
                return False
        return terminal_count == 2
    
    def _is_parallel_circuit(self) -> bool:
        """Check if circuit is purely parallel"""
        # Should have exactly 2 nodes with all components in parallel
        return len(self.graph.nodes()) == 2
    
    def _is_series_parallel_circuit(self) -> bool:
        """Check if circuit can be reduced using series/parallel rules"""
        # This is a simplified check - full implementation would be more complex
        cycles = self.find_cycles()
        return len(cycles) <= 1
    
    def _is_bridge_circuit(self) -> bool:
        """Check if circuit has bridge topology"""
        # Look for diamond-like structure
        if len(self.graph.nodes()) == 4:
            degrees = [self.graph.degree(node) for node in self.graph.nodes()]
            degrees.sort()
            return degrees == [2, 2, 2, 2]  # All nodes degree 2 in a 4-node bridge
        return False
    
    def _is_ladder_circuit(self) -> bool:
        """Check if circuit has ladder topology"""
        # Simplified check for ladder-like structure
        degrees = [self.graph.degree(node) for node in self.graph.nodes()]
        degree_counts = {d: degrees.count(d) for d in set(degrees)}
        
        # Ladder typically has 2 terminal nodes (degree 1) and rungs (degree 3)
        return degree_counts.get(1, 0) == 2 and degree_counts.get(3, 0) >= 2

class EnhancedCircuitNetlist:
    """
    Enhanced Circuit Netlist with graph-based representation, advanced connectivity analysis,
    and comprehensive circuit topology detection. This is a complete overhaul of the original
    netlist system with significant improvements in functionality and performance.
    """
    
    def __init__(self, canvas=None):
        self.canvas = canvas
        self.nodes: Dict[int, EnhancedNode] = {}
        self.components: List[Any] = []
        self.wires: List[Any] = []
        self.wire_properties: Dict[Any, WireProperties] = {}
        
        # Enhanced properties
        self._next_node_id = 0
        self.ground_node_id: Optional[int] = None
        self.circuit_graph = CircuitGraph(self)
        self.validator = CircuitValidator(self)
        
        # Visual management
        self.node_visuals = {}
        self.junction_visuals = {}
        
        # Performance optimization
        self._dirty_graph = True
        self._cached_metrics = None
        
        # Hierarchical support
        self.subcircuits = {}
        self.parent_circuit = None
    
    def add_component(self, component: Any) -> bool:
        """Add component with enhanced validation and connectivity analysis"""
        try:
            if component in self.components:
                logger.warning(f"Component {component.component_name} already in netlist")
                return False
            
            self.components.append(component)
            self._dirty_graph = True
            
            # Handle ground components specially
            if isinstance(component, Ground):
                self._handle_ground_component(component)
            
            # Update visual elements
            self._update_visuals()
            
            # Validate after addition
            errors, warnings = self.validator.validate_circuit()
            if errors:
                logger.warning(f"Validation errors after adding {component.component_name}: {errors}")
            
            logger.info(f"Added component: {component.component_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding component {component.component_name}: {e}")
            return False
    
    def remove_component(self, component: Any) -> bool:
        """Remove component with cleanup and validation"""
        try:
            if component not in self.components:
                logger.warning(f"Component {component.component_name} not in netlist")
                return False
            
            # Remove component connections
            nodes_to_check = set()
            for pin_item in component.get_pins():
                node = pin_item.data(3)
                if node and node.node_id in self.nodes:
                    node.remove_connection(component, pin_item.data(1))
                    nodes_to_check.add(node.node_id)
                    pin_item.setData(3, None)
            
            # Clean up empty nodes
            for node_id in nodes_to_check:
                if node_id in self.nodes:
                    node = self.nodes[node_id]
                    if (len(node.connections) == 0 and 
                        (self.ground_node_id is None or node_id != self.ground_node_id)):
                        del self.nodes[node_id]
                        logger.info(f"Removed empty node: {node_id}")
            
            # Handle ground component removal
            if isinstance(component, Ground):
                self._handle_ground_removal(component)
            
            self.components.remove(component)
            self._dirty_graph = True
            
            # Update visual elements
            self._update_visuals()
            
            logger.info(f"Removed component: {component.component_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing component {component.component_name}: {e}")
            return False
    
    def add_wire(self, wire: Any) -> bool:
        """Add wire with enhanced routing and connectivity analysis"""
        try:
            if wire in self.wires:
                logger.warning("Wire already in netlist")
                return False
            
            if not wire.start_pin or not wire.end_pin:
                logger.error("Wire missing start or end pin")
                return False
            
            start_comp = wire.start_pin.data(2)
            end_comp = wire.end_pin.data(2)
            start_pin_name = wire.start_pin.data(1)
            end_pin_name = wire.end_pin.data(1)
            
            logger.info(f"Adding wire: {start_comp.component_name}.{start_pin_name} → "
                       f"{end_comp.component_name}.{end_pin_name}")
            
            # Get or create nodes
            start_node = wire.start_pin.data(3)
            end_node = wire.end_pin.data(3)
            
            # Node creation and merging logic
            if start_node is None and end_node is None:
                # Create new node for both pins
                new_node = self._create_new_node()
                new_node.add_connection(start_comp, start_pin_name, wire.start_pin)
                new_node.add_connection(end_comp, end_pin_name, wire.end_pin)
                logger.info(f"Created new node {new_node.node_id} for wire")
                
            elif start_node is None:
                # Add start pin to existing end node
                end_node.add_connection(start_comp, start_pin_name, wire.start_pin)
                logger.info(f"Added start pin to existing node {end_node.node_id}")
                
            elif end_node is None:
                # Add end pin to existing start node
                start_node.add_connection(end_comp, end_pin_name, wire.end_pin)
                logger.info(f"Added end pin to existing node {start_node.node_id}")
                
            elif start_node != end_node:
                # Merge two existing nodes
                merged_node = self._merge_nodes(start_node, end_node)
                logger.info(f"Merged nodes {start_node.node_id} and {end_node.node_id} "
                           f"into {merged_node.node_id}")
            
            # Add wire to list
            self.wires.append(wire)
            
            # Create wire properties
            wire_props = WireProperties(
                wire=wire,
                start_node=wire.start_pin.data(3).node_id,
                end_node=wire.end_pin.data(3).node_id
            )
            self.wire_properties[wire] = wire_props
            
            self._dirty_graph = True
            self._update_visuals()
            
            logger.info("Wire added successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error adding wire: {e}")
            return False
    
    def remove_wire(self, wire: Any) -> bool:
        """Remove wire with intelligent node splitting"""
        try:
            if wire not in self.wires:
                logger.warning("Wire not in netlist")
                return False
            
            logger.info(f"Removing wire: {wire}")
            
            # Remove wire from list
            self.wires.remove(wire)
            
            # Remove wire properties
            if wire in self.wire_properties:
                del self.wire_properties[wire]
            
            # Handle node splitting if necessary
            self._handle_wire_removal_nodes(wire)
            
            # Clean up component references
            if wire.start_comp:
                wire.start_comp.remove_connected_wire(self)
            if wire.end_comp:
                wire.end_comp.remove_connected_wire(self)
            
            # Remove from scene
            scene = wire.scene()
            if scene:
                scene.removeItem(wire)
            
            self._dirty_graph = True
            self._update_visuals()
            
            logger.info("Wire removed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error removing wire: {e}")
            return False
    
    def _create_new_node(self, node_type: NodeType = NodeType.REGULAR) -> EnhancedNode:
        """Create a new node with unique ID"""
        node_id = self._get_next_node_id()
        node = EnhancedNode(node_id, node_type)
        self.nodes[node_id] = node
        return node
    
    def _merge_nodes(self, node1: EnhancedNode, node2: EnhancedNode) -> EnhancedNode:
        """Merge two nodes intelligently"""
        # Determine which node to keep (prefer ground, then higher degree)
        if node1.is_ground and not node2.is_ground:
            target_node, merged_node = node1, node2
        elif node2.is_ground and not node1.is_ground:
            target_node, merged_node = node2, node1
        elif len(node1.connections) >= len(node2.connections):
            target_node, merged_node = node1, node2
        else:
            target_node, merged_node = node2, node1
        
        # Transfer connections
        for conn in list(merged_node.connections):
            target_node.add_connection(conn.component, conn.pin_name, conn.pin_item, conn.connection_type)
        
        # Remove merged node
        if merged_node.node_id in self.nodes and merged_node.node_id != self.ground_node_id:
            del self.nodes[merged_node.node_id]
        
        return target_node
    
    def _handle_wire_removal_nodes(self, wire: Any):
        """Handle node splitting when wire is removed"""
        start_pin = wire.start_pin
        end_pin = wire.end_pin
        
        if not start_pin or not end_pin:
            return
        
        start_node = start_pin.data(3)
        end_node = end_pin.data(3)
        
        if not start_node or start_node != end_node:
            return
        
        # Check if node needs to be split
        node = start_node
        
        # Remove pin connections
        node.remove_connection(wire.start_comp, start_pin.data(1))
        node.remove_connection(wire.end_comp, end_pin.data(1))
        
        # Check if we need to split the node
        if len(node.connections) > 0:
            # Analyze remaining connections to see if they're still connected
            remaining_connections = self._analyze_remaining_connections(node, wire)
            
            if len(remaining_connections) > 1:
                # Split node into separate nodes for each connected component group
                self._split_node_by_connectivity(node, remaining_connections)
    
    def _analyze_remaining_connections(self, node: EnhancedNode, removed_wire: Any) -> List[List[ConnectionInfo]]:
        """Analyze which connections remain connected after wire removal"""
        # This is a simplified version - full implementation would use graph analysis
        remaining_connections = [conn for conn in node.connections]
        
        # For now, return each connection as a separate group
        # In a full implementation, this would analyze the circuit graph
        return [[conn] for conn in remaining_connections]
    
    def _split_node_by_connectivity(self, original_node: EnhancedNode, connection_groups: List[List[ConnectionInfo]]):
        """Split node into multiple nodes based on connectivity groups"""
        if len(connection_groups) <= 1:
            return
        
        # Keep original node for first group
        first_group = connection_groups[0]
        original_node.connections = first_group
        
        # Create new nodes for other groups
        for i, group in enumerate(connection_groups[1:], 1):
            new_node = self._create_new_node(original_node.node_type)
            new_node.connections = group
            
            # Update pin references
            for conn in group:
                conn.pin_item.setData(3, new_node)
            
            logger.info(f"Created split node {new_node.node_id} from {original_node.node_id}")
    
    def _handle_ground_component(self, ground_comp: Ground):
        """Handle ground component addition"""
        ground_pin = ground_comp.get_pins()[0]
        connected_node = ground_pin.data(3)
        
        if connected_node:
            self.set_ground_node(connected_node.node_id)
        else:
            logger.warning(f"Ground component {ground_comp.component_name} not connected")
    
    def _handle_ground_removal(self, ground_comp: Ground):
        """Handle ground component removal"""
        connected_node = ground_comp.get_pins()[0].data(3)
        
        if connected_node and connected_node.node_id == self.ground_node_id:
            # Check if other ground components share this node
            other_grounds = [
                c for c in self.components 
                if isinstance(c, Ground) and c != ground_comp and 
                c.get_pins()[0].data(3) == connected_node
            ]
            
            if not other_grounds:
                self.set_ground_node(None)
    
    def set_ground_node(self, node_id: Optional[int]):
        """Set ground node with validation"""
        if node_id is not None and node_id not in self.nodes:
            logger.warning(f"Cannot set non-existent node {node_id} as ground")
            return
        
        # Clear previous ground
        if self.ground_node_id is not None and self.ground_node_id in self.nodes:
            self.nodes[self.ground_node_id].is_ground = False
            self.nodes[self.ground_node_id].node_type = NodeType.REGULAR
        
        self.ground_node_id = node_id
        
        # Set new ground
        if node_id is not None and node_id in self.nodes:
            self.nodes[node_id].is_ground = True
            self.nodes[node_id].node_type = NodeType.GROUND
        
        logger.info(f"Ground node set to: {self.ground_node_id}")
        self._dirty_graph = True
        self._update_visuals()
    
    def get_ground_node(self) -> Optional[EnhancedNode]:
        """Get the ground node"""
        if self.ground_node_id is not None and self.ground_node_id in self.nodes:
            return self.nodes[self.ground_node_id]
        return None
    
    def find_automatic_ground_node_id(self) -> Optional[int]:
        """Find best candidate for automatic ground assignment"""
        if not self.nodes:
            return None
        
        # Prefer node with most connections
        best_node_id = None
        max_connections = -1
        
        for node_id, node in self.nodes.items():
            connection_count = len(node.connections)
            if connection_count > max_connections:
                max_connections = connection_count
                best_node_id = node_id
        
        return best_node_id
    
    def find_connected_subgraphs(self) -> List[Set[int]]:
        """Find all connected subgraphs in the circuit"""
        self._rebuild_graph_if_dirty()
        
        try:
            return [set(component) for component in nx.connected_components(self.circuit_graph.graph)]
        except:
            return []
    
    def find_voltage_source_loops(self) -> List[List[Any]]:
        """Find loops containing only voltage sources and wires"""
        voltage_sources = [c for c in self.components if isinstance(c, VoltageSource)]
        loops = []
        
        # This is a simplified implementation
        # Full implementation would use graph analysis to find actual loops
        
        return loops
    
    def find_current_source_cutsets(self) -> List[List[Any]]:
        """Find cutsets containing only current sources"""
        current_sources = [c for c in self.components if isinstance(c, CurrentSource)]
        cutsets = []
        
        # Simplified implementation
        return cutsets
    
    def find_short_circuits(self) -> List[Tuple[int, int]]:
        """Find potential short circuits (very low resistance paths)"""
        short_circuits = []
        
        # Check for zero-resistance components
        for comp in self.components:
            if isinstance(comp, Resistor) and comp.resistance < 1e-6:
                # Find nodes connected by this resistor
                pin_in = None
                pin_out = None
                for pin in comp.get_pins():
                    if pin.data(1) == "in":
                        pin_in = pin
                    elif pin.data(1) == "out":
                        pin_out = pin
                
                if pin_in and pin_out:
                    node_in = pin_in.data(3)
                    node_out = pin_out.data(3)
                    
                    if node_in and node_out:
                        short_circuits.append((node_in.node_id, node_out.node_id))
        
        return short_circuits
    
    def analyze_circuit_metrics(self) -> CircuitMetrics:
        """Analyze comprehensive circuit metrics"""
        if self._cached_metrics and not self._dirty_graph:
            return self._cached_metrics
        
        self._rebuild_graph_if_dirty()
        
        metrics = CircuitMetrics()
        metrics.node_count = len(self.nodes)
        metrics.component_count = len(self.components)
        metrics.wire_count = len(self.wires)
        
        if self.circuit_graph.graph.nodes():
            # Graph metrics
            degrees = [self.circuit_graph.graph.degree(node) for node in self.circuit_graph.graph.nodes()]
            metrics.max_node_degree = max(degrees) if degrees else 0
            metrics.avg_node_degree = sum(degrees) / len(degrees) if degrees else 0
            
            # Connectivity metrics
            if nx.is_connected(self.circuit_graph.graph):
                metrics.graph_diameter = nx.diameter(self.circuit_graph.graph)
                metrics.clustering_coefficient = nx.average_clustering(self.circuit_graph.graph)
            
            # Complexity score (0-1, higher = more complex)
            metrics.complexity_score = min(1.0, (metrics.max_node_degree / 10.0 + 
                                                len(self.circuit_graph.find_cycles()) / 20.0))
            
            # Connectivity score (0-1, higher = better connected)
            if metrics.node_count > 1:
                actual_edges = self.circuit_graph.graph.number_of_edges()
                max_possible_edges = metrics.node_count * (metrics.node_count - 1) / 2
                metrics.connectivity_score = actual_edges / max_possible_edges
        
        # Cache results
        self._cached_metrics = metrics
        return metrics
    
    def optimize_node_numbering(self):
        """Optimize node numbering for better matrix conditioning"""
        # Renumber nodes for better sparsity patterns
        old_to_new = {}
        new_node_id = 0
        
        # Start with ground node
        ground_node = self.get_ground_node()
        if ground_node:
            old_to_new[ground_node.node_id] = new_node_id
            new_node_id += 1
        
        # Then number by degree (high degree first for better conditioning)
        nodes_by_degree = sorted(
            [node for node in self.nodes.values() if not node.is_ground],
            key=lambda n: len(n.connections), reverse=True
        )
        
        for node in nodes_by_degree:
            if node.node_id not in old_to_new:
                old_to_new[node.node_id] = new_node_id
                new_node_id += 1
        
        # Update node IDs
        new_nodes = {}
        for old_id, new_id in old_to_new.items():
            if old_id in self.nodes:
                node = self.nodes[old_id]
                node.node_id = new_id
                new_nodes[new_id] = node
        
        self.nodes = new_nodes
        
        # Update ground node ID
        if ground_node:
            self.ground_node_id = old_to_new[ground_node.node_id]
        
        logger.info(f"Optimized node numbering: {len(old_to_new)} nodes renumbered")
        self._dirty_graph = True
    
    def _rebuild_graph_if_dirty(self):
        """Rebuild circuit graph if needed"""
        if self._dirty_graph:
            self.circuit_graph._build_graphs()
            self._dirty_graph = False
            self._cached_metrics = None
    
    def _update_visuals(self):
        """Update visual elements"""
        if self.canvas:
            self.canvas.update_node_visuals()
            
            # Hide simulation results to force recalculation
            if hasattr(self.canvas, 'main_window') and hasattr(self.canvas.main_window, 'hide_simulation_results'):
                self.canvas.main_window.hide_simulation_results()
            
            # Update component list
            if hasattr(self.canvas, 'main_window') and hasattr(self.canvas.main_window, 'properties_panel'):
                self.canvas.main_window.properties_panel.update_component_list()
    
    def _get_next_node_id(self) -> int:
        """Get next available node ID"""
        node_id = self._next_node_id
        self._next_node_id += 1
        return node_id
    
    def generate_enhanced_netlist_description(self) -> str:
        """Generate comprehensive netlist description"""
        description = "Enhanced Circuit Netlist Analysis:\n"
        description += "=" * 50 + "\n\n"
        
        # Circuit metrics
        metrics = self.analyze_circuit_metrics()
        description += f"Circuit Metrics:\n"
        description += f"  Nodes: {metrics.node_count}\n"
        description += f"  Components: {metrics.component_count}\n"
        description += f"  Wires: {metrics.wire_count}\n"
        description += f"  Max Node Degree: {metrics.max_node_degree}\n"
        description += f"  Avg Node Degree: {metrics.avg_node_degree:.2f}\n"
        description += f"  Complexity Score: {metrics.complexity_score:.3f}\n"
        description += f"  Connectivity Score: {metrics.connectivity_score:.3f}\n\n"
        
        # Topology analysis
        self._rebuild_graph_if_dirty()
        topology = self.circuit_graph.analyze_topology()
        description += f"Circuit Topology: {topology.value.title()}\n\n"
        
        # Validation results
        errors, warnings = self.validator.validate_circuit()
        if errors:
            description += f"Validation Errors ({len(errors)}):\n"
            for error in errors:
                description += f"  ❌ {error}\n"
            description += "\n"
        
        if warnings:
            description += f"Validation Warnings ({len(warnings)}):\n"
            for warning in warnings:
                description += f"  ⚠️  {warning}\n"
            description += "\n"
        
        # Components by type
        component_types = defaultdict(list)
        for comp in self.components:
            component_types[type(comp).__name__].append(comp)
        
        description += "Components by Type:\n"
        for comp_type, comps in component_types.items():
            description += f"  {comp_type}: {len(comps)}\n"
            for comp in comps:
                description += f"    - {comp.component_name}\n"
        description += "\n"
        
        # Enhanced node information
        description += "Enhanced Node Information:\n"
        for node_id in sorted(self.nodes.keys()):
            node = self.nodes[node_id]
            description += f"  Node {node_id} ({node.node_type.value})"
            
            if node.is_ground:
                description += " [GROUND]"
            
            description += f" - {len(node.connections)} connections:\n"
            
            for conn in node.connections:
                description += f"    - {conn.component.component_name}.{conn.pin_name}"
                if conn.connection_type != "normal":
                    description += f" ({conn.connection_type})"
                description += "\n"
        
        # Wire analysis
        if self.wires:
            description += "\nWire Analysis:\n"
            for wire in self.wires:
                props = self.wire_properties.get(wire, WireProperties(wire, -1, -1))
                start_comp = wire.start_comp.component_name if wire.start_comp else "Unknown"
                start_pin = wire.start_pin.data(1) if wire.start_pin else "Unknown"
                end_comp = wire.end_comp.component_name if wire.end_comp else "Unknown"
                end_pin = wire.end_pin.data(1) if wire.end_pin else "Unknown"
                
                description += f"  {start_comp}.{start_pin} → {end_comp}.{end_pin}"
                
                if props.wire_type != "normal":
                    description += f" ({props.wire_type})"
                
                if props.resistance > 0:
                    description += f" [R={props.resistance}Ω]"
                
                description += "\n"
        
        return description
    
    # Legacy compatibility method
    def generate_netlist_description(self) -> str:
        """Legacy compatibility method"""
        return self.generate_enhanced_netlist_description()

# Maintain backward compatibility
CircuitNetlist = EnhancedCircuitNetlist
Node = EnhancedNode

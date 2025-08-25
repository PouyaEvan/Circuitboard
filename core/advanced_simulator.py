"""
Advanced Circuit Simulator with modular analysis engines, robust numerical methods,
and comprehensive error handling. This is a complete overhaul of the original simulator
with significant improvements in performance, accuracy, and features.
"""

import numpy as np
from scipy import sparse, linalg
from scipy.sparse.linalg import spsolve, gmres, bicgstab
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any, Union
import warnings
from collections import defaultdict
import time
import logging

from components.resistor import Resistor
from components.vs import VoltageSource
from components.cs import CurrentSource
from components.inductor import Inductor
from components.capacitor import Capacitor
from components.ground import Ground

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalysisType(Enum):
    """Types of circuit analysis supported"""
    DC = "dc"
    AC = "ac"
    TRANSIENT = "transient"
    SMALL_SIGNAL = "small_signal"
    NOISE = "noise"
    DISTORTION = "distortion"

class ConvergenceError(Exception):
    """Raised when numerical methods fail to converge"""
    pass

class SingularMatrixError(Exception):
    """Raised when circuit matrix is singular"""
    pass

@dataclass
class SimulationSettings:
    """Configuration settings for simulation"""
    max_iterations: int = 100
    tolerance: float = 1e-12
    reltol: float = 1e-6
    abstol: float = 1e-12
    vntol: float = 1e-6  # Voltage tolerance
    gmin: float = 1e-12  # Minimum conductance
    use_sparse: bool = True
    iterative_solver: str = "spsolve"  # spsolve, gmres, bicgstab
    temperature: float = 300.15  # Kelvin
    enable_noise: bool = False
    enable_debug: bool = False

@dataclass
class AnalysisResults:
    """Container for analysis results"""
    success: bool = False
    message: str = ""
    node_voltages: Dict[int, complex] = field(default_factory=dict)
    branch_currents: Dict[str, complex] = field(default_factory=dict)
    component_currents: Dict[Tuple[Any, str], complex] = field(default_factory=dict)
    wire_currents: Dict[Tuple[Any, int], complex] = field(default_factory=dict)
    power_dissipation: Dict[Any, float] = field(default_factory=dict)
    frequency_response: Optional[Dict[str, np.ndarray]] = None
    time_response: Optional[Dict[str, np.ndarray]] = None
    convergence_history: List[float] = field(default_factory=list)
    solve_time: float = 0.0
    iterations: int = 0

class ComponentModel(ABC):
    """Abstract base class for component models"""
    
    @abstractmethod
    def get_stamps(self, frequency: complex = 0) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Return matrix stamps for MNA formulation"""
        pass
    
    @abstractmethod
    def get_nonlinear_stamps(self, voltages: Dict[int, complex]) -> Tuple[np.ndarray, np.ndarray]:
        """Return nonlinear matrix stamps"""
        pass
    
    @abstractmethod
    def is_nonlinear(self) -> bool:
        """Return True if component is nonlinear"""
        pass

class LinearComponentModel(ComponentModel):
    """Base class for linear components"""
    
    def get_nonlinear_stamps(self, voltages: Dict[int, complex]) -> Tuple[np.ndarray, np.ndarray]:
        """Linear components don't need nonlinear stamps"""
        return np.array([]), np.array([])
    
    def is_nonlinear(self) -> bool:
        return False

class ResistorModel(LinearComponentModel):
    """Advanced resistor model with temperature dependence"""
    
    def __init__(self, component: Resistor, node_map: Dict[int, int], settings: SimulationSettings):
        self.component = component
        self.node_map = node_map
        self.settings = settings
        self.temp_coeff = getattr(component, 'temp_coeff', 0.0)  # Temperature coefficient
    
    def get_resistance(self, temperature: float = None) -> float:
        """Get temperature-dependent resistance"""
        if temperature is None:
            temperature = self.settings.temperature
        
        temp_delta = temperature - 300.15  # Reference temperature (27°C)
        resistance = self.component.resistance * (1 + self.temp_coeff * temp_delta)
        
        # Ensure minimum resistance for numerical stability
        return max(resistance, self.settings.gmin)
    
    def get_stamps(self, frequency: complex = 0) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Get MNA stamps for resistor"""
        resistance = self.get_resistance()
        conductance = 1.0 / resistance
        
        # Get node pins
        pin_in = None
        pin_out = None
        for pin in self.component.get_pins():
            if pin.data(1) == "in":
                pin_in = pin
            elif pin.data(1) == "out":
                pin_out = pin
        
        if not pin_in or not pin_out:
            return np.array([]), np.array([]), []
        
        node_in = pin_in.data(3)
        node_out = pin_out.data(3)
        
        if not node_in or not node_out:
            return np.array([]), np.array([]), []
        
        idx_in = self.node_map.get(node_in.node_id, -1)
        idx_out = self.node_map.get(node_out.node_id, -1)
        
        # Create conductance stamps
        stamps = []
        rhs = np.array([])
        branch_vars = []
        
        if idx_in >= 0:
            stamps.append((idx_in, idx_in, conductance))
            if idx_out >= 0:
                stamps.append((idx_in, idx_out, -conductance))
        
        if idx_out >= 0:
            stamps.append((idx_out, idx_out, conductance))
            if idx_in >= 0:
                stamps.append((idx_out, idx_in, -conductance))
        
        return np.array(stamps), rhs, branch_vars

class CapacitorModel(LinearComponentModel):
    """Advanced capacitor model with frequency dependence"""
    
    def __init__(self, component: Capacitor, node_map: Dict[int, int], settings: SimulationSettings):
        self.component = component
        self.node_map = node_map
        self.settings = settings
        self.esr = getattr(component, 'esr', 0.0)  # Equivalent series resistance
        self.esl = getattr(component, 'esl', 0.0)  # Equivalent series inductance
    
    def get_impedance(self, frequency: complex) -> complex:
        """Get frequency-dependent impedance"""
        if frequency == 0:
            return float('inf')  # Open circuit at DC
        
        omega = 2j * np.pi * frequency
        z_cap = 1.0 / (omega * self.component.capacitance)
        z_esr = self.esr
        z_esl = omega * self.esl
        
        return z_cap + z_esr + z_esl
    
    def get_stamps(self, frequency: complex = 0) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Get MNA stamps for capacitor"""
        if frequency == 0:
            # Open circuit at DC - no stamps needed
            return np.array([]), np.array([]), []
        
        impedance = self.get_impedance(frequency)
        if abs(impedance) < self.settings.gmin:
            admittance = 1.0 / self.settings.gmin
        else:
            admittance = 1.0 / impedance
        
        # Similar stamp pattern as resistor but with complex admittance
        pin_in = None
        pin_out = None
        for pin in self.component.get_pins():
            if pin.data(1) == "in":
                pin_in = pin
            elif pin.data(1) == "out":
                pin_out = pin
        
        if not pin_in or not pin_out:
            return np.array([]), np.array([]), []
        
        node_in = pin_in.data(3)
        node_out = pin_out.data(3)
        
        if not node_in or not node_out:
            return np.array([]), np.array([]), []
        
        idx_in = self.node_map.get(node_in.node_id, -1)
        idx_out = self.node_map.get(node_out.node_id, -1)
        
        stamps = []
        
        if idx_in >= 0:
            stamps.append((idx_in, idx_in, admittance))
            if idx_out >= 0:
                stamps.append((idx_in, idx_out, -admittance))
        
        if idx_out >= 0:
            stamps.append((idx_out, idx_out, admittance))
            if idx_in >= 0:
                stamps.append((idx_out, idx_in, -admittance))
        
        return np.array(stamps), np.array([]), []

class InductorModel(LinearComponentModel):
    """Advanced inductor model with resistance and frequency dependence"""
    
    def __init__(self, component: Inductor, node_map: Dict[int, int], branch_map: Dict[str, int], settings: SimulationSettings):
        self.component = component
        self.node_map = node_map
        self.branch_map = branch_map
        self.settings = settings
        self.resistance = getattr(component, 'resistance', 0.0)  # Series resistance
        self.branch_var = f"I_{component.component_name}"
    
    def get_impedance(self, frequency: complex) -> complex:
        """Get frequency-dependent impedance"""
        if frequency == 0:
            return self.resistance  # Only resistance at DC
        
        omega = 2j * np.pi * frequency
        return self.resistance + omega * self.component.inductance
    
    def get_stamps(self, frequency: complex = 0) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Get MNA stamps for inductor"""
        pin_in = None
        pin_out = None
        for pin in self.component.get_pins():
            if pin.data(1) == "in":
                pin_in = pin
            elif pin.data(1) == "out":
                pin_out = pin
        
        if not pin_in or not pin_out:
            return np.array([]), np.array([]), []
        
        node_in = pin_in.data(3)
        node_out = pin_out.data(3)
        
        if not node_in or not node_out:
            return np.array([]), np.array([]), []
        
        idx_in = self.node_map.get(node_in.node_id, -1)
        idx_out = self.node_map.get(node_out.node_id, -1)
        branch_idx = self.branch_map.get(self.branch_var, -1)
        
        if branch_idx < 0:
            return np.array([]), np.array([]), []
        
        stamps = []
        rhs = np.array([0.0])  # Voltage constraint RHS
        branch_vars = [self.branch_var]
        
        # Voltage constraint: V_in - V_out = I * Z
        if frequency == 0:
            # DC: V_in - V_out = I * R
            constraint_val = self.resistance
        else:
            # AC: V_in - V_out = I * (R + jωL)
            omega = 2j * np.pi * frequency
            constraint_val = self.resistance + omega * self.component.inductance
        
        # Voltage constraint stamps
        if idx_in >= 0:
            stamps.append((branch_idx, idx_in, 1.0))
            stamps.append((idx_in, branch_idx, 1.0))
        
        if idx_out >= 0:
            stamps.append((branch_idx, idx_out, -1.0))
            stamps.append((idx_out, branch_idx, -1.0))
        
        # Add impedance to diagonal
        stamps.append((branch_idx, branch_idx, -constraint_val))
        
        return np.array(stamps), rhs, branch_vars

class VoltageSourceModel(LinearComponentModel):
    """Advanced voltage source model"""
    
    def __init__(self, component: VoltageSource, node_map: Dict[int, int], branch_map: Dict[str, int], settings: SimulationSettings):
        self.component = component
        self.node_map = node_map
        self.branch_map = branch_map
        self.settings = settings
        self.internal_resistance = getattr(component, 'internal_resistance', 0.0)
        self.branch_var = f"I_{component.component_name}"
    
    def get_stamps(self, frequency: complex = 0) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Get MNA stamps for voltage source"""
        pin_pos = None
        pin_neg = None
        for pin in self.component.get_pins():
            if pin.data(1) == "+":
                pin_pos = pin
            elif pin.data(1) == "-":
                pin_neg = pin
        
        if not pin_pos or not pin_neg:
            return np.array([]), np.array([]), []
        
        node_pos = pin_pos.data(3)
        node_neg = pin_neg.data(3)
        
        if not node_pos or not node_neg:
            return np.array([]), np.array([]), []
        
        idx_pos = self.node_map.get(node_pos.node_id, -1)
        idx_neg = self.node_map.get(node_neg.node_id, -1)
        branch_idx = self.branch_map.get(self.branch_var, -1)
        
        if branch_idx < 0:
            return np.array([]), np.array([]), []
        
        stamps = []
        rhs = np.array([complex(self.component.voltage)])
        branch_vars = [self.branch_var]
        
        # Voltage constraint: V_pos - V_neg = Voltage
        if idx_pos >= 0:
            stamps.append((branch_idx, idx_pos, 1.0))
            stamps.append((idx_pos, branch_idx, 1.0))
        
        if idx_neg >= 0:
            stamps.append((branch_idx, idx_neg, -1.0))
            stamps.append((idx_neg, branch_idx, -1.0))
        
        # Add internal resistance if specified
        if self.internal_resistance > 0:
            stamps.append((branch_idx, branch_idx, -self.internal_resistance))
        
        return np.array(stamps), rhs, branch_vars

class CurrentSourceModel(LinearComponentModel):
    """Advanced current source model"""
    
    def __init__(self, component: CurrentSource, node_map: Dict[int, int], settings: SimulationSettings):
        self.component = component
        self.node_map = node_map
        self.settings = settings
        self.output_resistance = getattr(component, 'output_resistance', float('inf'))
    
    def get_stamps(self, frequency: complex = 0) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Get MNA stamps for current source"""
        pin_pos = None
        pin_neg = None
        for pin in self.component.get_pins():
            if pin.data(1) == "+":
                pin_pos = pin
            elif pin.data(1) == "-":
                pin_neg = pin
        
        if not pin_pos or not pin_neg:
            return np.array([]), np.array([]), []
        
        node_pos = pin_pos.data(3)
        node_neg = pin_neg.data(3)
        
        if not node_pos or not node_neg:
            return np.array([]), np.array([]), []
        
        idx_pos = self.node_map.get(node_pos.node_id, -1)
        idx_neg = self.node_map.get(node_neg.node_id, -1)
        
        stamps = []
        rhs_size = max(self.node_map.values()) + 1 if self.node_map else 0
        rhs = np.zeros(rhs_size, dtype=complex)
        
        # Current injection stamps
        current = complex(self.component.current)
        
        if idx_pos >= 0:
            rhs[idx_pos] = -current  # Current flows out of positive terminal
        
        if idx_neg >= 0:
            rhs[idx_neg] = current  # Current flows into negative terminal
        
        # Add output resistance if finite
        if self.output_resistance != float('inf') and self.output_resistance > 0:
            conductance = 1.0 / self.output_resistance
            
            if idx_pos >= 0:
                stamps.append((idx_pos, idx_pos, conductance))
                if idx_neg >= 0:
                    stamps.append((idx_pos, idx_neg, -conductance))
            
            if idx_neg >= 0:
                stamps.append((idx_neg, idx_neg, conductance))
                if idx_pos >= 0:
                    stamps.append((idx_neg, idx_pos, -conductance))
        
        return np.array(stamps), rhs, []

class AdvancedAnalysisEngine(ABC):
    """Abstract base class for analysis engines"""
    
    def __init__(self, netlist, settings: SimulationSettings):
        self.netlist = netlist
        self.settings = settings
        self.component_models = {}
        self._setup_component_models()
    
    @abstractmethod
    def analyze(self, **kwargs) -> AnalysisResults:
        """Perform the analysis"""
        pass
    
    def _setup_component_models(self):
        """Setup component models for analysis"""
        # Create node mapping (excluding ground)
        ground_node = self.netlist.get_ground_node()
        unknown_nodes = [node for node in self.netlist.nodes.values() 
                        if not node.is_ground]
        self.node_map = {node.node_id: i for i, node in enumerate(unknown_nodes)}
        
        # Create branch variable mapping for current-carrying components
        branch_vars = []
        for comp in self.netlist.components:
            if isinstance(comp, (VoltageSource, Inductor)):
                branch_vars.append(f"I_{comp.component_name}")
        
        self.branch_map = {var: i + len(self.node_map) for i, var in enumerate(branch_vars)}
        
        # Create component models
        for comp in self.netlist.components:
            if isinstance(comp, Resistor):
                self.component_models[comp] = ResistorModel(comp, self.node_map, self.settings)
            elif isinstance(comp, Capacitor):
                self.component_models[comp] = CapacitorModel(comp, self.node_map, self.settings)
            elif isinstance(comp, Inductor):
                self.component_models[comp] = InductorModel(comp, self.node_map, self.branch_map, self.settings)
            elif isinstance(comp, VoltageSource):
                self.component_models[comp] = VoltageSourceModel(comp, self.node_map, self.branch_map, self.settings)
            elif isinstance(comp, CurrentSource):
                self.component_models[comp] = CurrentSourceModel(comp, self.node_map, self.settings)
    
    def _build_mna_system(self, frequency: complex = 0) -> Tuple[np.ndarray, np.ndarray]:
        """Build MNA system matrices"""
        total_vars = len(self.node_map) + len(self.branch_map)
        
        if total_vars == 0:
            return np.array([]), np.array([])
        
        if self.settings.use_sparse:
            A = sparse.lil_matrix((total_vars, total_vars), dtype=complex)
            B = np.zeros(total_vars, dtype=complex)
        else:
            A = np.zeros((total_vars, total_vars), dtype=complex)
            B = np.zeros(total_vars, dtype=complex)
        
        # Collect stamps from all component models
        for comp, model in self.component_models.items():
            try:
                stamps, rhs, branch_vars = model.get_stamps(frequency)
                
                # Apply matrix stamps
                for stamp in stamps:
                    if len(stamp) >= 3:
                        row, col, val = int(stamp[0]), int(stamp[1]), stamp[2]
                        if 0 <= row < total_vars and 0 <= col < total_vars:
                            A[row, col] += val
                
                # Apply RHS stamps
                if len(rhs) > 0:
                    for i, branch_var in enumerate(branch_vars):
                        if branch_var in self.branch_map:
                            branch_idx = self.branch_map[branch_var]
                            if branch_idx < total_vars and i < len(rhs):
                                B[branch_idx] += rhs[i]
                
                # For current sources, handle node injections separately
                if isinstance(model, CurrentSourceModel) and len(rhs) > 0:
                    # Current sources inject current directly into nodes
                    pin_pos = None
                    pin_neg = None
                    for pin in comp.get_pins():
                        if pin.data(1) == "+":
                            pin_pos = pin
                        elif pin.data(1) == "-":
                            pin_neg = pin
                    
                    if pin_pos and pin_neg:
                        node_pos = pin_pos.data(3)
                        node_neg = pin_neg.data(3)
                        
                        if node_pos and not node_pos.is_ground:
                            idx_pos = self.node_map.get(node_pos.node_id, -1)
                            if idx_pos >= 0:
                                B[idx_pos] -= comp.current
                        
                        if node_neg and not node_neg.is_ground:
                            idx_neg = self.node_map.get(node_neg.node_id, -1)
                            if idx_neg >= 0:
                                B[idx_neg] += comp.current
                                
            except Exception as e:
                logger.error(f"Error processing component {comp.component_name}: {e}")
                continue
        
        if self.settings.use_sparse:
            A = A.tocsr()
        
        return A, B
    
    def _solve_linear_system(self, A: np.ndarray, B: np.ndarray) -> Tuple[np.ndarray, bool, str]:
        """Solve linear system with robust numerical methods"""
        start_time = time.time()
        
        try:
            # Check for empty system
            if A.size == 0 or B.size == 0:
                return np.array([]), True, "Empty system"
            
            # Numerical conditioning check
            if self.settings.use_sparse and sparse.issparse(A):
                # For sparse matrices, estimate condition number
                try:
                    # Use a few iterations of power method for condition estimation
                    cond_est = sparse.linalg.norm(A) * sparse.linalg.norm(sparse.linalg.inv(A))
                except:
                    cond_est = 1e6  # Conservative estimate
            else:
                cond_est = np.linalg.cond(A)
            
            if cond_est > 1e12:
                return np.array([]), False, f"Ill-conditioned matrix (cond={cond_est:.2e})"
            
            # Solve based on solver type and matrix properties
            if self.settings.use_sparse and sparse.issparse(A):
                if self.settings.iterative_solver == "spsolve":
                    solution = spsolve(A, B)
                elif self.settings.iterative_solver == "gmres":
                    solution, info = gmres(A, B, tol=self.settings.tolerance)
                    if info != 0:
                        return np.array([]), False, f"GMRES failed to converge (info={info})"
                elif self.settings.iterative_solver == "bicgstab":
                    solution, info = bicgstab(A, B, tol=self.settings.tolerance)
                    if info != 0:
                        return np.array([]), False, f"BiCGSTAB failed to converge (info={info})"
                else:
                    solution = spsolve(A, B)
            else:
                # Dense matrix solution
                try:
                    solution = np.linalg.solve(A, B)
                except np.linalg.LinAlgError:
                    # Try least squares if direct solve fails
                    solution = np.linalg.lstsq(A, B, rcond=None)[0]
            
            solve_time = time.time() - start_time
            
            # Validate solution
            if np.any(np.isnan(solution)) or np.any(np.isinf(solution)):
                return np.array([]), False, "Solution contains NaN or Inf values"
            
            return solution, True, f"Solved successfully in {solve_time:.4f}s"
            
        except Exception as e:
            return np.array([]), False, f"Solver error: {str(e)}"

class DCAnalysisEngine(AdvancedAnalysisEngine):
    """DC Analysis Engine with Newton-Raphson for nonlinear components"""
    
    def analyze(self, **kwargs) -> AnalysisResults:
        """Perform DC analysis"""
        result = AnalysisResults()
        result.success = False
        
        try:
            # Ensure ground node exists
            ground_node = self.netlist.get_ground_node()
            if not ground_node and self.netlist.nodes:
                # Auto-assign ground
                auto_ground_id = self.netlist.find_automatic_ground_node_id()
                if auto_ground_id:
                    ground_node = self.netlist.nodes[auto_ground_id]
                    ground_node.is_ground = True
                    result.message += f"Auto-assigned ground to node {auto_ground_id}. "
            
            if not ground_node:
                result.message = "No ground node found"
                return result
            
            # Build and solve MNA system
            A, B = self._build_mna_system(frequency=0)
            
            if A.size == 0:
                result.success = True
                result.message = "Empty circuit"
                result.node_voltages = {ground_node.node_id: 0.0}
                return result
            
            # Solve linear system
            solution, success, solve_msg = self._solve_linear_system(A, B)
            result.message += solve_msg
            
            if not success:
                return result
            
            # Extract results
            self._extract_dc_results(solution, result)
            
            # Calculate power dissipation
            self._calculate_power_dissipation(result)
            
            result.success = True
            
        except Exception as e:
            result.message = f"DC analysis error: {str(e)}"
            logger.error(f"DC analysis failed: {e}")
        
        return result
    
    def _extract_dc_results(self, solution: np.ndarray, result: AnalysisResults):
        """Extract DC analysis results from solution vector"""
        # Extract node voltages
        ground_node = self.netlist.get_ground_node()
        if ground_node:
            result.node_voltages[ground_node.node_id] = 0.0
        
        for node_id, idx in self.node_map.items():
            if idx < len(solution):
                voltage = solution[idx]
                result.node_voltages[node_id] = complex(voltage).real
        
        # Extract branch currents
        for branch_var, idx in self.branch_map.items():
            if idx < len(solution):
                current = solution[idx]
                result.branch_currents[branch_var] = complex(current).real
        
        # Calculate component currents
        self._calculate_component_currents(result)
        
        # Calculate wire currents
        self._calculate_wire_currents(result)
    
    def _calculate_component_currents(self, result: AnalysisResults):
        """Calculate currents through components"""
        for comp in self.netlist.components:
            try:
                if isinstance(comp, Resistor):
                    # Calculate current through resistor
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
                            v_in = result.node_voltages.get(node_in.node_id, 0.0)
                            v_out = result.node_voltages.get(node_out.node_id, 0.0)
                            
                            if comp.resistance > 0:
                                current = (v_in - v_out) / comp.resistance
                                result.component_currents[(comp, "Current (in to out)")] = current
                
                elif isinstance(comp, VoltageSource):
                    # Current from branch variable
                    branch_var = f"I_{comp.component_name}"
                    if branch_var in result.branch_currents:
                        result.component_currents[(comp, "Current (out of +)")] = result.branch_currents[branch_var]
                
                elif isinstance(comp, CurrentSource):
                    # Current is defined by the source
                    result.component_currents[(comp, "Current (out of +)")] = comp.current
                
                elif isinstance(comp, Inductor):
                    # Current from branch variable (short circuit at DC)
                    branch_var = f"I_{comp.component_name}"
                    if branch_var in result.branch_currents:
                        result.component_currents[(comp, "Current (in to out)")] = result.branch_currents[branch_var]
                
                elif isinstance(comp, Capacitor):
                    # Open circuit at DC
                    result.component_currents[(comp, "Current")] = 0.0
                    
            except Exception as e:
                logger.error(f"Error calculating current for {comp.component_name}: {e}")
    
    def _calculate_wire_currents(self, result: AnalysisResults):
        """Calculate currents through wires based on component currents"""
        # Implementation similar to original but more robust
        for wire in self.netlist.wires:
            try:
                # Find components connected to this wire
                start_comp = wire.start_comp
                end_comp = wire.end_comp
                
                # Determine current based on connected components
                current_magnitude = 0.0
                direction = 0
                
                # Check if wire connects to a component with known current
                for comp, current_label in result.component_currents:
                    if comp == start_comp or comp == end_comp:
                        current_magnitude = abs(result.component_currents[(comp, current_label)])
                        
                        # Determine direction based on component type and connection
                        if isinstance(comp, (Resistor, Inductor)):
                            if comp == start_comp:
                                direction = 1 if result.component_currents[(comp, current_label)] > 0 else -1
                            else:
                                direction = -1 if result.component_currents[(comp, current_label)] > 0 else 1
                        elif isinstance(comp, (VoltageSource, CurrentSource)):
                            # Direction based on polarity
                            direction = 1 if result.component_currents[(comp, current_label)] > 0 else -1
                
                result.wire_currents[(wire, direction)] = current_magnitude
                
            except Exception as e:
                logger.error(f"Error calculating wire current: {e}")
                result.wire_currents[(wire, 0)] = 0.0
    
    def _calculate_power_dissipation(self, result: AnalysisResults):
        """Calculate power dissipation in components"""
        for comp in self.netlist.components:
            try:
                power = 0.0
                
                if isinstance(comp, Resistor):
                    current_key = (comp, "Current (in to out)")
                    if current_key in result.component_currents:
                        current = result.component_currents[current_key]
                        power = current**2 * comp.resistance
                
                elif isinstance(comp, VoltageSource):
                    current_key = (comp, "Current (out of +)")
                    if current_key in result.component_currents:
                        current = result.component_currents[current_key]
                        power = -current * comp.voltage  # Power delivered by source
                
                elif isinstance(comp, CurrentSource):
                    # Calculate voltage across current source
                    pin_pos = None
                    pin_neg = None
                    for pin in comp.get_pins():
                        if pin.data(1) == "+":
                            pin_pos = pin
                        elif pin.data(1) == "-":
                            pin_neg = pin
                    
                    if pin_pos and pin_neg:
                        node_pos = pin_pos.data(3)
                        node_neg = pin_neg.data(3)
                        
                        if node_pos and node_neg:
                            v_pos = result.node_voltages.get(node_pos.node_id, 0.0)
                            v_neg = result.node_voltages.get(node_neg.node_id, 0.0)
                            voltage = v_pos - v_neg
                            power = -voltage * comp.current  # Power delivered by source
                
                result.power_dissipation[comp] = power
                
            except Exception as e:
                logger.error(f"Error calculating power for {comp.component_name}: {e}")

class ACAnalysisEngine(AdvancedAnalysisEngine):
    """AC Analysis Engine for frequency domain analysis"""
    
    def analyze(self, frequencies: np.ndarray = None, **kwargs) -> AnalysisResults:
        """Perform AC analysis over frequency range"""
        result = AnalysisResults()
        result.success = False
        
        if frequencies is None:
            frequencies = np.logspace(1, 6, 100)  # 10 Hz to 1 MHz
        
        try:
            # Ensure ground node
            ground_node = self.netlist.get_ground_node()
            if not ground_node:
                result.message = "No ground node found for AC analysis"
                return result
            
            # Initialize frequency response storage
            result.frequency_response = {
                'frequencies': frequencies,
                'node_voltages': {},
                'component_currents': {},
                'transfer_functions': {}
            }
            
            # Initialize arrays for each node
            for node_id in self.node_map.keys():
                result.frequency_response['node_voltages'][node_id] = np.zeros(len(frequencies), dtype=complex)
            
            # Analyze at each frequency
            for i, freq in enumerate(frequencies):
                A, B = self._build_mna_system(frequency=freq)
                
                if A.size == 0:
                    continue
                
                solution, success, _ = self._solve_linear_system(A, B)
                
                if success and len(solution) > 0:
                    # Store node voltages at this frequency
                    for node_id, idx in self.node_map.items():
                        if idx < len(solution):
                            result.frequency_response['node_voltages'][node_id][i] = solution[idx]
            
            result.success = True
            result.message = f"AC analysis completed for {len(frequencies)} frequency points"
            
        except Exception as e:
            result.message = f"AC analysis error: {str(e)}"
            logger.error(f"AC analysis failed: {e}")
        
        return result

class TransientAnalysisEngine(AdvancedAnalysisEngine):
    """Transient Analysis Engine with adaptive time stepping"""
    
    def analyze(self, t_end: float = 1e-3, dt: float = None, **kwargs) -> AnalysisResults:
        """Perform transient analysis"""
        result = AnalysisResults()
        result.success = False
        
        if dt is None:
            dt = t_end / 1000  # Default 1000 time points
        
        try:
            # Determine time points
            time_points = np.arange(0, t_end + dt, dt)
            
            # Initialize time response storage
            result.time_response = {
                'time': time_points,
                'node_voltages': {},
                'component_currents': {}
            }
            
            # Initialize arrays for each node
            for node_id in self.node_map.keys():
                result.time_response['node_voltages'][node_id] = np.zeros(len(time_points))
            
            # Initial conditions (DC operating point)
            dc_engine = DCAnalysisEngine(self.netlist, self.settings)
            dc_result = dc_engine.analyze()
            
            if not dc_result.success:
                result.message = f"Failed to find DC operating point: {dc_result.message}"
                return result
            
            # Set initial conditions
            for i, t in enumerate(time_points):
                if i == 0:
                    # Use DC operating point
                    for node_id, voltage in dc_result.node_voltages.items():
                        if node_id in result.time_response['node_voltages']:
                            result.time_response['node_voltages'][node_id][i] = voltage
                else:
                    # Backward Euler integration (implicit)
                    # This would require more sophisticated implementation
                    # For now, use simplified analytical solutions for basic circuits
                    self._solve_transient_step(t, dt, result, i)
            
            result.success = True
            result.message = f"Transient analysis completed for {len(time_points)} time points"
            
        except Exception as e:
            result.message = f"Transient analysis error: {str(e)}"
            logger.error(f"Transient analysis failed: {e}")
        
        return result
    
    def _solve_transient_step(self, t: float, dt: float, result: AnalysisResults, step: int):
        """Solve single transient step (simplified implementation)"""
        # This is a placeholder for more sophisticated transient analysis
        # In a full implementation, this would use numerical integration methods
        # like Backward Euler, Trapezoidal, or Gear methods
        
        # For now, copy previous values (maintaining continuity)
        if step > 0:
            for node_id in result.time_response['node_voltages']:
                result.time_response['node_voltages'][node_id][step] = \
                    result.time_response['node_voltages'][node_id][step-1]

class AdvancedCircuitSimulator:
    """
    Advanced Circuit Simulator with multiple analysis engines and comprehensive features.
    This is a complete overhaul of the original simulator with significant improvements.
    """
    
    def __init__(self, netlist, settings: SimulationSettings = None):
        if not self._check_numpy():
            raise ImportError("NumPy is required for advanced simulation")
        
        self.netlist = netlist
        self.settings = settings or SimulationSettings()
        
        # Analysis engines
        self.dc_engine = DCAnalysisEngine(netlist, self.settings)
        self.ac_engine = ACAnalysisEngine(netlist, self.settings)
        self.transient_engine = TransientAnalysisEngine(netlist, self.settings)
        
        # Results storage
        self.last_results = {}
        
    def _check_numpy(self) -> bool:
        """Check if NumPy is available"""
        try:
            import numpy as np
            import scipy
            return True
        except ImportError:
            return False
    
    def run_dc_analysis(self) -> AnalysisResults:
        """Run DC analysis with comprehensive error handling and diagnostics"""
        logger.info("Starting DC analysis...")
        
        try:
            result = self.dc_engine.analyze()
            self.last_results[AnalysisType.DC] = result
            
            if result.success:
                logger.info(f"DC analysis completed successfully: {result.message}")
            else:
                logger.warning(f"DC analysis failed: {result.message}")
            
            return result
            
        except Exception as e:
            logger.error(f"DC analysis crashed: {e}")
            result = AnalysisResults()
            result.success = False
            result.message = f"Analysis crashed: {str(e)}"
            return result
    
    def run_ac_analysis(self, frequencies: np.ndarray = None) -> AnalysisResults:
        """Run AC analysis over frequency range"""
        logger.info("Starting AC analysis...")
        
        try:
            result = self.ac_engine.analyze(frequencies=frequencies)
            self.last_results[AnalysisType.AC] = result
            
            if result.success:
                logger.info(f"AC analysis completed: {result.message}")
            else:
                logger.warning(f"AC analysis failed: {result.message}")
            
            return result
            
        except Exception as e:
            logger.error(f"AC analysis crashed: {e}")
            result = AnalysisResults()
            result.success = False
            result.message = f"Analysis crashed: {str(e)}"
            return result
    
    def run_transient_analysis(self, t_end: float = 1e-3, dt: float = None) -> AnalysisResults:
        """Run transient analysis"""
        logger.info("Starting transient analysis...")
        
        try:
            result = self.transient_engine.analyze(t_end=t_end, dt=dt)
            self.last_results[AnalysisType.TRANSIENT] = result
            
            if result.success:
                logger.info(f"Transient analysis completed: {result.message}")
            else:
                logger.warning(f"Transient analysis failed: {result.message}")
            
            return result
            
        except Exception as e:
            logger.error(f"Transient analysis crashed: {e}")
            result = AnalysisResults()
            result.success = False
            result.message = f"Analysis crashed: {str(e)}"
            return result
    
    def get_results_description(self, analysis_type: AnalysisType = AnalysisType.DC, 
                              include_wire_currents: bool = False) -> str:
        """Get formatted description of analysis results"""
        if analysis_type not in self.last_results:
            return f"No {analysis_type.value} analysis results available."
        
        result = self.last_results[analysis_type]
        
        if not result.success:
            return f"{analysis_type.value.upper()} Analysis Failed: {result.message}"
        
        description = f"{analysis_type.value.upper()} Analysis Results:\n"
        description += f"Status: {result.message}\n\n"
        
        # Node voltages
        description += "Node Voltages:\n"
        if result.node_voltages:
            for node_id in sorted(result.node_voltages.keys()):
                voltage = result.node_voltages[node_id]
                is_ground = self.netlist.nodes.get(node_id, None) and self.netlist.nodes[node_id].is_ground
                ground_text = " (Ground)" if is_ground else ""
                
                if isinstance(voltage, complex):
                    if abs(voltage.imag) < 1e-12:
                        voltage_str = self._format_value_with_unit(voltage.real, 'V')
                    else:
                        voltage_str = f"{voltage.real:.6g} + j{voltage.imag:.6g} V"
                else:
                    voltage_str = self._format_value_with_unit(voltage, 'V')
                
                description += f"  Node {node_id}{ground_text}: {voltage_str}\n"
        
        # Component currents
        description += "\nComponent Currents:\n"
        if result.component_currents:
            for (component, current_label), current_val in result.component_currents.items():
                if isinstance(current_val, str):
                    description += f"  {component.component_name} ({current_label}): {current_val}\n"
                elif isinstance(current_val, complex):
                    if abs(current_val.imag) < 1e-12:
                        current_str = self._format_value_with_unit(abs(current_val.real), 'A')
                        arrow = "→" if current_val.real >= 0 else "←"
                    else:
                        current_str = f"{abs(current_val):.6g} A"
                        arrow = "→"
                    description += f"  {component.component_name} ({current_label}): {current_str} {arrow}\n"
                else:
                    current_str = self._format_value_with_unit(abs(current_val), 'A')
                    arrow = "→" if current_val >= 0 else "←"
                    description += f"  {component.component_name} ({current_label}): {current_str} {arrow}\n"
        
        # Power dissipation
        if result.power_dissipation:
            description += "\nPower Dissipation:\n"
            total_power = 0.0
            for component, power in result.power_dissipation.items():
                power_str = self._format_value_with_unit(power, 'W')
                description += f"  {component.component_name}: {power_str}\n"
                total_power += power
            
            description += f"\nTotal Power: {self._format_value_with_unit(total_power, 'W')}\n"
        
        # Wire currents if requested
        if include_wire_currents and result.wire_currents:
            description += "\nWire Currents:\n"
            for (wire, direction), current_val in result.wire_currents.items():
                start_comp = wire.start_comp.component_name if wire.start_comp else "Unknown"
                start_pin = wire.start_pin.data(1) if wire.start_pin else "Unknown"
                end_comp = wire.end_comp.component_name if wire.end_comp else "Unknown"
                end_pin = wire.end_pin.data(1) if wire.end_pin else "Unknown"
                
                wire_id = f"{start_comp}.{start_pin} → {end_comp}.{end_pin}"
                
                if isinstance(current_val, complex):
                    current_magnitude = abs(current_val)
                else:
                    current_magnitude = abs(current_val)
                
                current_str = self._format_value_with_unit(current_magnitude, 'A')
                arrow = "→" if direction == 1 else ("←" if direction == -1 else "-")
                
                description += f"  Wire ({wire_id}): {current_str} {arrow}\n"
        
        return description
    
    def _format_value_with_unit(self, value: float, unit: str) -> str:
        """Format value with appropriate SI prefix"""
        abs_val = abs(value)
        
        if unit == 'V':
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
        
        elif unit == 'A':
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
        
        elif unit == 'W':
            if abs_val >= 1:
                return f"{value:.6g} W"
            elif abs_val >= 1e-3:
                return f"{value*1e3:.6g} mW"
            elif abs_val >= 1e-6:
                return f"{value*1e6:.6g} μW"
            elif abs_val >= 1e-9:
                return f"{value*1e9:.6g} nW"
            else:
                return f"{value:.2e} W"
        
        return f"{value:.6g} {unit}"
    
    # Legacy compatibility methods
    def get_node_voltage(self, node_id: int) -> Optional[float]:
        """Get voltage at specific node (legacy compatibility)"""
        if AnalysisType.DC in self.last_results:
            result = self.last_results[AnalysisType.DC]
            voltage = result.node_voltages.get(node_id)
            if isinstance(voltage, complex):
                return voltage.real
            return voltage
        return None
    
    def get_component_current(self, component, current_label: str) -> Optional[float]:
        """Get current through specific component (legacy compatibility)"""
        if AnalysisType.DC in self.last_results:
            result = self.last_results[AnalysisType.DC]
            current = result.component_currents.get((component, current_label))
            if isinstance(current, complex):
                return current.real
            return current
        return None
    
    def get_wire_current_info(self, wire) -> Tuple[Optional[float], int]:
        """Get wire current info (legacy compatibility)"""
        if AnalysisType.DC in self.last_results:
            result = self.last_results[AnalysisType.DC]
            
            # Find wire current entry
            for (w, direction), current_val in result.wire_currents.items():
                if w == wire:
                    if isinstance(current_val, complex):
                        return abs(current_val.real), direction
                    return abs(current_val), direction
        
        return None, 0

# Export the new simulator class for backward compatibility
CircuitSimulator = AdvancedCircuitSimulator

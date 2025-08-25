from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QLabel, QListWidget,
    QFormLayout, QPushButton, QLineEdit, QScrollArea, QSplitter,
    QTextEdit, QGroupBox, QHBoxLayout
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont
from config import Component

class PropertiesPanel(QDockWidget):
    def __init__(self, main_window):
        super().__init__("Properties", main_window)
        self.main_window = main_window
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setMinimumWidth(300)

        # Create main widget with splitter for better layout management
        self.central_widget = QWidget()
        self.setWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setSpacing(8)
        self.main_layout.setContentsMargins(8, 8, 8, 8)

        # Create splitter to divide between component list and properties
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_layout.addWidget(self.splitter)

        # Components section
        self.components_group = QGroupBox("Circuit Components")
        self.components_layout = QVBoxLayout(self.components_group)
        
        # Component list with enhanced features
        self.component_list_label = QLabel("Select a component:")
        font = QFont()
        font.setBold(True)
        self.component_list_label.setFont(font)
        self.components_layout.addWidget(self.component_list_label)

        # Enhanced component list with scrolling
        self.component_list_widget = QListWidget()
        self.component_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.component_list_widget.currentItemChanged.connect(self.on_component_selected)
        self.component_list_widget.setMinimumHeight(150)
        self.component_list_widget.setAlternatingRowColors(True)
        self.component_list_widget.setToolTip("Select a component to view and edit its properties")
        
        # Enable proper scrolling for component list
        self.component_list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.component_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.components_layout.addWidget(self.component_list_widget)
        self.splitter.addWidget(self.components_group)

        # Properties section with scroll area
        self.properties_group = QGroupBox("Component Properties")
        self.properties_main_layout = QVBoxLayout(self.properties_group)
        
        # Create scroll area for properties form
        self.properties_scroll = QScrollArea()
        self.properties_scroll.setWidgetResizable(True)
        self.properties_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.properties_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.properties_scroll.setMinimumHeight(200)
        
        # Properties form widget inside scroll area
        self.properties_widget = QWidget()
        self.properties_form_layout = QFormLayout(self.properties_widget)
        self.properties_form_layout.setSpacing(6)
        self.properties_scroll.setWidget(self.properties_widget)
        
        self.properties_main_layout.addWidget(self.properties_scroll)

        # Action buttons
        self.button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Apply Changes")
        self.save_button.setDefault(True)
        self.save_button.setAutoDefault(True)
        self.save_button.clicked.connect(self.apply_property_changes)
        self.save_button.setToolTip("Apply property changes to the selected component")
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_component_list)
        self.refresh_button.setToolTip("Refresh the component list")
        
        self.button_layout.addWidget(self.refresh_button)
        self.button_layout.addWidget(self.save_button)
        self.properties_main_layout.addLayout(self.button_layout)
        
        self.splitter.addWidget(self.properties_group)
        
        # Set splitter proportions
        self.splitter.setSizes([200, 300])

        self.property_editors = {} # Dictionary to store QLineEdit editors for properties
        self.selected_component = None
        
        # Apply enhanced styling
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QListWidget {
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                background-color: white;
                selection-background-color: #3daee9;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #3daee9;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #e3f2fd;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QLineEdit {
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                padding: 5px;
                background-color: white;
            }
            QLineEdit:focus {
                border: 2px solid #3daee9;
            }
            QScrollArea {
                border: 1px solid #d0d0d0;
                border-radius: 3px;
            }
        """)

    def refresh_component_list(self):
        """Refresh the component list and update display."""
        self.update_component_list()
        self.clear_properties_display()
        print("Component list refreshed")

    def update_component_list(self):
        """Populates the list widget with components from the netlist."""
        self.component_list_widget.clear()
        
        if not hasattr(self.main_window, 'netlist') or not self.main_window.netlist:
            return
            
        # Group components by type for better organization
        component_groups = {}
        for component in self.main_window.netlist.components:
            comp_type = type(component).__name__
            if comp_type not in component_groups:
                component_groups[comp_type] = []
            component_groups[comp_type].append(component)
        
        # Add components to list, grouped by type
        for comp_type in sorted(component_groups.keys()):
            for component in sorted(component_groups[comp_type], key=lambda x: x.component_name):
                item_text = f"{component.component_name} ({comp_type})"
                self.component_list_widget.addItem(item_text)
                
        # Update tooltip with count
        total_components = len(self.main_window.netlist.components)
        self.component_list_widget.setToolTip(f"Total components: {total_components}")

    def on_component_selected(self, current, previous):
        """Displays properties of the selected component."""
        self.clear_properties_display()
        if current:
            # Extract component name from the item text (remove type suffix)
            item_text = current.text()
            component_name = item_text.split(' (')[0] if ' (' in item_text else item_text
            
            # Find the component object by name
            self.selected_component = None
            for comp in self.main_window.netlist.components:
                if comp.component_name == component_name:
                    self.selected_component = comp
                    break

            if self.selected_component:
                self._display_component_properties()
        else:
            self.selected_component = None

    def _display_component_properties(self):
        """Display properties of the selected component in the form."""
        if not self.selected_component:
            return
            
        properties = self.selected_component.get_properties()
        
        # Add component type info
        comp_type_label = QLabel("Component Type:")
        comp_type_info = QLabel(type(self.selected_component).__name__)
        comp_type_info.setStyleSheet("font-weight: bold; color: #666;")
        self.properties_form_layout.addRow(comp_type_label, comp_type_info)
        
        # Add separator
        separator = QLabel()
        separator.setStyleSheet("border-bottom: 1px solid #ccc; margin: 5px 0;")
        self.properties_form_layout.addRow(separator)
        
        # Add editable properties
        for name, value in properties.items():
            label = QLabel(name + ":")
            label.setToolTip(f"Modify the {name.lower()} property")
            
            editor = QLineEdit(str(value))
            editor.setClearButtonEnabled(True)
            editor.setPlaceholderText(f"Enter {name.lower()}")
            editor.setToolTip(f"Current value: {value}")
            
            self.properties_form_layout.addRow(label, editor)
            self.property_editors[name] = editor
            
        # Ensure scroll area updates its size
        self.properties_scroll.updateGeometry()


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
            component_name = self.selected_component.component_name
            
            # Search for the item in the list (considering the new format with type)
            for i in range(self.component_list_widget.count()):
                item = self.component_list_widget.item(i)
                if item.text().startswith(component_name + ' ('):
                    self.component_list_widget.setCurrentItem(item)
                    break
            else:
                # If not found, refresh the list and try again
                self.update_component_list()
                for i in range(self.component_list_widget.count()):
                    item = self.component_list_widget.item(i)
                    if item.text().startswith(component_name + ' ('):
                        self.component_list_widget.setCurrentItem(item)
                        break

            # Display properties if not already present
            if not self.property_editors:
                self._display_component_properties()
        else:
            self.selected_component = None

    def clear_properties_display(self):
        """Clears the property editors from the layout."""
        # Clear all rows from the form layout
        while self.properties_form_layout.count():
            item = self.properties_form_layout.takeRow(0)
            if item.fieldItem and item.fieldItem.widget(): 
                item.fieldItem.widget().deleteLater()
            if item.labelItem and item.labelItem.widget(): 
                item.labelItem.widget().deleteLater()
        self.property_editors.clear()
        
        # Update scroll area
        self.properties_scroll.updateGeometry()

    def apply_property_changes(self):
        """Applies the changes made in the property editors to the selected component."""
        if not self.selected_component:
            print("No component selected for property changes")
            return
            
        changes_applied = False
        failed_changes = []
        
        for name, editor in self.property_editors.items():
            new_value_text = editor.text().strip()
            old_value = str(self.selected_component.get_properties().get(name, ""))
            
            if new_value_text != old_value:
                # Attempt to set the property using the component's method
                if self.selected_component.set_property(name, new_value_text):
                    changes_applied = True
                    print(f"Updated {name}: {old_value} -> {new_value_text}")
                else:
                    failed_changes.append(name)
                    # If setting failed, revert the editor's text to the current property value
                    editor.setText(old_value)
                    editor.setStyleSheet("border: 2px solid red;")
                    editor.setToolTip(f"Failed to set {name} to '{new_value_text}'. Value reverted.")
                    
                    # Clear the error styling after a delay
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(3000, lambda e=editor: self._clear_error_styling(e))

        if changes_applied:
            print(f"Properties updated for {self.selected_component.component_name}")
            
            # Hide simulation results to force recalculation
            if hasattr(self.main_window, 'hide_simulation_results'):
                self.main_window.hide_simulation_results()
            
            # Update component list to reflect any name changes
            self.update_component_list()
            
            # Re-select the component in the list
            component_name = self.selected_component.component_name
            for i in range(self.component_list_widget.count()):
                item = self.component_list_widget.item(i)
                if item.text().startswith(component_name + ' ('):
                    self.component_list_widget.setCurrentItem(item)
                    break
                    
        if failed_changes:
            print(f"Failed to update properties: {', '.join(failed_changes)}")
    
    def _clear_error_styling(self, editor):
        """Clear error styling from an editor."""
        editor.setStyleSheet("")
        editor.setToolTip("")


from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QLabel, QListWidget,
    QFormLayout, QPushButton, QLineEdit
)
from PyQt6.QtCore import Qt
from config import Component

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
        self.component_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.component_list_widget.currentItemChanged.connect(self.on_component_selected)
        self.layout.addWidget(self.component_list_widget)

        self.properties_form_layout = QFormLayout()
        self.layout.addLayout(self.properties_form_layout)

        self.property_editors = {} # Dictionary to store QLineEdit editors for properties

        self.save_button = QPushButton("Apply Changes")
        self.save_button.setDefault(True)
        self.save_button.setAutoDefault(True)
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
                self.update_component_list()
                items = self.component_list_widget.findItems(self.selected_component.component_name, Qt.MatchFlag.MatchExactly)
                if items:
                    self.component_list_widget.setCurrentItem(items[0])

            # Only add property fields if not already present
            if not self.property_editors:
                properties = self.selected_component.get_properties()
                for name, value in properties.items():
                    label = QLabel(name + ":")
                    editor = QLineEdit(str(value))
                    editor.setClearButtonEnabled(True)
                    editor.setPlaceholderText(f"Enter {name.lower()}")
                    self.properties_form_layout.addRow(label, editor)
                    self.property_editors[name] = editor
        else:
            self.selected_component = None


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


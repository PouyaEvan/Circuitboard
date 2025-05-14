from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox, QTextEdit, QVBoxLayout

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Transient Analysis Settings')
        layout = QFormLayout(self)
        self.time_end = 1.0
        self.time_step = 0.01
        sb_end = QDoubleSpinBox(); sb_end.setValue(self.time_end); sb_end.setSuffix(' s')
        sb_step = QDoubleSpinBox(); sb_step.setValue(self.time_step); sb_step.setSuffix(' s')
        layout.addRow('End Time:', sb_end)
        layout.addRow('Time Step:', sb_step)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(lambda: self.accept_settings(sb_end.value(), sb_step.value()))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept_settings(self, end, step):
        self.time_end = end
        self.time_step = step
        self.accept()

class InstructionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Instructions')
        layout = QVBoxLayout(self)
        text = QTextEdit(self); text.setReadOnly(True)
        text.setPlainText('''  Welcome to CircuitSimulator V0.5 Beta

- Use the toolbar to place components.
- Draw wires by selecting the wire tool and clicking pins.
- Use the Analysis menu for DC and transient simulations.
- Access settings to configure simulation parameters.
- Press Delete to remove selections.
- View this help under Help > Instructions.
''')
        layout.addWidget(text)

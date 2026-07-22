from qtpy.QtWidgets import QWidget, QPushButton, QGridLayout, QDoubleSpinBox, QLabel
from .CalibrateHomeDialog import CalibrateHomeDialog
class JogPanel(QWidget):
    def __init__(self, stage_movement):
        super().__init__()
        self.stage_movement = stage_movement  

        layout = QGridLayout(self)
        #Axis numbers
        X_axis = 0
        Y_axis = 1
        Z_axis = 2

        # step size control
        self.step_size_box = QDoubleSpinBox()
        self.step_size_box.setRange(0.2, 1000)
        self.step_size_box.setValue(10.0)
        layout.addWidget(QLabel("Step size (µm)"), 0, 0)
        layout.addWidget(self.step_size_box, 0, 1)

        # jog buttons
        self.up_btn = self._make_jog_button("+X ↑")
        self.down_btn = self._make_jog_button("-X ↓")
        self.left_btn = self._make_jog_button("-Y ←")
        self.right_btn = self._make_jog_button("+Y →")
        self.up_z_btn = self._make_jog_button("↑")
        self.down_z_btn = self._make_jog_button("↓")

        self.up_btn.clicked.connect(lambda: self.jog(axis=X_axis, direction=+1))
        self.down_btn.clicked.connect(lambda: self.jog(axis=X_axis, direction=-1))
        self.left_btn.clicked.connect(lambda: self.jog(axis=Y_axis, direction=-1))
        self.right_btn.clicked.connect(lambda: self.jog(axis=Y_axis, direction=+1))
        self.up_z_btn.clicked.connect(lambda: self.jog(axis=Z_axis, direction=+1))
        self.down_z_btn.clicked.connect(lambda: self.jog(axis=Z_axis, direction=-1))

        layout.addWidget(self.up_btn, 1, 1)
        layout.addWidget(self.left_btn, 2, 0)
        layout.addWidget(self.right_btn, 2, 2)
        layout.addWidget(self.down_btn, 3, 1)
        layout.addWidget(self.up_z_btn, 1, 3)
        layout.addWidget(self.down_z_btn, 3, 3)

        # per-axis motor enable toggles
        self.x_toggle = QPushButton("X Motor: ON")
        self.x_toggle.setCheckable(True)
        self.x_toggle.setChecked(self.stage_movement.isenabled(X_axis))
        self.x_toggle.toggled.connect(self._on_x_toggle)

        self.y_toggle = QPushButton("Y Motor: ON")
        self.y_toggle.setCheckable(True)
        self.y_toggle.setChecked(self.stage_movement.isenabled(Y_axis))
        self.y_toggle.toggled.connect(self._on_y_toggle)

        self.z_toggle = QPushButton("Z Motor: ON")
        self.z_toggle.setCheckable(True)
        self.z_toggle.setChecked(self.stage_movement.isenabled(Z_axis))
        self.z_toggle.toggled.connect(self._on_z_toggle)

        layout.addWidget(self.x_toggle, 4, 0)
        layout.addWidget(self.y_toggle, 4, 1)
        layout.addWidget(self.z_toggle, 4, 3)

        # sync jog-button enabled/disabled state with actual starting hardware state
        self._set_buttons_enabled((self.up_btn, self.down_btn), self.x_toggle.isChecked())
        self._set_buttons_enabled((self.left_btn, self.right_btn), self.y_toggle.isChecked())
        self._set_buttons_enabled((self.up_z_btn, self.down_z_btn), self.z_toggle.isChecked())

        self.move_home = self._make_moveto_button('Move Home')
        self.move_home.clicked.connect(lambda: self._move_home())

        self.set_home = self._make_moveto_button('Calibrate Home')
        self.set_home.clicked.connect(lambda: self._calibrate_home())
        
        layout.addWidget(self.move_home, 5, 0)
        layout.addWidget(self.set_home, 5, 1)
        


    def _make_jog_button(self, text):
        btn = QPushButton(text)
        btn.setFixedSize(70, 70)
        btn.setStyleSheet("font-size: 14pt; font-weight: bold;")
        return btn

    def _make_moveto_button(self, text):
        btn = QPushButton(text)
        return btn
    
    def _refresh_motor_toggles_from_hardware(self):
        X_axis, Y_axis, Z_axis = 0, 1, 2

        x = self.stage_movement.isenabled(X_axis)
        y = self.stage_movement.isenabled(Y_axis)
        z = self.stage_movement.isenabled(Z_axis)

        # block signals to avoid calling enable/disable again
        for btn, state in [(self.x_toggle, x), (self.y_toggle, y), (self.z_toggle, z)]:
            btn.blockSignals(True)
            btn.setChecked(state)
            btn.blockSignals(False)

        self.x_toggle.setText("X Motor: ON" if x else "X Motor: OFF")
        self.y_toggle.setText("Y Motor: ON" if y else "Y Motor: OFF")
        self.z_toggle.setText("Z Motor: ON" if z else "Z Motor: OFF")

        self._set_buttons_enabled((self.up_btn, self.down_btn), x)
        self._set_buttons_enabled((self.left_btn, self.right_btn), y)
        self._set_buttons_enabled((self.up_z_btn, self.down_z_btn), z)

    def _move_home(self):
        self.stage_movement.move_home()
        self._refresh_motor_toggles_from_hardware()
        
    def _calibrate_home(self):
        dlg = CalibrateHomeDialog(self.stage_movement, parent=self)
        if dlg.exec():  # modal; blocks other interaction but keeps UI responsive
            self._refresh_motor_toggles_from_hardware()
    def _set_buttons_enabled(self, buttons, enabled):
        for btn in buttons:
            btn.setEnabled(enabled)

    def _on_x_toggle(self, checked):
        if checked:
            self.stage_movement.enable_x()
        else:
            self.stage_movement.disable_x()
        self.x_toggle.setText("X Motor: ON" if checked else "X Motor: OFF")
        self._set_buttons_enabled((self.up_btn, self.down_btn), checked)

    def _on_y_toggle(self, checked):
        if checked:
            self.stage_movement.enable_y()
        else:
            self.stage_movement.disable_y()
        self.y_toggle.setText("Y Motor: ON" if checked else "Y Motor: OFF")
        self._set_buttons_enabled((self.left_btn, self.right_btn), checked)

    def _on_z_toggle(self, checked):
        if checked:
            self.stage_movement.enable_z()
        else:
            self.stage_movement.disable_z()
        self.z_toggle.setText("Z Motor: ON" if checked else "Z Motor: OFF")
        self._set_buttons_enabled((self.up_z_btn, self.down_z_btn), checked)

    def jog(self, axis, direction):
        step_um = self.step_size_box.value() * direction
        step_mm = step_um / 1000
        self.stage_movement.jog(axis, step_mm)
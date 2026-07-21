from qtpy.QtWidgets import QWidget, QPushButton, QGridLayout, QDoubleSpinBox, QLabel
class AcquisitionPanel(QWidget):
    def __init__(self, stage_movement):
        super().__init__()
        self.stage_movement = stage_movement  

        layout = QGridLayout(self)

        # step size control
        self.step_size_box = QDoubleSpinBox()
        self.step_size_box.setRange(0.2, 1000)
        self.step_size_box.setValue(10.0)
        layout.addWidget(QLabel("Step size (µm)"), 0, 0)
        layout.addWidget(self.step_size_box, 0, 1)

        # jog buttons
        up_btn = QPushButton("+X ↑")
        down_btn = QPushButton("-X ↓")
        left_btn = QPushButton("-Y ←")
        right_btn = QPushButton("+Y →")
        up_z_btn = QPushButton("↑")
        down_z_btn = QPushButton("↓")

        #Axis numbers
        X_axis = 0
        Y_axis = 1
        Z_axis = 2

        up_btn.clicked.connect(lambda: self.jog(axis=X_axis, direction=+1))
        down_btn.clicked.connect(lambda: self.jog(axis=X_axis, direction=-1))
        left_btn.clicked.connect(lambda: self.jog(axis=Y_axis, direction=-1))
        right_btn.clicked.connect(lambda: self.jog(axis=Y_axis, direction=+1))
        up_z_btn.clicked.connect(lambda: self.jog(axis=Z_axis, direction =+1))
        down_z_btn.clicked.connect(lambda: self.jog(axis = Z_axis, direction = -1))
        layout.addWidget(up_btn, 1, 1)
        layout.addWidget(left_btn, 2, 0)
        layout.addWidget(right_btn, 2, 2)
        layout.addWidget(down_btn, 3, 1)
        layout.addWidget(up_z_btn, 1, 3)
        layout.addWidget(down_z_btn, 3, 3)

    def jog(self, axis, direction):
        step_um = self.step_size_box.value() * direction
        step_mm = step_um/1000
        self.stage_movement.jog(axis,step_mm)
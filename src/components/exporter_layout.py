"""Shared presentation for the three two-step exporter windows."""

from PySide6 import QtCore, QtWidgets

from components.activity_panel import ActivityPanel


class ExpandableOptions(QtWidgets.QWidget):
    def __init__(self, title, sections, switches, parent=None):
        super().__init__(parent)
        self.title = title
        self.switches = switches
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Maximum)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.toggle = QtWidgets.QToolButton()
        self.toggle.setProperty('class', 'disclosure')
        self.toggle.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.toggle.setCheckable(True)
        self.content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        for section in sections:
            content_layout.addWidget(section)
        self.content.hide()
        layout.addWidget(self.toggle)
        layout.addWidget(self.content)
        self.toggle.toggled.connect(self._set_expanded)
        for switch in switches:
            switch.toggled.connect(self._update_summary)
        self._set_expanded(False)
        self._update_summary()

    def _set_expanded(self, expanded):
        self.content.setVisible(expanded)
        self.toggle.setArrowType(QtCore.Qt.ArrowType.DownArrow if expanded else QtCore.Qt.ArrowType.RightArrow)

    def _update_summary(self):
        enabled = [switch.text() for switch in self.switches if switch.isChecked()]
        self.toggle.setText(self.title + (f' · {len(enabled)} enabled' if enabled else ''))
        self.toggle.setToolTip('\n'.join(enabled) if enabled else 'Show additional export options')


def audio_options(window):
    group = QtWidgets.QGroupBox('Audio settings')
    layout = QtWidgets.QGridLayout(group)
    layout.setHorizontalSpacing(24)
    layout.setVerticalSpacing(12)
    layout.addWidget(window.trim_silence, 0, 0)
    layout.addWidget(window.normalize, 0, 1)
    layout.addWidget(window.skip_existing, 1, 0)
    if hasattr(window, 'include_preview'):
        layout.addWidget(window.include_preview, 1, 1)
    for column, (title, combo) in enumerate((('Sample rate', window.sample_rate), ('Bit depth', window.bit_depth))):
        combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(12)
        # Keep the device-specific caveat in the tooltip, without stretching
        # every audio control to accommodate one long dropdown entry.
        combo.setItemText(0, 'Original')
        if title == 'Sample rate':
            combo.setItemText(1, '44.1 kHz')
            combo.setItemText(2, '48 kHz')
        else:
            combo.setItemText(2, '16-bit')
            combo.setItemText(4, '32-bit')
            combo.setItemData(4, 'SP-404 MK2 does not support 32-bit audio.', QtCore.Qt.ItemDataRole.ToolTipRole)
            combo.setToolTip('Bit depth for exported WAV files. SP-404 MK2 does not support 32-bit audio.')
        label = QtWidgets.QLabel(title)
        label.setBuddy(combo)
        field = QtWidgets.QHBoxLayout()
        field.addWidget(label)
        field.addWidget(combo, 1)
        layout.addLayout(field, 2, column)
        layout.setColumnStretch(column, 1)
    return group


def activity_panel(window):
    panel = ActivityPanel(window.log_output)
    window.activity_status = panel.status
    window.clear_log_button = panel.clear_button
    return panel


def finish_layout(window, title, description):
    layout = window.layout()
    layout.setContentsMargins(18, 16, 18, 12)
    layout.setSpacing(12)
    header = QtWidgets.QWidget()
    row = QtWidgets.QHBoxLayout(header)
    row.setContentsMargins(0, 0, 0, 8)
    row.setSpacing(12)
    icon = QtWidgets.QLabel()
    icon.setPixmap(window.windowIcon().pixmap(36, 36))
    row.addWidget(icon)
    text = QtWidgets.QVBoxLayout()
    text.setSpacing(3)
    heading = QtWidgets.QLabel(title)
    font = heading.font()
    font.setPointSize(18)
    font.setBold(True)
    heading.setFont(font)
    text.addWidget(heading)
    subtitle = QtWidgets.QLabel(description)
    subtitle.setWordWrap(True)
    text.addWidget(subtitle)
    row.addLayout(text, 1)
    layout.insertWidget(0, header)
    window.tabs.setTabText(0, '1  Process')
    window.tabs.setTabText(1, '2  Export')
    for tab in (window.tab_process, window.tab_export):
        tab.layout().setContentsMargins(14, 14, 14, 14)
        tab.layout().setSpacing(12)
    for scroll in window.tabs.findChildren(QtWidgets.QScrollArea):
        scroll.setObjectName('exporterScroll')
        scroll.widget().setObjectName('exporterScrollContent')
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setStyleSheet('QScrollArea { border: none; background: transparent; }')
        scroll.widget().layout().setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        scroll.widget().layout().setContentsMargins(0, 4, 8, 0)
    for form in window.tabs.findChildren(QtWidgets.QFormLayout):
        form.setVerticalSpacing(12)
        form.setHorizontalSpacing(12)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
    for name, caption in (('input_folder', 'Library folder'), ('output_folder', 'Index folder'),
                          ('json_path', 'Index file'), ('proc_output_folder', 'Export folder')):
        field = getattr(window, name, None)
        if field is None:
            continue
        field.setMinimumHeight(30)
        field.setAccessibleName(caption)
        browse = getattr(window, name + '_btn')
        browse.setText('Browse…')
        browse.setMinimumWidth(86)
        browse.setMinimumHeight(30)
        browse.setAccessibleName('Browse for ' + caption.lower())
    if hasattr(window, 'generate_txt'):
        window.generate_txt.setText('Save a text report for each kit' if 'Kits' in title else 'Save a text report for each group')
    for tab, button in ((window.tab_process, window.run_build_btn), (window.tab_export, window.run_process_btn)):
        tab.layout().removeWidget(button)
        actions = QtWidgets.QHBoxLayout()
        actions.addStretch()
        button.setMinimumWidth(180)
        button.setMinimumHeight(38)
        button.setAutoDefault(False)
        actions.addWidget(button)
        tab.layout().addLayout(actions)
    for button in window.findChildren(QtWidgets.QPushButton):
        button.setAutoDefault(False)
    window.resize(900, 780)

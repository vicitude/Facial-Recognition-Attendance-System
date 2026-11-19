from PyQt5 import QtCore, QtGui, QtWidgets


STYLE = '''
QWidget { color: #303650; font-family: 'Microsoft YaHei UI'; font-size: 10pt; }
QMainWindow, QDialog, QWidget#workspace { background: #f5f6fc; }
QMessageBox { background: #f5f6fc; }
QMessageBox QLabel { background: transparent; }
QFrame#sidebar { background: #eef0fc; border-right: 1px solid #e1e4f4; }
QLabel#brand { color: #5b62bd; font-size: 18pt; font-weight: 700; }
QLabel#eyebrow { color: #7c83bc; font-size: 9pt; }
QLabel#pageTitle { font-size: 23pt; font-weight: 700; }
QLabel#sectionTitle { font-size: 13pt; font-weight: 700; }
QLabel#muted { color: #66708c; }
QLabel#resultName { font-size: 17pt; font-weight: 700; color: #6269bd; }
QLabel#dialogTitle { font-size: 18pt; font-weight: 700; color: #535cab; }
QLabel#badge { background: #eef1ff; color: #565ea7; border-radius: 10px; padding: 7px 12px; }
QFrame#card { background: white; border: 1px solid #e4e7f3; border-radius: 18px; }
QListWidget#navigation { background: transparent; border: none; outline: none; }
QListWidget#navigation::item { padding: 14px 12px; margin: 4px 0; border-radius: 12px; color: #66708c; }
QListWidget#navigation::item:selected { background: #dfe3fc; color: #525bb1; font-weight: 700; }
QListWidget#navigation::item:hover:!selected { background: #e6e9f9; }
QTabWidget::pane { border: none; background: transparent; }
QPushButton { background: white; border: 1px solid #dce0ee; border-radius: 10px; padding: 9px 16px; min-height: 20px; }
QPushButton:hover { background: #f0f1ff; border-color: #a4a9e6; }
QPushButton:pressed { background: #e2e5fa; }
QPushButton#primary { background: #7c83e8; color: white; border-color: #7c83e8; font-weight: 700; }
QPushButton#primary:hover { background: #6972d7; }
QPushButton#danger { color: #bd456a; background: #fff2f6; border-color: #f0d7e1; }
QPushButton:disabled, QPushButton#primary:disabled, QPushButton#danger:disabled { background: #eceef5; color: #939ab1; border-color: #e4e7f0; }
QLineEdit, QComboBox, QDateEdit { background: white; border: 1px solid #dce0ee; border-radius: 8px; padding: 7px; min-height: 22px; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border-color: #7c83e8; }
QTableWidget { background: white; alternate-background-color: #f7f8fe; border: 1px solid #e4e7f3; border-radius: 12px; gridline-color: #edf0f8; selection-background-color: #e5e8fc; selection-color: #303650; }
QHeaderView::section { background: #eef0fb; color: #626b89; padding: 10px; border: none; border-bottom: 1px solid #e4e7f3; }
QMenuBar, QStatusBar { background: #f5f6fc; color: #66708c; }
QMenu { background: white; border: 1px solid #e4e7f3; padding: 6px; }
QMenu::item { padding: 8px 24px; }
QMenu::item:selected { background: #e5e8fc; }
QLabel#videoCanvas { background: #232b46; color: #c5cee9; border: 2px solid #d7dcf7; border-radius: 16px; font-size: 14pt; }
'''


def apply_theme(widget: QtWidgets.QWidget) -> None:
    widget.setStyleSheet(STYLE)


def label(text: str, role: str = 'muted') -> QtWidgets.QLabel:
    widget = QtWidgets.QLabel(text)
    widget.setObjectName(role)
    widget.setWordWrap(True)
    return widget


def card(parent=None):
    widget = QtWidgets.QFrame(parent)
    widget.setObjectName('card')
    return widget


def configure_table(table, stretch_last=True):
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setFocusPolicy(QtCore.Qt.NoFocus)
    table.setTextElideMode(QtCore.Qt.ElideRight)
    table.verticalHeader().setDefaultSectionSize(42)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setDefaultAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
    table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(stretch_last)


def page_header(title, subtitle, count_text=None):
    widget = card()
    layout = QtWidgets.QHBoxLayout(widget)
    layout.setContentsMargins(20, 16, 20, 16)
    text = QtWidgets.QVBoxLayout()
    text.setSpacing(4)
    text.addWidget(label(title, 'sectionTitle'))
    text.addWidget(label(subtitle))
    layout.addLayout(text, 1)
    if count_text is not None:
        badge = label(count_text, 'badge')
        badge.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(badge)
    return widget


def card(parent=None):
    widget = QtWidgets.QFrame(parent)
    widget.setObjectName('card')
    return widget


def configure_table(table, stretch_last=True):
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setFocusPolicy(QtCore.Qt.NoFocus)
    table.setTextElideMode(QtCore.Qt.ElideRight)
    table.verticalHeader().setDefaultSectionSize(42)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setDefaultAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
    table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
    if stretch_last:
        table.horizontalHeader().setStretchLastSection(True)


def page_header(title, subtitle, count_text=None):
    widget = card()
    layout = QtWidgets.QHBoxLayout(widget)
    layout.setContentsMargins(20, 16, 20, 16)
    text = QtWidgets.QVBoxLayout()
    text.setSpacing(4)
    text.addWidget(label(title, 'sectionTitle'))
    text.addWidget(label(subtitle))
    layout.addLayout(text, 1)
    if count_text is not None:
        badge = label(count_text, 'badge')
        badge.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(badge)
    return widget


def prepare_dialog(dialog, title, subtitle, primary_button, minimum_width=480):
    apply_theme(dialog)
    dialog.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
    layout = dialog.layout()
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(16)
    layout.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
    layout.insertWidget(0, label(subtitle))
    layout.insertWidget(0, label(title, 'dialogTitle'))
    for form in dialog.findChildren(QtWidgets.QFormLayout):
        form.setVerticalSpacing(14)
        form.setHorizontalSpacing(16)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
    primary_button.setObjectName('primary')
    primary_button.style().unpolish(primary_button)
    primary_button.style().polish(primary_button)
    dialog.adjustSize()
    dialog.setMinimumSize(dialog.minimumSizeHint().expandedTo(QtCore.QSize(minimum_width, 0)))
    dialog.resize(dialog.sizeHint().expandedTo(dialog.minimumSize()))


class StarBanner(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(118)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        gradient = QtGui.QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QtGui.QColor('#e2e7ff'))
        gradient.setColorAt(1, QtGui.QColor('#f9e5f1'))
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(QtCore.QRectF(self.rect()), 16, 16)
        painter.setBrush(QtGui.QColor('#b6bbed'))
        painter.drawEllipse(QtCore.QPointF(self.width() - 46, 38), 20, 20)
        painter.setBrush(QtGui.QColor('#f2e5f5'))
        painter.drawEllipse(QtCore.QPointF(self.width() - 37, 30), 18, 18)
        painter.setPen(QtGui.QPen(QtGui.QColor('#929bd4'), 1.7))
        for horizontal, vertical, radius in [(0.15, 0.23, 4), (0.64, 0.3, 3), (0.83, 0.72, 5)]:
            center = QtCore.QPointF(self.width() * horizontal, self.height() * vertical)
            painter.drawLine(center + QtCore.QPointF(-radius, 0), center + QtCore.QPointF(radius, 0))
            painter.drawLine(center + QtCore.QPointF(0, -radius), center + QtCore.QPointF(0, radius))
        painter.setPen(QtGui.QColor('#59649d'))
        painter.setFont(QtGui.QFont('Microsoft YaHei UI', 12, QtGui.QFont.Bold))
        title_metrics = painter.fontMetrics()
        title_baseline = 22 + title_metrics.ascent()
        painter.drawText(18, title_baseline, '每一次相遇')
        painter.setFont(QtGui.QFont('Microsoft YaHei UI', 10))
        painter.drawText(18, title_baseline + title_metrics.descent() + 10 + painter.fontMetrics().ascent(), '都值得被记录')

    def sizeHint(self):
        title_metrics = QtGui.QFontMetrics(QtGui.QFont('Microsoft YaHei UI', 12, QtGui.QFont.Bold))
        detail_metrics = QtGui.QFontMetrics(QtGui.QFont('Microsoft YaHei UI', 10))
        return QtCore.QSize(title_metrics.horizontalAdvance('每一次相遇') + 44, max(118, title_metrics.height() + detail_metrics.height() + 54))

from PySide6.QtWidgets import QMessageBox
from .buttons import ButtonFactory

class MessageBox:
    @staticmethod
    def show_styled_message(parent, title, text, icon_type=QMessageBox.Icon.Information):
        msg = QMessageBox(parent)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(icon_type)
        ok_button = ButtonFactory.create_ok_button("OK")
        msg.addButton(ok_button, QMessageBox.ButtonRole.AcceptRole)
        msg.exec()
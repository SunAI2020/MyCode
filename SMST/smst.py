# This Python file uses the following encoding: utf-8
import sys
from PySide2.QtWidgets import QApplication, QMainWindow


class SMST(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)


if __name__ == "__main__":
    app = QApplication([])
    window = SMST()
    window.show()
    sys.exit(app.exec_())

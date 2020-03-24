import sys
from PyQt5.QtWidgets import (QWidget, QSlider, 
    QLabel, QApplication)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
 
 
class Example(QWidget):
    
    def __init__(self):
        super().__init__()
        
        self.initUI()
        
        
    def initUI(self):      
 
        sld = QSlider(Qt.Horizontal, self)
        sld.setFocusPolicy(Qt.NoFocus)
        sld.setGeometry(30,30, 300, 30)
        sld.valueChanged[int].connect(self.changeValue)
        
        self.label = QLabel(self)
        self.label.setPixmap(QPixmap('app.ico'))
        self.label.setGeometry(30, 60, 300,300)
        
        self.setGeometry(300, 300, 360, 390)
        self.setWindowTitle('QSlider')
        self.show()
        
        
    def changeValue(self, value):
 
        if value == 0:
            self.label.setPixmap(QPixmap('app.ico'))
        elif value > 0 and value <= 30:
            self.label.setPixmap(QPixmap('add1.jpg'))
        elif value > 30 and value < 80:
            self.label.setPixmap(QPixmap('exit.jpg'))
        else:
            self.label.setPixmap(QPixmap('ding1.jpg'))
            
 
if __name__ == '__main__':
 
    app = QApplication(sys.argv)
    ex = Example()
    sys.exit(app.exec_())    

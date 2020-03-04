import sys
from PyQt5.QtWidgets import (QWidget, QToolTip, QMessageBox,QDesktopWidget,
    QPushButton, QApplication)
from PyQt5.QtGui import QFont    
from PyQt5.QtCore import QCoreApplication 
 
class Example(QWidget):
    
    def __init__(self):
        super().__init__()
        
        self.initUI()
        self.center()
        
        
    def initUI(self):
        #这种静态的方法设置一个用于显示工具提示的字体。我们使用10px滑体字体。
        QToolTip.setFont(QFont('SansSerif', 10))
        
        #创建一个提示，我们称之为settooltip()方法。我们可以使用丰富的文本格式
        self.setToolTip('This is a <b>QWidget</b> widget')
        
        #创建一个PushButton并为他设置一个tooltip
        btn = QPushButton('Button', self)
        btn.setToolTip('This is a <b>QPushButton</b> widget')
        
        #btn.sizeHint()显示默认尺寸
        btn.resize(btn.sizeHint())
        
        #移动窗口的位置
        btn.move(50,70)       

        qbtn = QPushButton('Quit', self)
        qbtn.setToolTip('This is a <b>QUIT</b> widget')
        qbtn.clicked.connect(QCoreApplication.instance().quit)
        qbtn.resize(qbtn.sizeHint())
        qbtn.move(150, 70)
        
        self.setGeometry(400, 500, 300, 200)
        self.setWindowTitle('Tooltips')    
        self.show()

    def center(self):
        
        #获得窗口
        qr = self.frameGeometry()
        #获得屏幕中心点
        cp = QDesktopWidget().availableGeometry().center()
        #显示到屏幕中心
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def closeEvent(self, event):
         reply = QMessageBox.question(self, 'Message',"Are you sure to quit?", QMessageBox.Yes | 
            QMessageBox.No, QMessageBox.No)
         if reply == QMessageBox.Yes:
             event.accept()
         else:
             event.ignore()        
        
        
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    ex = Example()
    sys.exit(app.exec_())

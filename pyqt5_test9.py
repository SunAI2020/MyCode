import sys
from PyQt5.QtWidgets import QMainWindow, QAction, qApp, QApplication
from PyQt5.QtGui import QIcon
 
 
class Example(QMainWindow):
    
    def __init__(self):
        super().__init__()
        
        self.initUI()
        
        
    def initUI(self):               
        
        exitAction = QAction(QIcon('python.ico'), '&Exit', self)        
        exitAction.setShortcut('Ctrl+Q')
        exitAction.setStatusTip('Exit application')
        exitAction.triggered.connect(qApp.quit)
 
        self.statusBar()
 
        #创建一个菜单栏
        menubar = self.menuBar()
        #添加菜单
        fileMenu = menubar.addMenu('&File')
        #添加事件
        fileMenu.addAction(exitAction)

        fileMenu = menubar.addMenu('&Edit')
        fileMenu = menubar.addMenu('&Format')
        fileMenu = menubar.addMenu('&Run')
        fileMenu = menubar.addMenu('&Option')
        fileMenu = menubar.addMenu('&Window')
        fileMenu = menubar.addMenu('&Help')
        
        self.setGeometry(300, 300, 600, 500)
        self.setWindowTitle('Menubar')
        
        self.statusBar().showMessage('Ready to GO!!!')
    
        self.toolbar = self.addToolBar('Exit')
        self.toolbar.addAction(exitAction)
        self.show()
        
        
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    ex = Example()
    sys.exit(app.exec_())  
        

        

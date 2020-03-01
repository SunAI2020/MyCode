from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Ellipse

class TestApp(App):
     def build(self):
        return Button(text='iPaoMi')
    
TestApp().run()

class MyWidget(Widget):
    def on_touch_down(self, touch):
        print(touch)
        return Label(text='Hello world')

class MyPaintApp(App):
    def build(self):
        return MyWidget()

if __name__ == '__main__':
    MyPaintApp().run()

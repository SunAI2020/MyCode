from kivy.app import App
from kivy.uix.button import Button
class TestApp(App):
     def build(self):
         return Button(text='iPaoMi')
TestApp().run()

import kivy
kivy.require('1.11.1') # 用你当前的kivy版本替换
from kivy.app import App
from kivy.uix.label import Label
class MyApp(App):
    def build(self):
        return Label(text='Hello world')

if __name__ == '__main__':
    MyApp().run()

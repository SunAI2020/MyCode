from flask import Flask
from flask import render_template
from random import randint

app = Flask(__name__)
@app.route('/')
def Hello_world():
    return render_template('hello_world.html')
if __name__=='__main__':
    app.run()

# -*- coding: utf-8 -*-
"""
Created on Wed Apr  8 15:14:49 2020

@author: sun
"""

import pandas as pd
df=pd.read_csv('data.csv')
a=df
a=df.loc[1,:]
df=df.set_index('名称')
a=df.loc['苹果',:]
a=df.iloc[2,1]
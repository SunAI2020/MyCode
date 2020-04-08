# -*- coding: utf-8 -*-
"""
Spyder 编辑器

这是一个临时脚本文件。
"""

import pandas as pd
df=pd.read_csv('d:\\github\\mycode\\data.csv')

a=df.iloc[1,1]
df=df.set_index('名称')
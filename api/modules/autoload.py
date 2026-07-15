import os
import re
import sys



''' system paths'''
rootdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rootdir = re.sub(r'\\', '/', rootdir)
sys.path.insert(0, rootdir + r'/modules')

''' reading config files '''
from config import Config
try:
    Config.load(file=rootdir + '/ini.yaml')
except FileNotFoundError:
    pass    
try:
    Config.load(file=rootdir + '/env.yaml')
except FileNotFoundError:
    pass

Config.rootdir = rootdir

'''    
if Config.paths:
    for name, path in Config.paths.items():
        Config.paths[name] = rootdir + '/' + path
'''
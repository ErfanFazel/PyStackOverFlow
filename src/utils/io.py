import json 
def read_json(filename):
    with open(filename) as f:
        return json.load()
    
def write_json(data,filename,indent=4):
    with open(filename,'w') as f:
        json.dump(data, f,indent=indent)
def read_file(filename):
    with open(filename) as f:
        return json.load(f)       
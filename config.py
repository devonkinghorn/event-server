

class Config:
    def __init__(self,fileName):
        with open(fileName) as f:
            lines = f.readlines()
            self.media = {}
            self.hosts = {}
            self.parameters = {}
            for line in lines:
                if line != '':
                    line = line.replace('\n','')
                    line = line.split(' ')
                    if line[0] == 'host':
                        self.hosts[line[1]] = line[2]
                    elif line[0] == 'media':
                        self.media[line[1]] = line[2]
                    elif line[0] == 'parameter':
                        self.parameters[line[1]] = line[2]
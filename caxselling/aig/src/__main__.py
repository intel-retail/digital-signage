#Arguments
import sys
import os
import argparse

#Server
sys.path.append('./src')
from server.aig_server import AigServer

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=os.getenv('AIG_PORT'))
    args = parser.parse_args()



    aigserver = AigServer()
    #Registering the clean up function    
    aigserver.run(hostname="0.0.0.0", pport=args.port, pdebug=True,)

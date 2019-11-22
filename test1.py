#!/usr/bin/env python3

import grpc, sys
from buildgrid.client.cas import Uploader

if __name__ == '__main__':
    channel = grpc.insecure_channel('localhost:50051')
    upme = Uploader(channel)
    print(upme.upload_directory(sys.argv[1]))
    upme.flush()
    upme.close()

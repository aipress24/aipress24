import sys

from .main import serve

if __name__ == "__main__":
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
        serve(port=port)
    else:
        serve()

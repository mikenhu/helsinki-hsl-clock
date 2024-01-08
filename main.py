from hyperpixel2r import Hyperpixel2r
from transport import Transport

def main():
    display = Hyperpixel2r()
    transport = Transport(display)
    
    transport.run()  # Run the clock

if __name__ == "__main__":
    main()
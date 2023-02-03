from models import Time

if __name__ == '__main__':
    time = Time(10, 200, True)
    time.start()
    time.join()

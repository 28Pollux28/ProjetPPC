import signal
import time

stateSignal = 0
eventID = []
duration = []
factor = []
impact = []


def convertArrayToBinary(array):
    print(array)
    binaryStr = ''.join(str(e) for e in array)
    print(binaryStr)
    integer = int(binaryStr, 2)
    print(integer)
    return integer


def handler(signum, frame):
    global stateSignal, eventID, duration, factor, impact
    print('Signal handler called with signal', signum)

    if stateSignal ==0:
        if signum == signal.SIGALRM:
            print(eventID)
            stateSignal+=1
        elif signum == signal.SIGUSR1:
            eventID.append(0)
        else:
            eventID.append(1)
    elif stateSignal==1:
        if signum == signal.SIGALRM:
            print(duration)
            stateSignal+=1
        elif signum == signal.SIGUSR1:
            duration.append(0)
        else:
            duration.append(1)
    elif stateSignal==2:
        if signum == signal.SIGALRM:
            print(factor)
            stateSignal += 1
        elif signum == signal.SIGUSR1:
            factor.append(0)
        else:
            factor.append(1)
    elif stateSignal==3:
        if signum == signal.SIGALRM:
            print(impact)
            stateSignal += 1
            eventNum = convertArrayToBinary(eventID)
            durationNum = convertArrayToBinary(duration)
            factorNum = convertArrayToBinary(factor)
            impactNum = convertArrayToBinary(impact)
            print(eventNum, durationNum, factorNum, impactNum)
            eventID, duration, factor, impact = [], [], [], []
            stateSignal = 0
        elif signum == signal.SIGUSR1:
            impact.append(0)
        else:
            impact.append(1)

# Set the signal handler and a 5-second alarm


signal.signal(signal.SIGALRM, handler)
signal.signal(signal.SIGUSR1, handler)
signal.signal(signal.SIGUSR2, handler)
# signal.pthread_sigmask(signal.SIG_SETMASK,[signal.SIGALRM,signal.SIGUSR1])
# signal.alarm(2)
# signal.raise_signal(signal.NSIG)
signal.raise_signal(signal.SIGUSR2)
signal.raise_signal(signal.SIGUSR1)
signal.raise_signal(signal.SIGUSR2)
signal.raise_signal(signal.SIGUSR1)
signal.raise_signal(signal.SIGUSR2)
signal.raise_signal(signal.SIGALRM)
signal.raise_signal(signal.SIGUSR1)
signal.raise_signal(signal.SIGUSR2)
signal.raise_signal(signal.SIGALRM)
signal.raise_signal(signal.SIGUSR1)
signal.raise_signal(signal.SIGUSR2)
signal.raise_signal(signal.SIGALRM)
signal.raise_signal(signal.SIGUSR1)
signal.raise_signal(signal.SIGUSR2)
signal.raise_signal(signal.SIGALRM)

time.sleep(4)

# signal.pthread_sigmask(signal.SIG_UNBLOCK, [signal.SIGALRM,signal.SIGUSR1])

time.sleep(3)


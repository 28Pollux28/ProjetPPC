import multiprocessing
import os
import signal
import threading
import random
import time
from typing import *

from utils.utils import convertArrayToBinary, convertDecimalToBinary


class ExternalEvent:

    CENTRALE_EXPLOSION = {'id': 0, 'probability': 0.05, 'maxDuration': 7, 'betaMax': 0.5, 'impactMax': 0.5}
    FUEL_SHORTAGE = {'id': 1, 'probability': 0.1, 'maxDuration': 2, 'betaMax': 0.7, 'impactMax': 0.6}
    STRIKE = {'id': 2, 'probability': 0.1, 'maxDuration': 3, 'betaMax': 0.2, 'impactMax': 0.3}
    ECONOMIC_CRISIS = {'id': 3, 'probability': 0.1, 'maxDuration': 5, 'betaMax': 0.3, 'impactMax': 0.4}

    EVENTS = [CENTRALE_EXPLOSION, FUEL_SHORTAGE, STRIKE, ECONOMIC_CRISIS]


    def __init__(self, id, duration, beta, impact):
        self.id = id
        self.duration = duration
        self.beta = beta
        self.impact = impact



class Home(multiprocessing.Process):
    def __init__(self, start_new_day_barrier,sharedWH):
        super().__init__()
        self.start_new_day_barrier = start_new_day_barrier
        self.sharedWH = sharedWH

    def run(self) -> None:
        pass


class Market(multiprocessing.Process):
    def __init__(self, start_new_day_barrier, sharedWH, startPrice:float, gamma:float, demandAlpha:float, internalFactorsAlpha: List[float], externalEvents: List[ExternalEvent]):
        super().__init__()
        self.external: External = None
        self.start_new_day_barrier = start_new_day_barrier
        self.sharedWH = sharedWH
        self.price = startPrice
        self.gamma = gamma
        self.internalFactorsAlpha = internalFactorsAlpha # factors for weather
        self.externalEvents: List[ExternalEvent] = externalEvents
        self.demand = 1
        self.demandAlpha = demandAlpha
        self.stateSignal=0
        self.eventID, self.duration, self.factor, self.impact = [], [], [], []

    def calcContributionFactors(self):
        total = 0
        for extFact in self.externalEvents:
            total += extFact.impact*extFact.beta
            extFact.duration-=1
            if extFact.duration <=0:
                self.externalEvents.remove(extFact)
        return total

    def calcPrice(self):
        self.price = self.gamma * self.price + self.calcContributionFactors()

    def handler(self, signum, frame):
        if self.stateSignal == 0:
            if signum == signal.SIGALRM:
                self.stateSignal += 1
            elif signum == signal.SIGUSR1:
                self.eventID.append(0)
            else:
                self.eventID.append(1)
        elif self.stateSignal == 1:
            if signum == signal.SIGALRM:
                self.stateSignal += 1
            elif signum == signal.SIGUSR1:
                self.duration.append(0)
            else:
                self.duration.append(1)
        elif self.stateSignal == 2:
            if signum == signal.SIGALRM:
                self.stateSignal += 1
            elif signum == signal.SIGUSR1:
                self.factor.append(0)
            else:
                self.factor.append(1)
        elif self.stateSignal == 3:
            if signum == signal.SIGALRM:
                self.stateSignal += 1
                eventNum = convertArrayToBinary(self.eventID)
                durationNum = convertArrayToBinary(self.duration)
                factorNum = convertArrayToBinary(self.factor)
                impactNum = convertArrayToBinary(self.impact)
                self.externalEvents.append(ExternalEvent(eventNum, durationNum, factorNum, impactNum))
                self.eventID, self.duration, self.factor, self.impact = [], [], [], []
                self.stateSignal = 0
            elif signum == signal.SIGUSR1:
                self.impact.append(0)
            else:
                self.impact.append(1)

    def run(self) -> None:
        signal.signal(signal.SIGALRM, self.handler)
        signal.signal(signal.SIGUSR1, self.handler)
        signal.signal(signal.SIGUSR2, self.handler)
        self.external = External(self.start_new_day_barrier)

class Weather(multiprocessing.Process):
    def __init__(self, start_new_day_barrier, sharedWH):
        super().__init__()
        self.start_new_day_barrier = start_new_day_barrier
        self.sharedWH = sharedWH

    def run(self) -> None:
        pass


class External(multiprocessing.Process):

    def __init__(self, start_new_day_barrier: threading.Barrier):
        super().__init__()
        self.start_new_day_barrier: threading.Barrier = start_new_day_barrier
        self.ppid = os.getppid()

    def sendSignal(self, signum):
        os.kill(self.ppid, signum)

    def sendExternalEvent(self, eventID, duration, factor, impact):
        # encode eventID, duration, factor, impact to binary
        eventIDBin = convertDecimalToBinary(eventID)
        durationBin = convertDecimalToBinary(duration)
        factorBin = convertDecimalToBinary(factor*10)
        impactBin = convertDecimalToBinary(impact*10)
        # send signals
        for eBin in [eventIDBin, durationBin, factorBin, impactBin]:
            for i in range(len(eBin)):
                if eBin[i] == 0:
                    self.sendSignal(signal.SIGUSR1)
                else:
                    self.sendSignal(signal.SIGUSR2)
            self.sendSignal(signal.SIGALRM)

    def run(self) -> None:
        self.start_new_day_barrier.wait()
        # generate new event
        event = random.choice(ExternalEvent.EVENTS)
        if random.random() < event['probability']:
            id = event['id']
            duration = random.randint(0, event['durationMax'])
            beta = random.uniform(0, event['betaMax'])
            # round to 1 decimal place
            beta = round(beta, 1)
            impact = random.uniform(0, event['impactMax'])
            impact = round(impact, 1)
            self.sendExternalEvent(id, duration, beta, impact)



class Time(multiprocessing.Process):
    def __init__(self, nHomes):
        super().__init__()
        self.sharedWH: multiprocessing.Array = None
        self.market: Market = None
        self.homes: List[Home] = None
        self.weather: Weather = None
        self.day = 0
        self.nHomes = nHomes
        self.start_new_day_barrier = threading.Barrier(3+nHomes, action=self.startNewDay)

    def startNewDay(self):
        self.day += 1
        print("Good Morning, it is day : "+str(self.day))


    def createWeather(self):
        self.weather = Weather(self.start_new_day_barrier, self.sharedWH)
        self.weather.start()

    def createHomes(self):
        self.homes = [Home(self.start_new_day_barrier, self.sharedWH) for _ in range(self.nHomes)]
        for h in self.homes:
            h.start()

    def createMarket(self):
        self.market = Market(self.start_new_day_barrier, self.sharedWH, 0.17, 0.99, 0.5, [], [])

    def run(self):
        self.sharedWH = multiprocessing.Array('i', range(10)) # 0: Température
        self.createWeather()
        self.createHomes()
        self.createMarket()


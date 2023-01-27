import multiprocessing as mp
import os
import signal
import random
import time
from typing import *

import sysv_ipc

from utils.utils import convertArrayToBinary, convertDecimalToBinary


class ExternalEvent:

    CENTRALE_EXPLOSION = {'id': 0, 'probability': 0.05, 'durationMax': 7, 'betaMax': 0.5, 'impactMax': 0.5}
    FUEL_SHORTAGE = {'id': 1, 'probability': 0.1, 'durationMax': 2, 'betaMax': 0.7, 'impactMax': 0.6}
    STRIKE = {'id': 2, 'probability': 0.1, 'durationMax': 3, 'betaMax': 0.2, 'impactMax': 0.3}
    ECONOMIC_CRISIS = {'id': 3, 'probability': 0.1, 'durationMax': 5, 'betaMax': 0.3, 'impactMax': 0.4}

    EVENTS = [CENTRALE_EXPLOSION, FUEL_SHORTAGE, STRIKE, ECONOMIC_CRISIS]

    def __init__(self, id, duration, beta, impact):
        self.id = id
        self.duration = duration
        self.beta = beta
        self.impact = impact


class Home(mp.Process):
    def __init__(self, id: int ,start_new_day_barrier: mp.Barrier, home_barrier: mp.Barrier,sharedWH, consumerKey: int, producerKey: int, transactionKey: int, production: int, consumption: int, producerType: int, maxDays: int, lock):
        super().__init__()
        self.id = id
        self.start_new_day_barrier = start_new_day_barrier
        self.home_barrier = home_barrier
        self.sharedWH = sharedWH
        self.consumerKey = consumerKey
        self.producerKey = producerKey
        self.transactionKey = transactionKey
        self.production = production
        self.consumption = consumption
        self.producerType = producerType
        self.maxDays = maxDays
        self.energy = 0
        self.lock = lock

    def log(self, message: str):
        self.lock.acquire()
        print("Home {} : {}".format(self.id, message))
        self.lock.release()

    def logCarac(self):
        self.lock.acquire()
        print("Home {} : pid = {}, production = {}, consumption = {}, producerType = {}, energy = {}".format(self.id, os.getpid(),self.production, self.consumption, self.producerType, self.energy))
        self.lock.release()

    def sellToHomes(self, consumerMQ, producerMQ, transactionMQ):
        while self.energy > 0 and (consumerMQ.current_messages > 0 or consumerMQ.last_send_time > time.time() - 1 or
                                   consumerMQ.last_receive_time > time.time() - 1):
            try:
                message, mType = consumerMQ.receive(block=False, type=1)
                msg = message.decode()
                clientRequest = msg.split(",")
                clientID = int(clientRequest[0])
                energyAsked = int(clientRequest[1])
                energySent = min(self.energy, energyAsked)
                self.log("Home {} sent {} energy to Home {}".format(self.id, energySent, clientID))
                self.energy -= energySent
                transactionMQ.send(str(energySent).encode(), type=clientID)
            except sysv_ipc.BusyError:
                pass

        if self.energy == 0:
            producerMQ.receive(block=False, type=self.pid)

    def buyFromHomes(self, consumerMQ, producerMQ, transactionMQ):
        while self.energy < 0 and producerMQ.current_messages > 0:
            try:
                # print("Home {} is waiting for energy".format(self.id))
                message, mType = transactionMQ.receive(block=False, type=self.pid)
                msg = message.decode()
                energyReceived = int(msg)
                self.energy += energyReceived
                self.log("Home {} received {} energy".format(self.id, energyReceived))
                # print("received energy :" + str(energyReceived))
                if self.energy < 0:

                    consumerMQ.send((str(self.pid) + "," + str(abs(self.energy))).encode(), type=1)
            except sysv_ipc.BusyError:
                pass
        self.log("Home {} has finished transactions with other homes".format(self.id))

    def sellMarket(self):
        pass

    def buyFromMarket(self):
        '''
        Buy from market to cover the energy deficit
        :param energy: negative value that represents the energy deficit
        :return:
        '''
        print("Home {} is buying {} energy from market".format(self.id, abs(self.energy)))

    def run(self) -> None:
        day = 0
        try:
            consumerMQ = sysv_ipc.MessageQueue(self.consumerKey, sysv_ipc.IPC_CREX)
        except sysv_ipc.ExistentialError:
            consumerMQ = sysv_ipc.MessageQueue(self.consumerKey)
        try:
            producerMQ = sysv_ipc.MessageQueue(self.producerKey, sysv_ipc.IPC_CREX)
        except sysv_ipc.ExistentialError:
            producerMQ = sysv_ipc.MessageQueue(self.producerKey)
        try:
            transactionMQ = sysv_ipc.MessageQueue(self.transactionKey, sysv_ipc.IPC_CREX)
        except sysv_ipc.ExistentialError:
            transactionMQ = sysv_ipc.MessageQueue(self.transactionKey)
        if self.id == 0:
            print(transactionMQ.current_messages)
            for i in range(transactionMQ.current_messages):
                print(i)
                transactionMQ.receive()
            print("emptied transaction queue")
            for i in range(consumerMQ.current_messages):
                consumerMQ.receive()
            for i in range(producerMQ.current_messages):
                producerMQ.receive()

        while day < self.maxDays:
            print("Home {} is waiting for a new day".format(self.id))
            self.start_new_day_barrier.wait()
            day += 1
            self.energy = self.production - self.consumption
            self.logCarac()

            if self.energy < 0:
                self.log("Home {} have {} energy deficit".format(self.id, abs(self.energy)))
                consumerMQ.send((str(self.pid) + "," + str(abs(self.energy))).encode(), type=1)
                self.home_barrier.wait()
                self.buyFromHomes(consumerMQ, producerMQ, transactionMQ)
                if self.energy < 0:
                    self.buyFromMarket()
                self.home_barrier.wait()
            else:
                if self.producerType != 0:
                    self.log("Home {} have {} energy available to consumer".format(self.id, self.energy))
                    producerMQ.send(str(self.pid).encode(), type=self.pid)
                    self.home_barrier.wait()
                    self.sellToHomes(consumerMQ, producerMQ, transactionMQ)
                    if self.producerType == 1 and self.energy > 0:
                        self.log("Home {} is selling {} energy to the market".format(self.id, self.energy))
                        self.sellMarket()
                    self.home_barrier.wait()
                else:
                    self.home_barrier.wait()
                    self.log("Home {} is selling {} energy directly to the market".format(self.id, self.energy))
                    self.sellMarket()
                    self.home_barrier.wait()


            if self.id == 0:
                print(transactionMQ.current_messages)
                for i in range(transactionMQ.current_messages):
                    print(i)
                    transactionMQ.receive()
                print("emptied transaction queue")
                for i in range(consumerMQ.current_messages):
                    consumerMQ.receive()
                for i in range(producerMQ.current_messages):
                    producerMQ.receive()












            # transactionMQ.send("".encode(), type=1)
            # transactionMQ.receive(type=1)
            # # print("Home {} is starting a new day".format(self.id))
            #
            # # Calculate Production vs Consumption
            #
            # print("Home {} has {} energy".format(self.id, energy))
            # if energy > 0:
            #     if self.producerType == 0:
            #         # Sell all to market
            #         self.sellMarket(energy)
            #     elif self.producerType == 1:
            #         # Sell to homes and then to market
            #         energyLeft = self.sellToHomes(consumerMQ, transactionMQ, energy)
            #         if energyLeft > 0:
            #             self.sellMarket(energyLeft)
            #
            #     else:
            #         # Sell all to homes and nether to market
            #         self.sellToHomes(consumerMQ, transactionMQ, energy)
            # else:
            #     consumerMQ.send((str(os.getpid()) + "," + str(abs(self.energy))).encode(), type=1)
            #     self.buyFromHomes(consumerMQ, transactionMQ)
            #     if self.energy < 0:
            #         self.buyFromMarket()




class Market(mp.Process):
    def __init__(self, start_new_day_barrier, sharedWH, startPrice:float, gamma:float, demandAlpha:float, internalFactorsAlpha: List[float], externalEvents: List[ExternalEvent], maxDays: int):
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
        self.day = 0
        self.maxDays = maxDays

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
                eventNum = convertArrayToBinary(self.eventID)
                durationNum = convertArrayToBinary(self.duration)
                factorNum = convertArrayToBinary(self.factor)
                impactNum = convertArrayToBinary(self.impact)
                self.externalEvents.append(ExternalEvent(eventNum, durationNum, factorNum/10, impactNum/10))
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
        while self.day < self.maxDays:
            self.start_new_day_barrier.wait()
            self.day += 1
        self.terminate()

class Weather(mp.Process):
    def __init__(self, start_new_day_barrier, sharedWH):
        super().__init__()
        self.start_new_day_barrier = start_new_day_barrier
        self.sharedWH = sharedWH

    def run(self) -> None:
        pass


class External(mp.Process):

    def __init__(self, start_new_day_barrier: mp.Barrier, maxDays):
        super().__init__()
        self.start_new_day_barrier: mp.Barrier = start_new_day_barrier
        self.ppid = os.getppid()
        self.day = 0
        self.maxDays = maxDays

    def sendSignal(self, signum):
        os.kill(self.ppid, signum)

    def sendExternalEvent(self, eventID, duration, factor, impact):
        # encode eventID, duration, factor, impact to binary
        eventIDBin = convertDecimalToBinary(eventID)
        durationBin = convertDecimalToBinary(duration)
        factorBin = convertDecimalToBinary(int(factor*10))
        impactBin = convertDecimalToBinary(int(impact*10))
        # send signals
        for eBin in [eventIDBin, durationBin, factorBin, impactBin]:
            for i in range(len(eBin)):
                if eBin[i] == 0:
                    self.sendSignal(signal.SIGUSR1)
                else:
                    self.sendSignal(signal.SIGUSR2)
            self.sendSignal(signal.SIGALRM)

    def run(self) -> None:
        while self.day< self.maxDays:
            # wait for new day
            self.start_new_day_barrier.wait()
            self.day += 1
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




class Time(mp.Process):
    def __init__(self, nHomes, maxDays):
        super().__init__()
        self.sharedWH: mp.Array = None
        self.market: Market = None
        self.homes: List[Home] = None
        self.weather: Weather = None
        self.day = 0
        self.nHomes = nHomes
        self.maxDays = maxDays
        self.start_new_day_barrier = mp.Barrier(nHomes+1)
        self.lock = mp.Lock()

    def startNewDay(self):
        self.day += 1
        self.lock.acquire()
        print("Good Morning, it is day : "+str(self.day))
        self.lock.release()

    def createWeather(self):
        self.weather = Weather(self.start_new_day_barrier, self.sharedWH)
        self.weather.start()

    def createHomes(self):

        home_barrier = mp.Barrier(self.nHomes)
        self.homes = [Home(i, self.start_new_day_barrier, home_barrier,self.sharedWH, 128, 192, 256, random.randint(50, 100), random.randint(50,100), random.randint(0,2), self.maxDays, self.lock) for i in range(self.nHomes)]
        for h in self.homes:
            print("starting home "+str(h.id)+"...")
            h.start()

    def createMarket(self):
        self.market = Market(self.start_new_day_barrier, self.sharedWH, 0.17, 0.99, 0.5, [], [])

    def run(self):
        self.sharedWH = mp.Array('i', range(10)) # 0: Température
        # self.createWeather()
        self.createHomes()
        # self.createMarket()
        while self.day < self.maxDays:
            self.start_new_day_barrier.wait()
            self.startNewDay()
            time.sleep(4)
        print("ending time...")
        for h in self.homes:
            h.join()
            print(h.id)
        print("home joined")
        # self.market.join()
        # self.weather.join()



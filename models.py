import concurrent.futures
import datetime
import errno
import math
import multiprocessing as mp
import os
import select
import signal
import random
import socket
import sys
import threading
import time
from typing import *

import numpy as np
import sysv_ipc
from matplotlib import pyplot as plt, animation
from matplotlib.colors import ListedColormap
from scipy.stats import norm

from utils.utils import convertArrayToBinary, convertDecimalToBinary


class ExternalEvent:
    CENTRALE_EXPLOSION = {'id': 0, 'probability': 0.005, 'durationMax': 7, 'betaMax': 0.5,
                          'name': "Explosion d'une centrale"}
    FUEL_SHORTAGE = {'id': 1, 'probability': 0.01, 'durationMax': 2, 'betaMax': 0.4, 'name': "Pénurie de carburant"}
    # STRIKE = {'id': 2, 'probability': 0.1, 'durationMax': 3, 'betaMax': 0.2, 'name': "Grèves"}
    ECONOMIC_CRISIS = {'id': 3, 'probability': 0.002, 'durationMax': 5, 'betaMax': 0.6, 'name': "Crise économique"}
    WAR = {'id': 4, 'probability': 0.001, 'durationMax': 10, 'betaMax': 0.8, 'name': "Guerre"}

    EVENTS = [CENTRALE_EXPLOSION, FUEL_SHORTAGE, ECONOMIC_CRISIS, WAR]

    def __init__(self, id, duration, beta, eventNumber):
        self.id = id
        self.duration = duration
        self.beta = beta
        self.eventNumber = eventNumber
        self.initialDuration = duration


class Home(mp.Process):
    def __init__(self, id: int, start_new_day_barrier: mp.Barrier, home_barrier: mp.Barrier, sharedWH, consumerKey: int,
                 producerKey: int, transactionKey: int, production: int, consumption: int, producerType: int,
                 maxDays: int, marketBarrier: mp.Barrier, logLock):
        super().__init__()
        self.id = id
        self.name = "Home {}".format(id)
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
        self.marketBarrier = marketBarrier
        self.logLock = logLock
        self.host = "localhost"
        self.port = 6226

    def log(self, message: str):
        # self.logLock.acquire()
        # print("Home {} : {}".format(self.id, message))
        # self.logLock.release()
        pass

    def logCarac(self):
        # self.logLock.acquire()
        # print("Home {} : pid = {}, production = {}, consumption = {}, producerType = {}, energy = {}".format(self.id,
        #                                                                                                      os.getpid(),
        #                                                                                                      self.production,
        #                                                                                                      self.consumption,
        #                                                                                                      self.producerType,
        #                                                                                                      self.energy))
        # self.logLock.release()
        pass

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

        producerMQ.receive(block=False, type=self.pid)
        self.log("Home {} has finished transactions with other homes".format(self.id))

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
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((self.host, self.port))
            message = "sell," + str(abs(self.energy))
            client_socket.send(message.encode())
            resp = client_socket.recv(1024)
            if not len(resp):
                print("The socket connection has been closed!")
                sys.exit(1)
            receive = resp.decode().split(',')
            self.energy -= int(receive[0])
            price = float(receive[1])
            self.log("Home {} sold {} energy to market at price {}€".format(self.id, int(receive[0]), price))
            client_socket.close()

    def buyFromMarket(self):
        '''
        Buy from market to cover the energy deficit
        :param energy: negative value that represents the energy deficit
        :return:
        '''
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((self.host, self.port))
            message = "buy," + str(abs(self.energy))
            client_socket.send(message.encode())
            resp = client_socket.recv(1024)
            if not len(resp):
                self.log("The socket connection has been closed!")

            receive = resp.decode().split(',')
            self.energy += int(receive[0])
            price = float(receive[1])
            self.log("Home {} bought {} energy to market at price {}€".format(self.id, int(receive[0]), price))
            client_socket.close()

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
        self.emptyQueues(consumerMQ, producerMQ, transactionMQ)

        while day < self.maxDays:
            self.start_new_day_barrier.wait()
            # wait for weather to be calculated
            self.start_new_day_barrier.wait()
            # Wait for data to be printed
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
                    self.log("Home {} is waiting at market barrier".format(self.id))
                    self.marketBarrier.wait()
                    self.log("Home {} is buying {} energy from the market".format(self.id, abs(self.energy)))
                    self.buyFromMarket()
                else:
                    self.marketBarrier.wait()
            else:
                if self.producerType != 0:
                    self.log("Home {} have {} energy available to consumer".format(self.id, self.energy))
                    producerMQ.send(str(self.pid).encode(), type=self.pid)
                    self.home_barrier.wait()
                    self.sellToHomes(consumerMQ, producerMQ, transactionMQ)
                    if self.producerType == 1 and self.energy > 0:
                        self.log("Home {} is waiting at market barrier".format(self.id))
                        self.marketBarrier.wait()
                        self.log("Home {} is selling {} energy to the market".format(self.id, self.energy))
                        self.sellMarket()
                    else:
                        self.log("Home {} is waiting at market barrier".format(self.id))
                        self.marketBarrier.wait()
                else:
                    self.home_barrier.wait()
                    self.log("Home {} is waiting at market barrier".format(self.id))
                    self.marketBarrier.wait()
                    self.log("Home {} is selling {} energy directly to the market".format(self.id, self.energy))
                    self.sellMarket()
            self.home_barrier.wait()
            if self.id == 0:
                self.stopMarket()
                self.emptyQueues(consumerMQ, producerMQ, transactionMQ)
        self.home_barrier.wait()
        if self.id == 0:
            consumerMQ.remove()
            producerMQ.remove()
            transactionMQ.remove()

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

    def emptyQueues(self, consumerMQ, producerMQ, transactionMQ):
        for i in range(transactionMQ.current_messages):
            transactionMQ.receive()
        for i in range(consumerMQ.current_messages):
            consumerMQ.receive()
        for i in range(producerMQ.current_messages):
            producerMQ.receive()

    def stopMarket(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((self.host, self.port))
            message = "end"
            client_socket.send(message.encode())


class Market(mp.Process):
    def __init__(self, start_new_day_barrier, sharedWH, startPrice: float, gamma: float, demandAlpha: float,
                 internalFactorsAlpha: List[float], externalEvents: List[ExternalEvent], maxDays: int,
                 marketBarrier: mp.Barrier, logLock: mp.Lock, marketDataBarrier: mp.Barrier, marketTimeChildPipe):
        super().__init__()
        self.serve = None
        self.external: External = None
        self.start_new_day_barrier = start_new_day_barrier
        self.sharedWH = sharedWH
        self.price = startPrice
        self.gamma = gamma
        self.internalFactorsAlpha = internalFactorsAlpha  # factors for weather
        self.externalEvents: List[ExternalEvent] = externalEvents
        self.demand = 1
        self.demandAlpha = demandAlpha
        self.stateSignal = 0
        self.eventID, self.duration, self.factor = [], [], []
        self.day = 0
        self.maxDays = maxDays
        self.marketLock = mp.Lock()
        self.host = "localhost"
        self.port = 6226
        self.dayResults = 0
        self.externalBarrier = mp.Barrier(2)
        self.marketBarrier = marketBarrier
        self.logLock = logLock
        self.marketDataBarrier = marketDataBarrier
        self.marketTimeChildPipe = marketTimeChildPipe
        self.eventNumber = 0

    def log(self, msg):
        pass
        # with self.logLock:
        #     print("Market: {}".format(msg))

    def calcContributionFactors(self):
        total = 0
        for extFact in self.externalEvents:
            total += 1 * extFact.beta
            extFact.duration -= 1
        # Temperature
        if self.sharedWH[0] > 25:
            total += abs(25 - self.sharedWH[0])/200 * self.internalFactorsAlpha[0]
        elif self.sharedWH[0] < 10:
            total += abs(10 - self.sharedWH[0])/200 * self.internalFactorsAlpha[0]
        return total

    def updateExternalEvents(self):
        for extFact in self.externalEvents:
            if extFact.duration <= 0:
                self.externalEvents.remove(extFact)

    def calcPrice(self):
        self.price = self.gamma * self.price + self.calcContributionFactors() + self.demand * self.demandAlpha

    def calcDemand(self):
        self.demand -= self.dayResults / 20
        self.demand = 0.7 + 0.2 * self.demand
        # self.demand *= abs(2-self.demand)
        if self.demand < 0:
            self.demand = 0

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
                eventNum = convertArrayToBinary(self.eventID)
                durationNum = convertArrayToBinary(self.duration)
                factorNum = convertArrayToBinary(self.factor)
                self.eventNumber += 1
                self.externalEvents.append(ExternalEvent(eventNum, durationNum, factorNum / 10, self.eventNumber))
                self.eventID, self.duration, self.factor = [], [], []
                self.stateSignal = 0
                self.log("New external event: {} {} {}".format(eventNum, durationNum, factorNum / 10))
            elif signum == signal.SIGUSR1:
                self.factor.append(0)
            else:
                self.factor.append(1)

    def handle_home(self, conn: socket.socket, addr):
        with conn:
            data = conn.recv(1024)
            m = data.decode()
            messages = m.split(',')
            if messages[0] == "buy":
                self.marketLock.acquire()
                self.dayResults -= int(messages[1])
                self.marketLock.release()
                conn.send((messages[1] + ',' + str(self.price)).encode())
                conn.close()
            elif messages[0] == "sell":
                self.marketLock.acquire()
                self.dayResults += int(messages[1])
                self.marketLock.release()
                conn.send((messages[1] + ',' + str(self.price)).encode())
                conn.close()
            elif messages[0] == "end":
                self.serve = False
                conn.close()
                return

    def run(self) -> None:
        signal.signal(signal.SIGALRM, self.handler)
        signal.signal(signal.SIGUSR1, self.handler)
        signal.signal(signal.SIGUSR2, self.handler)
        self.external = External(self.start_new_day_barrier, self.maxDays, self.externalBarrier, self.pid)
        self.external.start()
        while self.day < self.maxDays:
            self.start_new_day_barrier.wait()
            self.start_new_day_barrier.wait()
            self.marketDataBarrier.wait()
            # send data to Time
            self.marketTimeChildPipe.send([self.price, self.dayResults, self.demand, self.externalEvents])
            # print("sent data to Time")
            self.start_new_day_barrier.wait()
            self.day += 1
            self.log("Day {}".format(self.day))
            self.externalBarrier.wait()
            self.marketLock.acquire()
            self.calcPrice()
            self.marketLock.release()
            self.dayResults = 0
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                server_socket.setblocking(False)
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    server_socket.bind((self.host, self.port))
                except socket.error as e:
                    if e.errno == errno.EADDRINUSE:
                        print("Port is already in use")
                        sys.exit()
                    else:
                        # something else raised the socket.error exception
                        print(e)
                server_socket.listen(4)
                self.serve = True
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    self.marketBarrier.wait()
                    self.log("Serving day {}".format(self.day))
                    futures = []
                    while self.serve:
                        readable, writable, error = select.select([server_socket], [], [], 0.1)
                        if server_socket in readable:
                            client_socket, address = server_socket.accept()
                            futures.append(executor.submit(self.handle_home, client_socket, address))
                    concurrent.futures.wait(futures)
                    executor.shutdown()
                server_socket.close()
            self.calcDemand()
            self.updateExternalEvents()
        self.external.join()


class Weather(mp.Process):
    def __init__(self, start_new_day_barrier, sharedWH: mp.Array, maxDays, logLock):
        super().__init__()
        self.start_new_day_barrier = start_new_day_barrier
        self.sharedWH: mp.Array = sharedWH
        self.maxDays = maxDays
        self.logLock = logLock
        self.day = 0
        self.season = 0
        self.meanTemp = [15, 25, 10, 0]
        self.sharedWH[0] = self.meanTemp[0]

    def log(self, msg):
        pass
        # self.logLock.acquire()
        # print("Weather: {}".format(msg))
        # self.logLock.release()

    def updateSeason(self):
        if self.day % 10 == 0 and self.day != 0:
            self.season = (self.season + 1) % 4

    def calcWeather(self):
        self.updateSeason()
        pastTemp = self.sharedWH[0]
        random_random = random.uniform(0.2, 0.8)
        newTemp = norm.ppf(random_random, self.meanTemp[self.season], 3)
        if newTemp > pastTemp:
            self.sharedWH[0] = min(newTemp, pastTemp + 3)
        else:
            self.sharedWH[0] = max(newTemp, pastTemp - 3)

    def run(self) -> None:
        while self.day < self.maxDays:
            self.start_new_day_barrier.wait()
            self.calcWeather()
            self.start_new_day_barrier.wait()
            self.start_new_day_barrier.wait()
            self.day += 1


class External(mp.Process):
    def __init__(self, start_new_day_barrier: mp.Barrier, maxDays: int, externalBarrier: mp.Barrier, marketPID: int):
        super().__init__()
        self.start_new_day_barrier: mp.Barrier = start_new_day_barrier
        self.ppid = marketPID
        self.day = 0
        self.maxDays = maxDays
        self.externalBarrier: mp.Barrier = externalBarrier

    def log(self, msg):
        # print("External: {}".format(msg))
        pass

    def sendSignal(self, signum):
        os.kill(self.ppid, signum)

    def sendExternalEvent(self, eventID, duration, factor):
        # encode eventID, duration, factor to binary
        eventIDBin = convertDecimalToBinary(eventID)
        durationBin = convertDecimalToBinary(duration)
        factorBin = convertDecimalToBinary(int(factor * 10))
        # send signals
        for eBin in [eventIDBin, durationBin, factorBin]:
            for i in range(len(eBin)):
                time.sleep(0.1)
                if eBin[i] == 0:
                    self.sendSignal(signal.SIGUSR1)
                else:
                    self.sendSignal(signal.SIGUSR2)
            self.sendSignal(signal.SIGALRM)

    def run(self) -> None:
        while self.day < self.maxDays:
            # wait for new day
            self.log("External waiting for new day")
            self.start_new_day_barrier.wait()
            # wait for weather to be calculated
            self.start_new_day_barrier.wait()
            # Wait for data to be printed
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
                self.sendExternalEvent(id, duration, beta)
            self.log("External waiting for externalBarrier")
            self.externalBarrier.wait()


class Time(mp.Process):
    def __init__(self, nHomes, maxDays):
        super().__init__()
        self.weatherLine = None
        self.priceline = None
        self.sharedWH: mp.Array = None
        self.market: Market = None
        self.homes: List[Home] = None
        self.weather: Weather = None
        self.day = 0
        self.nHomes = nHomes
        self.maxDays = maxDays
        self.start_new_day_barrier = mp.Barrier(nHomes + 4)
        self.marketBarrier = mp.Barrier(nHomes + 1)
        self.logLock = mp.Lock()
        self.marketDataBarrier = mp.Barrier(2)
        self.marketTimeParentPipe, self.marketTimeChildPipe = mp.Pipe()
        self.weatherColors = [["Spring", 'springgreen'], ["Summer", 'orange'], ["Autumn", 'peru'], ["Winter", 'lightskyblue']]
        self.weatherNum = 0

    def startNewDay(self):
        self.day += 1
        # self.logLock.acquire()
        # print("Good Morning, it is day : " + str(self.day))
        # self.logLock.release()

    def createWeather(self):
        self.weather = Weather(self.start_new_day_barrier, self.sharedWH, self.maxDays, self.logLock)
        self.weather.start()

    def createHomes(self):
        home_barrier = mp.Barrier(self.nHomes)
        self.homes = [
            Home(i, self.start_new_day_barrier, home_barrier, self.sharedWH, 128, 192, 256, random.randint(50, 100),
                 random.randint(50, 100), random.randint(0, 2), self.maxDays, self.marketBarrier, self.logLock) for i in
            range(self.nHomes)]
        for h in self.homes:
            print("starting home " + str(h.id) + "...")
            h.start()

    def createMarket(self):
        self.market = Market(self.start_new_day_barrier, self.sharedWH, 0.45, 0.8, 0.1, [0.3], [], self.maxDays,
                             self.marketBarrier, self.logLock, self.marketDataBarrier, self.marketTimeChildPipe)
        print("market starting...")
        self.market.start()

    def initPlot(self):
        i = len(ExternalEvent.EVENTS)
        self.pricePlt, (self.pricePlot, self.weatherPlot) = plt.subplots(2, sharex=True)

        # self.pricePlot.set_ylabel('Energy Price €/kWh')
        # self.pricePlot.set_title('Energy Price and Demand')
        self.demandPlot = self.pricePlot.twinx()
        # self.demandPlot.set_ylabel('Current Demand (1=equilibrium)')
        self.weatherPlot.set_title('Weather')
        self.weatherPlot.set_xlabel('Days')
        self.weatherPlot.set_ylabel('Temperature (°C)')
        # self.weatherPlt, self.weatherPlot = plt.subplots(1)
        # self.eventPlt, self.eventPlots = plt.subplots(i // 2, i // 2)
        plt.tight_layout(pad=3)
        self.plotsX = []
        self.plotsYs = []
        self.plotsYs.append([])
        self.plotsYs.append([])
        self.plotsYs.append([])
        plt.pause(0.01)
        plt.ion()
        # self.anim = animation.FuncAnimation(self.marketPlt, self.animate, interval=100)
        # self.animate()

    def animate(self):
        self.plotsX.append(self.day)
        data = self.marketTimeParentPipe.recv()
        events = data[3]




        self.plotsYs[0].append(data[0])
        self.plotsYs[2].append(data[2])
        self.plotsYs[1].append(self.sharedWH[0])
        if not self.priceline:
            # self.pricePlot.clear()
            self.priceline, = self.pricePlot.plot(self.plotsX, self.plotsYs[0],color='red', label='Price')
            self.demandPlot.clear()
            self.demandLine,  = self.demandPlot.plot(self.plotsX, self.plotsYs[2], color='blue', label='Demand')
            self.demandFill = self.demandPlot.fill_between(self.plotsX, self.plotsYs[2], 0, color='blue', alpha=0.3)
            self.pricePlot.legend(loc='upper left')
            self.demandPlot.legend(loc='upper right')
        else:
            self.priceline.set_data(self.plotsX, self.plotsYs[0])
            # self.demandPlot.clear()
            self.demandLine.set_data(self.plotsX, self.plotsYs[2])
            self.demandFill.remove()
            self.demandFill = self.demandPlot.fill_between(self.plotsX, self.plotsYs[2], 0, color='blue', alpha=0.3)

        self.pricePlot.set_ylim(0, max(self.plotsYs[0])+1)
        self.pricePlot.set_xlim(max(0, self.day-100), self.day+1)
        self.demandPlot.set_ylim(0, max(self.plotsYs[2])+1)
        self.demandPlot.set_xlim(max(0, self.day-100), self.day+1)
        if not self.weatherLine:
            self.weatherLine, = self.weatherPlot.plot(self.plotsX, self.plotsYs[1])
        else:
            self.weatherLine.set_data(self.plotsX, self.plotsYs[1])
        if self.day % 10 == 0:
            if self.day != 0:
                self.weatherNum = (self.weatherNum + 1) % 4 #using sharedMemory is way slower than this
            self.weatherPlot.axvspan(self.day, self.day+10, color=self.weatherColors[self.weatherNum][1], alpha=0.5)
            self.weatherPlot.text(self.day+5, 32, self.weatherColors[self.weatherNum][0], ha='center', va='center', fontsize=10, clip_on=True, rotation=90)
        self.weatherPlot.set_xlim(max(0, self.day-100), self.day+1)
        self.weatherPlot.set_ylim(min(self.plotsYs[1])-1, max(max(self.plotsYs[1]),45))
        plt.pause(0.05)


        # for i, plot in enumerate(self.eventPlots.flat):
        #     plot.set_title("I am plot for event " + str(ExternalEvent.EVENTS[i]['name']))
        #     plot.plot([0, 1, 2, 3], [0, 1, 2, 5])
        #     # plot.clear()
        # plt.pause(1)
        # self.plotsYs[0].append(self.market.price)
        # print(self.plotsX, self.plotsYs[0])
        # self.pricePlot.plot(self.plotsX, self.plotsYs[0])
        # plt.pause(0.2)

    # def plot(self):
    #     marketPlt = plt.figure()
    #     i = len(ExternalEvent.EVENTS)
    #     plots = marketPlt.add_subplot((i+1)//3+1, 3, 1)
    #     plotsXs = []
    #     plotsYs = []
    #
    #
    #
    #     def animate(_, xs, ys):
    #
    #         # Read temperature (Celsius) from TMP102
    #         temp_c = round(random.random(), 2)
    #
    #         # Add x and y to lists
    #         xs.append(datetime.datetime.now().strftime('%H:%M:%S.%f'))
    #         ys.append(temp_c)
    #
    #         # Limit x and y lists to 20 items
    #         xs = xs[-20:]
    #         ys = ys[-20:]
    #
    #         # Draw x and y lists
    #         ax.clear()
    #         ax.plot(xs, ys)
    #
    #         # Format plot
    #         plt.xticks(rotation=45, ha='right')
    #         plt.subplots_adjust(bottom=0.30)
    #         plt.title('TMP102 Temperature over Time')
    #         plt.ylabel('Temperature (deg C)')
    #
    #     # Set up plot to call animate() function periodically
    #     ani = animation.FuncAnimation(marketPlt, animate, fargs=(xs, ys), interval=100)
    #     # we're using a remote IDE on wsl, so we need to use the following line to show the plot
    #     plt.show()

    def run(self):
        self.sharedWH = mp.Array('d', range(10))  # 0: Température
        self.createWeather()
        self.createHomes()
        self.createMarket()
        self.initPlot()
        while self.day < self.maxDays:
            self.start_new_day_barrier.wait()
            # wait for weather to be calculated
            self.start_new_day_barrier.wait()
            self.marketDataBarrier.wait()
            # print(self.marketTimeParentPipe.recv(), self.sharedWH[0])
            self.animate()
            self.start_new_day_barrier.wait()
            self.startNewDay()
            # time.sleep(1)
        print("ending time...")
        for h in self.homes:
            h.join()
            print(h.id)
        print("home joined")
        self.market.join()
        self.weather.join()
        time.sleep(0.5)
        plt.show(block=True)
        # plt.show()
        # plt.close('all')

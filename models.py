import multiprocessing
import threading
class ExternalEvent:
    def __init__(self, duration, beta):
        self.duration = duration
        self.beta = beta

class Home(multiprocessing.Process):
    def __init__(self, sharedWH):
        super().__init__()
        self.sharedWH = sharedWH

    def run(self) -> None:
        pass


class Market(multiprocessing.Process):
    def __init__(self, sharedWH, startPrice, gamma, demandAlpha, internalFactorsAlpha, externalEvents,externalFactorsBeta):
        super().__init__()
        self.price = startPrice
        self.gamma = gamma
        self.sharedWH = sharedWH
        self.internalFactorsAlpha = internalFactorsAlpha # factors for weather
        self.externalEvents = externalEvents
        self.demand = 1
        self.demandAlpha = demandAlpha

    def calcContributionFactors(self):
        sum = 0
        # for i, intFact in self.sharedWH:
        #     sum += intFact * self.internalFactorsAlpha[i]
        for extFact in self.externalEvents:
            sum += ex


    def calcPrice(self):
        self.price = self.gamma * self.price +



class Weather(multiprocessing.Process):
    def __init__(self, sharedWH):
        super().__init__()
        self.sharedWH = sharedWH

    def run(self) -> None:
        pass

class External(multiprocessing.Process):
    pass


class Time(multiprocessing.Process):
    def __init__(self, nHomes):
        super().__init__()
        self.homes = None
        self.weather = None
        self.day = 0
        self.nHomes = nHomes
        self.start_new_day_barrier = threading.Barrier(3+nHomes, action=self.startNewDay)

    def startNewDay(self):
        self.day += 1
        print("Good Morning, it is day : "+str(self.day))


    def createWeather(self):
        self.weather = Weather(self.sharedWH)
        self.weather.start()

    def createHomes(self):
        self.homes = [Home(self.sharedWH) for _ in range(self.nHomes)]
        for h in self.homes:
            h.start()


    def run(self):
        self.sharedWH = multiprocessing.Array('i', range(10)) # 0: Température
        self.createWeather()
        self.createHomes()
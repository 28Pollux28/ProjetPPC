from scipy.stats import norm

mu = 10
x = norm.ppf(0.99, loc=mu, scale=1)
sigma = (x-mu)/2
print(sigma)
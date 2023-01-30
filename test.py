import math
import random
import time
import socket
import select
import concurrent.futures

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import animation
import datetime as dt

from matplotlib.patches import Rectangle
from scipy.stats import norm

matplotlib.use('TkAgg')
#
# fig, ax = plt.subplots(3, 3)
# print(ax)
# xs = []
# ys = []
#
# def animate(i, xs, ys):
#
#     # Read temperature (Celsius) from TMP102
#     temp_c = round(random.random(), 2)
#
#     # Add x and y to lists
#     xs.append(dt.datetime.now().strftime('%H:%M:%S.%f'))
#     ys.append(temp_c)
#
#     # Limit x and y lists to 20 items
#     xs = xs[-20:]
#     ys = ys[-20:]
#
#     # Draw x and y lists
#     ax.clear()
#     ax.plot(xs, ys)
#
#     # Format plot
#     plt.xticks(rotation=45, ha='right')
#     plt.subplots_adjust(bottom=0.30)
#     plt.title('TMP102 Temperature over Time')
#     plt.ylabel('Temperature (deg C)')
#
# # Set up plot to call animate() function periodically
# ani = animation.FuncAnimation(fig, animate, fargs=(xs, ys))
# # we're using a remote IDE on wsl, so we need to use the following line to show the plot
# plt.show()

# serve = True
# fig, ax = plt.subplots(1, 1)
# x = np.linspace(-10, 40, 10000)
# for duration in range(2,40):
#     dur2 = duration / 2
#     srt = math.sqrt(dur2)
#     dev = srt-srt/duration
#
#     pdf = norm.pdf(x, dur2, srt)
#     max = np.amax(pdf)
#     pdf = pdf/max
#     ax.plot(x, pdf, lw=5, alpha=0.6, label='norm pdf')
#
# plt.show()

# import numpy as np
# import matplotlib.pyplot as plt


# fig, ax = plt.subplots()
# lx = [0, 1, 2, 3, 4, 5, 6]
# l = [1, 2, 3, 4, 5, 6, 7]
# line, = ax.plot(l)
# ax.set_ylim(0, 10)
# ax.set_xlim(0, 10)
#
# # Add two custom background color rectangles
# ax.axvspan(1.5, 2.5, facecolor='red', alpha=0.5)
#
# plt.pause(2)
# ax.axvspan(3.0, 10.0, facecolor='skyblue', alpha=0.5)
# l.append(8)
# lx.append(7)
# line.set_data(lx, l)
# plt.show()

# Generate data for line chart
x = np.arange(0, 10, 1)
y = x**2

# Generate data for bar chart
x_bar = np.arange(0, 10, 2)
y_bar = x_bar**3

# Create a plot
fig, ax1 = plt.subplots(figsize=(10, 5))

# Plot the line chart on the first axes
ax1.plot(x, y, label='Line Chart', color='C0')

# Create a second y-axis for the bar chart
ax2 = ax1.twinx()

# Plot the bar chart on the second axes
ax2.bar(x_bar, y_bar, label='Bar Chart', color='C1')

# Add a legend to the plot
ax1.legend(loc='upper left')
ax2.legend(loc='upper right')

# Show the plot
plt.show()

# def socket_handler(s, a):
#     global serve
#     with s:
#         print("Connected to client: ", a)
#         data = s.recv(1024)
#         m = data.decode()[0]
#         if m == "1":
#             s.send(time.asctime().encode())
#         if m == "2":
#             print("Terminating time server!")
#             serve = False
#         print("Disconnecting from client: ", a)
#
#
# HOST = "localhost"
# PORT = 1789
# with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
#     server_socket.setblocking(False)
#     server_socket.bind((HOST, PORT))
#     server_socket.listen(4)
#     with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
#         while serve:
#             readable, writable, error = select.select([server_socket], [], [], 1)
#             if server_socket in readable:
#                 client_socket, address = server_socket.accept()
#                 executor.submit(socket_handler, client_socket, address)




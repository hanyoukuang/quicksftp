import pyte
s = pyte.HistoryScreen(80, 24, history=100)
stream = pyte.Stream(s)
for i in range(30):
    stream.feed(f"Line {i}\r\n")
s.prev_page()
print(s.buffer[0][0].data)
s.next_page()
print(s.buffer[0][0].data)

from tkdeft import *
from tkinter import *
from tkinter.font import *

root = DWindow()
root.configure(background="#ffffff")
root.configure(background="#202020")

frame1 = DFrame()

badge1 = DBadge(frame1, text="DBadge")
badge1.pack(padx=5, pady=5)

button1 = DButton(frame1, text="DButton", command=lambda: print("DButton -> Clicked"))
button1.pack(fill="x", padx=5, pady=5)

button2 = DAccentButton(frame1, text="DAccentButton", command=lambda: print("DAccentButton -> Clicked"))
button2.pack(fill="x", padx=5, pady=5)

entry1 = DEntry(frame1)
entry1.pack(fill="x", padx=5, pady=5)

text1 = DText(frame1)
text1.pack(fill="x", padx=5, pady=5)

frame1.pack(fill="both", expand="yes", side="left", padx=5, pady=5)

frame2 = DDarkFrame()

badge2 = DDarkBadge(frame2, text="DDarkBadge", width=100)
badge2.pack(padx=5, pady=5)

button3 = DDarkButton(frame2, text="DDarkButton", command=lambda: print("DDarkButton -> Clicked"))
button3.pack(fill="x", padx=5, pady=5)

button4 = DDarkAccentButton(frame2, text="DDarkAccentButton", command=lambda: print("DDarkAccentButton -> Clicked"))
button4.pack(fill="x", padx=5, pady=5)

entry2 = DDarkEntry(frame2)
entry2.pack(fill="x", padx=5, pady=5)

text2 = DDarkText(frame2)
text2.pack(fill="x", padx=5, pady=5)

frame2.pack(fill="both", expand="yes", side="right", padx=5, pady=5)
root.mainloop()

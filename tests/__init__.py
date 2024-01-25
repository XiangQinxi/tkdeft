# 绘制100*240像素,圆角20的矩形.
import cv2 as cv
import numpy as np

img = np.zeros((200, 360, 3), dtype=np.uint8) + 255
# 采用等轴椭圆起始点绘制1/4圆角
cv.ellipse(img, (50, 50), (20, 20), 0, 180, 270, (0, 0, 255), 2)
cv.ellipse(img, (270, 50), (20, 20), 0, 270, 360, (0, 0, 255), 2)
cv.ellipse(img, (270, 110), (20, 20), 0, 0, 90, (0, 0, 255), 2)
cv.ellipse(img, (50, 110), (20, 20), 0, 90, 180, (0, 0, 255), 2)
# 绘制直线
cv.line(img, (50, 30), (270, 30), (255, 0, 0), 2)
cv.line(img, (290, 50), (290, 110), (255, 0, 0), 2)
cv.line(img, (270, 130), (50, 130), (255, 0, 0), 2)
cv.line(img, (30, 110), (30, 50), (255, 0, 0), 2)
# 显示图像
cv.imwrite("test.png", img)
# cv.imshow('rectangle',img)

from tkinter import Tk, PhotoImage, Label

root = Tk()

img_png = PhotoImage(file='test.png')
label_img = Label(root, image=img_png)
label_img.pack()

root.mainloop()

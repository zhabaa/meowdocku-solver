import cv2
import numpy as np

SCREEN_PATH = "img/tmp/TEST_SCREEN.png"
TEMPLATE_PATH = "img/TEMPLATE.png"

screen = cv2.imread(SCREEN_PATH, cv2.IMREAD_GRAYSCALE)
template = cv2.imread(TEMPLATE_PATH, cv2.IMREAD_GRAYSCALE)

width, height = template.shape[::-1]

result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)

threshold = 0.2
loc = np.where( result >= threshold)

for pt in zip(*loc[::-1]):
    cv2.rectangle(screen, pt, (pt[0] + width, pt[1] + height), (0,0,255), 2)

cv2.imwrite('result.png',screen)

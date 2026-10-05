import cv2
import numpy as np
from scipy import stats
import time
from pprint import pprint
from cv2 import UMat
from PIL import Image


SCREEN_PATH = "img/tmp/TEST_SCREEN10.png"
TEMPLATE_PATH = "img/TEMPLATE.png"
THRESHOLD = 220


# cv2.namedWindow('window', cv2.WINDOW_NORMAL)
# cv2.resizeWindow('window', 800, 600)

screen = cv2.imread(SCREEN_PATH)

IMAGE_HEIGHT, IMAGE_WIDTH, LAYERS = screen.shape

cropped_screen = screen[640:1800, 0:IMAGE_WIDTH]


filtered_screen = cv2.medianBlur(src=cropped_screen, ksize=7)

gray_filtered_screen = cv2.cvtColor(src=filtered_screen,
                                    code=cv2.COLOR_BGR2GRAY)

ret, threshold_image = cv2.threshold(src=gray_filtered_screen, 
                                     thresh=THRESHOLD, maxval=255, 
                                     type=cv2.THRESH_BINARY)

contours, hierarchy = cv2.findContours(image=threshold_image, 
                                       mode=cv2.RETR_TREE, 
                                       method=cv2.CHAIN_APPROX_SIMPLE)

contours_image = np.uint8(np.zeros((cropped_screen.shape[0], 
                                    cropped_screen.shape[1])))

contour_areas = [(i, cv2.contourArea(i)) for i in contours]

contour_areas.sort(key=lambda x: x[1])
contour_areas.pop(-1)

board_coordinates = []

for contour, area in contour_areas:
    x, y, w, h = cv2.boundingRect(contour)
    center_x = x + w // 2
    center_y = y + h // 2
    
    board_coordinates.append([center_x, center_y])
    
board_coordinates.sort(key=lambda x: x[1])
    
print(board_coordinates)

# cropped_screen = screen[640:1800, 0:IMAGE_WIDTH]
# for x, y in board_coordinates:
#     cv2.circle(screen, (x, y + 640), 3, (0, 0, 0), 2)
# cv2.imshow("window", screen)
# cv2.waitKey(0)
# cv2.imwrite(f"{time.time()}.png", screen)

color_mask = [[None for _ in range(int(len(board_coordinates) ** 0.5))] for _ in range(int(len(board_coordinates) ** 0.5))]
pprint(color_mask)

print(int(len(board_coordinates) ** 0.5))

for i in range(int(len(board_coordinates) ** 0.5)):
    for j in range(int(len(board_coordinates) ** 0.5)):
        color_mask[i][j] = 
        

pprint(color_mask)

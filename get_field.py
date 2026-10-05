import cv2
import numpy as np

SCREEN_PATH = "img/tmp/TEST_SCREEN.png"
TEMPLATE_PATH = "img/TEMPLATE.png"
THRESHOLD = 250

cv2.namedWindow('window', cv2.WINDOW_NORMAL)
cv2.resizeWindow('window', 800, 600)

screen = cv2.imread(SCREEN_PATH)

filtered_screen = cv2.medianBlur(screen, 7)

gray_filtered_screen = cv2.cvtColor(filtered_screen, cv2.COLOR_BGR2GRAY)

ret, threshold_image = cv2.threshold(gray_filtered_screen, THRESHOLD,
                                     255, cv2.THRESH_BINARY)

contours, hierarchy = cv2.findContours(threshold_image, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

contours_image = np.uint8(np.zeros((screen.shape[0], screen.shape[1])))

cv2.drawContours(contours_image, contours, -1, (255, 255, 255), 1)

cv2.imshow("window", contours_image)
cv2.waitKey(0)

# cv2.imwrite("contours.png", contours_image)

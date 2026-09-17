#include "Arduino_LED_Matrix.h"

ArduinoLEDMatrix matrix;

// 12x8 LED Matrix Bitmaps (3x 32-bit integers per 96-LED frame)
// Frame 1: Shopping Cart + Ground dots (Shift A)
const uint32_t cart_frame_1[] = {
  0x0380e40b,
  0xc0bf0830,
  0x830bf005
};

// Frame 2: Shopping Cart + Ground dots (Shift B - Creates moving ground effect)
const uint32_t cart_frame_2[] = {
  0x0380e40b,
  0xc0bf0830,
  0x830bf00a
};

void setup() {
  matrix.begin();
}

void loop() {
  // Continuously loop the cart animation on power on
  matrix.loadFrame(cart_frame_1);
  delay(180);
  matrix.loadFrame(cart_frame_2);
  delay(180);
}